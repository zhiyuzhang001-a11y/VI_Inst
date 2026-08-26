"""
仪器连接说明（测量前请确认 6221 输出为 OFF）：

1. Keithley 6221 用于向样品施加脉冲电流：
   - 6221 OUTPUT HI -> 样品电流端 I+
   - 6221 OUTPUT LO -> 样品电流端 I-

2. Keithley 2182A 用于监测样品电压，建议使用四线/Kelvin 接法：
   - 2182A CH1 INPUT HI -> 样品电压端 V+
   - 2182A CH1 INPUT LO -> 样品电压端 V-
   - V+ 应靠近 I+ 一侧，V- 应靠近 I- 一侧；如果电压符号相反，
     请检查样品端定义，不要在仪器输出开启时改线。

3. 通信连接：
   - 6221 和 2182A 分别通过 GPIB 连接电脑。
   - 6221 与 2182A 之间还需按仪器 PDEL 接法连接 RS-232/Trigger Link，
     用于 PDEL 的同步与控制；本程序同时通过 2182A 的 GPIB 读取监测电压。

接线前还应核对样品允许电流、6221 compliance voltage，以及 2182A 的
最大输入和共模电压限制；仪器机壳地、OUTPUT LO 和 INPUT LO 不应在未确认
接地关系时随意短接。

本脚本受测试时序限制，不进行实时画图；采集结束并关闭仪器连接后，才一次性
显示全部测量点。
"""

import time
import csv
import pyvisa
import numpy as np

from app_config import data_path, visa_resource
from keithley_6221_pdel import Keithley6221PDEL
from static_plot import save_svg, show_file


ADDR_6221 = visa_resource("keithley_6221")
ADDR_2182_MONITOR = visa_resource("keithley_2182a")


class Keithley2182Monitor:
    def __init__(self, resource, timeout_ms=10000):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource)
        self.inst.write_termination = "\n"
        self.inst.read_termination = "\n"
        self.inst.timeout = timeout_ms

    def write(self, cmd, delay=0.03):
        print("2182 SEND:", cmd)
        self.inst.write(cmd)
        time.sleep(delay)

    def query(self, cmd, delay=0.0):
        ans = self.inst.query(cmd).strip()
        time.sleep(delay)
        return ans

    def idn(self):
        return self.query("*IDN?")

    def setup_voltage(self, nplc=1, auto_range=True, auto_zero=False):
        self.write("SENS:FUNC 'VOLT'")
        self.write("SENS:VOLT:RANG:AUTO ON" if auto_range else "SENS:VOLT:RANG 0.1")
        self.write(f"SENS:VOLT:NPLC {nplc}")
        self.write("SYST:AZER ON" if auto_zero else "SYST:AZER OFF")
        self.write("INIT:CONT ON")
        print("2182 ERR:", self.query("SYST:ERR?"))

    def read_voltage(self):
        return float(self.query("FETCH?"))

    def close(self):
        try:
            self.inst.close()
        except Exception:
            pass
        try:
            self.rm.close()
        except Exception:
            pass


def save_point(writer, idx, t_read, v, eq_current, low_current_a, read_mode):
    resistance = v / low_current_a
    writer.writerow([
        idx,
        t_read,
        v,
        eq_current,
        eq_current * 1e3,
        resistance,
        read_mode,
    ])
    return resistance


def plot_monitor_result(
    t_list,
    v_list,
    eq_current_list,
    start_a,
    stop_a,
    step_a,
    pulse_width_s,
    low_current_a,
    delay_s,
    fig_file="pdel_2182_monitor.svg",
    right_y="resistance",
    show_plot=True,
):
    t_arr = np.array(t_list)
    v_arr = np.array(v_list)
    x_current_a = np.array(eq_current_list)

    current_list = np.arange(start_a, stop_a + step_a / 2, step_a)

    t_plot, i_plot = [], []
    for k, I in enumerate(current_list):
        t0p = k * delay_s

        t_plot.extend([t0p, t0p])
        i_plot.extend([low_current_a, I])

        t_plot.extend([t0p, t0p + pulse_width_s])
        i_plot.extend([I, I])

        t_plot.extend([t0p + pulse_width_s, (k + 1) * delay_s])
        i_plot.extend([low_current_a, low_current_a])

    if right_y == "resistance":
        y = v_arr / low_current_a
        ylabel = "Resistance at low current (Ω)"
    else:
        y = v_arr * 1e3
        ylabel = "Monitor voltage (mV)"

    figure_path = save_svg(
        data_path(fig_file or "pdel/pdel_2182_monitor.svg"),
        [
            {
                "title": "Monitor voltage",
                "xlabel": "Time (s)",
                "ylabel": "Monitor voltage (mV)",
                "series": [{"x": t_arr, "y": v_arr * 1e3, "label": "Voltage"}],
            },
            {
                "title": "Pulse sequence",
                "xlabel": "Time (s)",
                "ylabel": "Current (mA)",
                "series": [{"x": t_plot, "y": np.asarray(i_plot) * 1e3, "label": "Current"}],
            },
            {
                "title": "Switch curve",
                "xlabel": "Equivalent pulse current (mA)",
                "ylabel": ylabel,
                "series": [{"x": x_current_a * 1e3, "y": y, "label": ylabel}],
            },
        ],
        title="PDEL monitor result",
        width=1280,
        height=720,
        layout=[(0.0, 0.0, 0.5, 0.5), (0.0, 0.5, 0.5, 0.5), (0.5, 0.0, 0.5, 1.0)],
    )
    print("图像已保存：", figure_path)
    if show_plot:
        show_file(figure_path)
    return figure_path


def run_pdel_and_monitor_2182(
    start_a=1e-3,
    stop_a=10e-3,
    step_a=0.1e-3,
    pulse_width_s=100e-6,
    low_current_a=100e-6,
    delay_s=0.5,
    nplc=1,
    read_mode="middle",
    save_file="pdel_2182_monitor.csv",
    fig_file="pdel_2182_monitor.svg",
    samples_per_gap=5, #取点数量，越多越接近连续
    guard_after_pulse_s=0.05,
    guard_before_next_s=0.05,
    right_y="resistance",
    show_plot=True,
    compliance_v=30,
):
    save_file = data_path(save_file)
    if fig_file:
        fig_file = data_path(fig_file)

    src = Keithley6221PDEL(ADDR_6221)
    nvm = Keithley2182Monitor(ADDR_2182_MONITOR)

    t_list, v_list, eq_current_list = [], [], []

    try:
        print("6221:", src.idn())
        print("2182 monitor:", nvm.idn())

        nvm.setup_voltage(nplc=nplc, auto_range=True, auto_zero=False)

        src.reset()
        time.sleep(1)

        src.configure_sweep_pulse(
            start_a=start_a,
            stop_a=stop_a,
            step_a=step_a,
            pulse_width_s=pulse_width_s,
            low_current_a=low_current_a,
            delay_s=delay_s,
            lme=1,
            compliance_v=compliance_v,
        )

        src.arm()

        n_points = src.calc_n_points(start_a, stop_a, step_a)
        total_time_s = n_points * delay_s

        print(f"n_points = {n_points}")
        print(f"预计总时间约 {total_time_s:.2f} s")

        t0 = time.perf_counter()
        src.start()

        with open(save_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "index",
                "time_s",
                "voltage_V",
                "eq_current_A",
                "eq_current_mA",
                "resistance_ohm",
                "read_mode",
            ])

            idx = 0

            if read_mode == "continuous":
                while True:
                    if time.perf_counter() - t0 > total_time_s:
                        break

                    try:
                        v = nvm.read_voltage()
                        t_read = time.perf_counter() - t0

                        gap_pos = t_read / delay_s
                        k = int(np.floor(gap_pos))
                        if k < 0:
                            continue

                        frac = gap_pos - k

                        if k < n_points - 1:
                            I_now = start_a + k * step_a
                            I_next = start_a + (k + 1) * step_a
                            eq_current = I_now + frac * (I_next - I_now)
                        else:
                            eq_current = start_a + (n_points - 1) * step_a

                        t_list.append(t_read)
                        v_list.append(v)
                        eq_current_list.append(eq_current)

                        save_point(writer, idx, t_read, v, eq_current, low_current_a, read_mode)
                        f.flush()

                        print(f"{idx:04d}  t={t_read:.3f} s  V={v:.6e} V  Ieq={eq_current*1e3:.3f} mA")
                        idx += 1

                    except Exception as e:
                        print("2182 READ ERROR:", e)

            elif read_mode == "middle":
                for k in range(n_points):
                    if k < n_points - 1:
                        gap_start = k * delay_s + pulse_width_s + guard_after_pulse_s
                        gap_end = (k + 1) * delay_s - guard_before_next_s
                        I_now = start_a + k * step_a
                        I_next = start_a + (k + 1) * step_a
                    else:
                        gap_start = k * delay_s + pulse_width_s + guard_after_pulse_s
                        gap_end = k * delay_s + delay_s - guard_before_next_s
                        I_now = start_a + k * step_a
                        I_next = I_now

                    if gap_end <= gap_start:
                        continue

                    target_times = np.linspace(gap_start, gap_end, samples_per_gap)

                    for target_t in target_times:
                        while time.perf_counter() - t0 < target_t:
                            time.sleep(0.001)

                        try:
                            v = nvm.read_voltage()
                            t_read = time.perf_counter() - t0

                            frac = (t_read - gap_start) / (gap_end - gap_start)
                            frac = np.clip(frac, 0, 1)

                            eq_current = I_now + frac * (I_next - I_now)

                            t_list.append(t_read)
                            v_list.append(v)
                            eq_current_list.append(eq_current)

                            save_point(writer, idx, t_read, v, eq_current, low_current_a, read_mode)
                            f.flush()

                            print(
                                f"{idx:04d}  gap={k}  "
                                f"target={target_t:.3f} s  actual={t_read:.3f} s  "
                                f"Ieq={eq_current*1e3:.3f} mA  V={v:.6e} V"
                            )
                            idx += 1

                        except Exception as e:
                            print("2182 READ ERROR:", e)

            else:
                raise ValueError("read_mode 只能是 'continuous' 或 'middle'")

        print("数据已保存：", save_file)

    finally:
        try:
            src.close()
        except Exception:
            pass

        try:
            nvm.close()
        except Exception:
            pass

        print("仪器连接已关闭")

    plot_monitor_result(
        t_list,
        v_list,
        eq_current_list,
        start_a=start_a,
        stop_a=stop_a,
        step_a=step_a,
        pulse_width_s=pulse_width_s,
        low_current_a=low_current_a,
        delay_s=delay_s,
        fig_file=fig_file,
        right_y=right_y,
        show_plot=show_plot,
    )

    return t_list, v_list, eq_current_list


if __name__ == "__main__":
    run_pdel_and_monitor_2182(
        start_a=10e-3,
        stop_a=-10e-3,
        step_a=-0.5e-3, #注意正负号
        pulse_width_s=100e-6,
        low_current_a=100e-6,
        delay_s=0.5,
        nplc=1,
        read_mode="middle", #middle or continuous
        samples_per_gap=5,
        save_file="pdel_2182_monitor.csv",
        fig_file="pdel/pdel_2182_monitor.svg",
        right_y="resistance",
        show_plot=True,
        compliance_v=30
    )
