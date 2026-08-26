"""轻量实时曲线窗口；绘图故障不会阻塞仪器测量或 CSV 保存。"""

import ctypes
import math
import multiprocessing as mp
import sys


_COLORS = (
    "#0067c0",
    "#d83b01",
    "#107c10",
    "#8764b8",
    "#c239b3",
    "#038387",
)


def _plain_text(value):
    """把项目当前使用的少量 Matplotlib 数学标签转成普通文本。"""
    return (
        str(value)
        .replace(r"$R_{xy}$", "Rxy")
        .replace(r"$\Omega$", "Ω")
        .replace("$", "")
    )


def _normalize_panels(xlabel, ylabel, title, series, panels):
    if panels is None:
        series_names = list(series or [""])
        panels = [
            {
                "title": title,
                "xlabel": xlabel,
                "ylabel": ylabel,
                "series": series_names,
            }
        ]

    normalized = []
    series_index = 0
    for panel in panels:
        names = list(panel.get("series") or [""])
        indexes = list(range(series_index, series_index + len(names)))
        series_index += len(names)
        normalized.append(
            {
                "title": _plain_text(panel.get("title", "")),
                "xlabel": _plain_text(panel.get("xlabel", xlabel or "")),
                "ylabel": _plain_text(panel.get("ylabel", ylabel or "")),
                "series": [_plain_text(name) for name in names],
                "series_indexes": indexes,
            }
        )

    if series_index < 1:
        raise ValueError("实时图至少需要一条曲线")
    return normalized, series_index


def _set_windows_low_priority():
    """让实时图在 Win10 上主动让出 CPU；失败不影响绘图。"""
    if sys.platform != "win32":
        return
    try:
        below_normal_priority_class = 0x00004000
        process = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetPriorityClass(
            process, below_normal_priority_class
        )
    except Exception:
        pass


def _set_windows_dpi_awareness():
    """避免 Win10 在 125%/150% 缩放时把整个窗口作为位图放大。"""
    if sys.platform != "win32":
        return

    try:
        per_monitor_v2 = ctypes.c_void_p(-4)
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(per_monitor_v2):
            return
    except Exception:
        pass

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _configure_tk_scaling(root):
    """让 Tk 的 point 字体尺寸跟随当前显示器 DPI。"""
    try:
        dpi = float(root.winfo_fpixels("1i"))
        root.tk.call("tk", "scaling", max(1.0, dpi / 72.0))
    except Exception:
        pass


def _format_tick(value):
    if value == 0:
        return "0"
    if abs(value) >= 1e4 or abs(value) < 1e-3:
        return f"{value:.2e}"
    return f"{value:.4g}"


def _expanded_range(values):
    low = min(values)
    high = max(values)
    if not math.isfinite(low) or not math.isfinite(high):
        return 0.0, 1.0
    if low == high:
        padding = max(abs(low) * 0.05, 1.0 if low == 0 else 1e-12)
    else:
        padding = (high - low) * 0.06
    return low - padding, high + padding


def _downsample_indexes(length, pixel_width):
    """显示点不超过横向像素数，并始终保留最新点。"""
    if length <= pixel_width:
        return range(length)
    step = max(1, math.ceil(length / pixel_width))
    indexes = list(range(0, length, step))
    if indexes[-1] != length - 1:
        indexes.append(length - 1)
    return indexes


def _draw_panel(canvas, panel, columns):
    width = max(canvas.winfo_width(), 320)
    height = max(canvas.winfo_height(), 220)
    canvas.delete("plot")

    left, right, top, bottom = 88, 24, 38, 58
    plot_width = max(width - left - right, 10)
    plot_height = max(height - top - bottom, 10)
    x0, x1 = left, left + plot_width
    y0, y1 = top, top + plot_height

    x_values = columns[0]
    panel_y = [columns[index + 1] for index in panel["series_indexes"]]
    finite_x = [value for value in x_values if math.isfinite(value)]
    finite_y = [
        value
        for values in panel_y
        for value in values
        if math.isfinite(value)
    ]

    if not finite_x or not finite_y:
        canvas.create_text(
            width / 2,
            height / 2,
            text="Waiting for data...",
            fill="#666666",
            font=("Segoe UI", 10),
            tags="plot",
        )
        return

    xmin, xmax = _expanded_range(finite_x)
    ymin, ymax = _expanded_range(finite_y)

    canvas.create_rectangle(
        x0, y0, x1, y1, outline="#777777", width=1, tags="plot"
    )

    tick_count = 5
    for tick in range(tick_count + 1):
        fraction = tick / tick_count
        px = x0 + fraction * plot_width
        py = y1 - fraction * plot_height
        xv = xmin + fraction * (xmax - xmin)
        yv = ymin + fraction * (ymax - ymin)

        canvas.create_line(px, y0, px, y1, fill="#d0d0d0", tags="plot")
        canvas.create_line(x0, py, x1, py, fill="#d0d0d0", tags="plot")
        canvas.create_text(
            px,
            y1 + 16,
            text=_format_tick(xv),
            fill="#333333",
            font=("Segoe UI", 10),
            tags="plot",
        )
        canvas.create_text(
            x0 - 8,
            py,
            text=_format_tick(yv),
            anchor="e",
            fill="#333333",
            font=("Segoe UI", 10),
            tags="plot",
        )

    canvas.create_text(
        (x0 + x1) / 2,
        height - 12,
        text=panel["xlabel"],
        fill="#111111",
        font=("Segoe UI", 11),
        tags="plot",
    )
    canvas.create_text(
        18,
        (y0 + y1) / 2,
        text=panel["ylabel"],
        angle=90,
        fill="#111111",
        font=("Segoe UI", 11),
        tags="plot",
    )
    if panel["title"]:
        canvas.create_text(
            (x0 + x1) / 2,
            17,
            text=panel["title"],
            fill="#111111",
            font=("Segoe UI", 12, "bold"),
            tags="plot",
        )

    indexes = _downsample_indexes(len(x_values), int(plot_width))
    for local_index, values in enumerate(panel_y):
        color = _COLORS[panel["series_indexes"][local_index] % len(_COLORS)]
        coords = []
        last_point = None
        for index in indexes:
            xv = x_values[index]
            yv = values[index]
            if not math.isfinite(xv) or not math.isfinite(yv):
                continue
            px = x0 + (xv - xmin) / (xmax - xmin) * plot_width
            py = y1 - (yv - ymin) / (ymax - ymin) * plot_height
            coords.extend((px, py))
            last_point = (px, py)

        if len(coords) >= 4:
            canvas.create_line(*coords, fill=color, width=2, tags="plot")
        if last_point is not None:
            px, py = last_point
            canvas.create_oval(
                px - 2,
                py - 2,
                px + 2,
                py + 2,
                fill=color,
                outline=color,
                tags="plot",
            )

    named_series = [name for name in panel["series"] if name]
    if len(named_series) > 1:
        legend_y = y0 + 9
        for local_index, name in enumerate(panel["series"]):
            if not name:
                continue
            color = _COLORS[
                panel["series_indexes"][local_index] % len(_COLORS)
            ]
            canvas.create_line(
                x1 - 142,
                legend_y,
                x1 - 118,
                legend_y,
                fill=color,
                width=2,
                tags="plot",
            )
            canvas.create_text(
                x1 - 112,
                legend_y,
                text=name,
                anchor="w",
                fill="#222222",
                font=("Segoe UI", 10),
                tags="plot",
            )
            legend_y += 17


def _read_snapshot(shared_data, sequence, data_lock, capacity, column_count):
    if not data_lock.acquire(False):
        return None
    try:
        end_sequence = int(sequence.value)
        count = min(end_sequence, capacity)
        start_sequence = end_sequence - count
        columns = [[] for _ in range(column_count)]
        for sample_sequence in range(start_sequence, end_sequence):
            row = (sample_sequence % capacity) * column_count
            for column in range(column_count):
                columns[column].append(shared_data[row + column])
        return end_sequence, columns
    finally:
        data_lock.release()


def _plot_main(
    shared_data,
    sequence,
    data_lock,
    stop_event,
    window_title,
    panels,
    capacity,
    column_count,
    refresh_s,
):
    _set_windows_dpi_awareness()
    _set_windows_low_priority()
    try:
        import tkinter as tk
    except Exception as exc:
        print(f"实时绘图启动失败，当前 Python 缺少 Tkinter: {exc}")
        return

    try:
        root = tk.Tk()
    except Exception as exc:
        print(f"实时绘图窗口创建失败: {exc}")
        return

    _configure_tk_scaling(root)
    root.title(_plain_text(window_title or "Live Plot"))
    initial_height = 520 if len(panels) == 1 else 380 * len(panels)
    minimum_height = 360 if len(panels) == 1 else 240 * len(panels)
    root.geometry(f"860x{initial_height}")
    root.minsize(560, minimum_height)

    canvases = []
    for _panel in panels:
        canvas = tk.Canvas(root, background="white", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        canvases.append(canvas)

    refresh_ms = max(50, int(refresh_s * 1000))
    last_sequence = -1
    last_columns = None
    force_redraw = True

    def close_window():
        stop_event.set()
        root.destroy()

    def request_redraw(_event=None):
        nonlocal force_redraw
        force_redraw = True

    def refresh():
        nonlocal last_sequence, last_columns, force_redraw
        if stop_event.is_set():
            close_window()
            return

        snapshot = _read_snapshot(
            shared_data,
            sequence,
            data_lock,
            capacity,
            column_count,
        )
        if snapshot is not None:
            current_sequence, columns = snapshot
            if current_sequence != last_sequence:
                last_sequence = current_sequence
                last_columns = columns
                force_redraw = True

        if force_redraw and last_columns is not None:
            for canvas, panel in zip(canvases, panels):
                _draw_panel(canvas, panel, last_columns)
            force_redraw = False

        root.after(refresh_ms, refresh)

    root.protocol("WM_DELETE_WINDOW", close_window)
    for canvas in canvases:
        canvas.bind("<Configure>", request_redraw)
    root.after(0, refresh)
    root.mainloop()


class LivePlotProcess:
    """非阻塞实时图；共享缓冲只保留最新显示点，原始数据不受影响。"""

    def __init__(
        self,
        xlabel=None,
        ylabel=None,
        title="Live Plot",
        max_points=1000,
        refresh_s=0.2,
        *,
        series=None,
        panels=None,
    ):
        self._panels, self._series_count = _normalize_panels(
            xlabel, ylabel, title, series, panels
        )
        self._capacity = max(2, int(max_points))
        self._column_count = self._series_count + 1

        ctx = mp.get_context("spawn")
        self._shared_data = ctx.Array(
            "d", self._capacity * self._column_count, lock=False
        )
        self._sequence = ctx.Value("Q", 0, lock=False)
        self._data_lock = ctx.Lock()
        self._stop_event = ctx.Event()
        self._started = False
        self._process = ctx.Process(
            target=_plot_main,
            args=(
                self._shared_data,
                self._sequence,
                self._data_lock,
                self._stop_event,
                title,
                self._panels,
                self._capacity,
                self._column_count,
                max(0.05, float(refresh_s)),
            ),
            daemon=True,
        )

    def start(self):
        if not self._started:
            self._process.start()
            self._started = True

    def add(self, x, *values):
        """写入显示数据；锁忙时直接丢显示点，绝不等待测量进程。"""
        if len(values) != self._series_count or self._stop_event.is_set():
            return
        if not self._data_lock.acquire(False):
            return
        try:
            sample_sequence = int(self._sequence.value)
            row = (sample_sequence % self._capacity) * self._column_count
            self._shared_data[row] = float(x)
            for offset, value in enumerate(values, start=1):
                self._shared_data[row + offset] = float(value)
            self._sequence.value = sample_sequence + 1
        except (TypeError, ValueError):
            return
        finally:
            self._data_lock.release()

    def close(self):
        self._stop_event.set()
        if not self._started:
            return
        self._process.join(timeout=2.0)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=1.0)
