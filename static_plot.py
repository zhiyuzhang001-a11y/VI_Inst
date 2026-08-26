"""零第三方依赖的静态 SVG 曲线绘图器。"""

from html import escape
import math
from pathlib import Path
import webbrowser


COLORS = ("#0067c0", "#d83b01", "#107c10", "#8764b8", "#c239b3", "#038387")


def _numbers(values):
    return [float(value) for value in values]


def _format_tick(value):
    if value == 0:
        return "0"
    if abs(value) >= 1e4 or abs(value) < 1e-3:
        return f"{value:.2e}"
    return f"{value:.4g}"


def _expanded_range(values):
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return 0.0, 1.0
    low, high = min(finite), max(finite)
    if low == high:
        padding = max(abs(low) * 0.05, 1.0 if low == 0 else 1e-12)
    else:
        padding = (high - low) * 0.06
    return low - padding, high + padding


def _series_points(x_values, y_values, style):
    pairs = [
        (x, y)
        for x, y in zip(_numbers(x_values), _numbers(y_values))
        if math.isfinite(x) and math.isfinite(y)
    ]
    if style != "step" or len(pairs) < 2:
        return pairs

    stepped = [pairs[0]]
    for previous, current in zip(pairs, pairs[1:]):
        stepped.append((current[0], previous[1]))
        stepped.append(current)
    return stepped


def _svg_text(x, y, text, *, size=14, anchor="middle", weight="normal", rotate=None):
    transform = f' transform="rotate({rotate} {x:.2f} {y:.2f})"' if rotate is not None else ""
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" '
        f'font-family="Segoe UI, Arial, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="#1a1a1a"{transform}>{escape(str(text))}</text>'
    )


def _draw_panel(panel, box, clip_id):
    box_x, box_y, box_width, box_height = box
    left, right, top, bottom = 82, 24, 42, 62
    x0 = box_x + left
    y0 = box_y + top
    width = max(box_width - left - right, 20)
    height = max(box_height - top - bottom, 20)
    x1, y1 = x0 + width, y0 + height

    series = panel.get("series", [])
    all_x = []
    all_y = []
    prepared = []
    for index, item in enumerate(series):
        points = _series_points(item["x"], item["y"], item.get("style", "line"))
        prepared.append((item, points, item.get("color", COLORS[index % len(COLORS)])))
        all_x.extend(point[0] for point in points)
        all_y.extend(point[1] for point in points)

    xmin, xmax = _expanded_range(all_x)
    ymin, ymax = _expanded_range(all_y)

    def map_point(point):
        px = x0 + (point[0] - xmin) / (xmax - xmin) * width
        py = y1 - (point[1] - ymin) / (ymax - ymin) * height
        return px, py

    parts = [f'<clipPath id="{clip_id}"><rect x="{x0}" y="{y0}" width="{width}" height="{height}"/></clipPath>']
    tick_count = 5
    for tick in range(tick_count + 1):
        fraction = tick / tick_count
        px = x0 + fraction * width
        py = y1 - fraction * height
        xv = xmin + fraction * (xmax - xmin)
        yv = ymin + fraction * (ymax - ymin)
        parts.append(f'<line x1="{px:.2f}" y1="{y0:.2f}" x2="{px:.2f}" y2="{y1:.2f}" stroke="#d0d0d0" stroke-width="1"/>')
        parts.append(f'<line x1="{x0:.2f}" y1="{py:.2f}" x2="{x1:.2f}" y2="{py:.2f}" stroke="#d0d0d0" stroke-width="1"/>')
        parts.append(_svg_text(px, y1 + 22, _format_tick(xv), size=12))
        parts.append(_svg_text(x0 - 10, py + 4, _format_tick(yv), size=12, anchor="end"))

    parts.append(f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{width:.2f}" height="{height:.2f}" fill="none" stroke="#666666" stroke-width="1.2"/>')
    parts.append(_svg_text((x0 + x1) / 2, box_y + box_height - 14, panel.get("xlabel", ""), size=15))
    parts.append(_svg_text(box_x + 20, (y0 + y1) / 2, panel.get("ylabel", ""), size=15, rotate=-90))
    if panel.get("title"):
        parts.append(_svg_text((x0 + x1) / 2, box_y + 22, panel["title"], size=16, weight="600"))

    for item, points, color in prepared:
        if not points:
            continue
        mapped = [map_point(point) for point in points]
        value = " ".join(f"{x:.2f},{y:.2f}" for x, y in mapped)
        parts.append(
            f'<polyline points="{value}" fill="none" stroke="{color}" '
            f'stroke-width="{item.get("width", 2)}" stroke-linejoin="round" '
            f'stroke-linecap="round" clip-path="url(#{clip_id})"/>'
        )
        last_x, last_y = mapped[-1]
        parts.append(f'<circle cx="{last_x:.2f}" cy="{last_y:.2f}" r="2.8" fill="{color}" clip-path="url(#{clip_id})"/>')

    named = [(item.get("label", ""), color) for item, _points, color in prepared if item.get("label")]
    if len(named) > 1:
        legend_x = x1 - 168
        legend_y = y0 + 14
        legend_height = 22 * len(named) + 10
        parts.append(f'<rect x="{legend_x - 8:.2f}" y="{legend_y - 12:.2f}" width="174" height="{legend_height}" fill="white" fill-opacity="0.88" stroke="#aaaaaa"/>')
        for label, color in named:
            parts.append(f'<line x1="{legend_x:.2f}" y1="{legend_y:.2f}" x2="{legend_x + 28:.2f}" y2="{legend_y:.2f}" stroke="{color}" stroke-width="2.5"/>')
            parts.append(_svg_text(legend_x + 36, legend_y + 4, label, size=12, anchor="start"))
            legend_y += 22

    return parts


def save_svg(filename, panels, *, title="", width=1000, height=700, layout=None):
    """保存 SVG。layout 使用 (x, y, width, height) 的 0~1 归一化坐标。"""
    path = Path(filename)
    if path.suffix.lower() != ".svg":
        path = path.with_suffix(".svg")
    path.parent.mkdir(parents=True, exist_ok=True)

    outer_top = 38 if title else 8
    usable_height = height - outer_top
    if layout is None:
        panel_height = usable_height / max(len(panels), 1)
        boxes = [
            (0, outer_top + index * panel_height, width, panel_height)
            for index in range(len(panels))
        ]
    else:
        boxes = [
            (x * width, outer_top + y * usable_height, w * width, h * usable_height)
            for x, y, w, h in layout
        ]

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    if title:
        parts.append(_svg_text(width / 2, 26, title, size=19, weight="600"))

    for index, (panel, box) in enumerate(zip(panels, boxes)):
        parts.extend(_draw_panel(panel, box, f"plot-clip-{index}"))
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")
    return path.resolve()


def show_file(path):
    webbrowser.open(Path(path).resolve().as_uri())

