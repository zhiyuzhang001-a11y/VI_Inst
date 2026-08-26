import time
import csv
import math
import os
import sys
import pyvisa

from app_config import data_path, visa_resource
from live_plot_process import LivePlotProcess


class Keithley6221:
    def __init__(self, resource_name, auto_config=False, timeout_ms=5000):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource_name)
        self.inst.timeout = timeout_ms
        self.inst.write_termination = "\n"
        self.inst.read_termination = "\n"
        self.auto_config = auto_config

    def idn(self):
        return self.inst.query("*IDN?").strip()

    def setup_dc_current(self, current_a=1e-4, compliance_v=10):

        if self.auto_config:
            self.inst.write("SOUR:FUNC CURR")
            self.inst.write("SOUR:CURR:RANG:AUTO ON")
            self.inst.write(f"SOUR:CURR:LEV {current_a}")
            self.inst.write(f"SOUR:CURR:COMP {compliance_v}")
            self.inst.write("OUTP ON")
            time.sleep(0.5)
        else:
            self.set_current(current_a)
            self.output_on()

    def set_current(self, current_a):
        self.inst.write(f"SOUR:CURR:LEV {current_a}")
        time.sleep(0.1)

    def output_on(self):
        self.inst.write("OUTP ON")
        time.sleep(0.1)

    def output_off(self):
        self.inst.write("OUTP OFF")
        time.sleep(0.1)

    def close(self):
        try:
            self.inst.close()
        finally:
            self.rm.close()


class Keithley2182A:
    def __init__(self, resource_name, auto_config=False, timeout_ms=5000):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource_name)
        self.inst.timeout = timeout_ms
        self.inst.write_termination = "\n"
        self.inst.read_termination = "\n"
        self.auto_config = auto_config

    def idn(self):
        return self.inst.query("*IDN?").strip()

    def setup_voltage(self, nplc=0.1):
        if self.auto_config:
            self.inst.write(":SENS:FUNC 'VOLT'")
            self.inst.write(":SENS:VOLT:CHAN1:RANG:AUTO ON")
            self.inst.write(f":SENS:VOLT:NPLC {nplc}")
            self.inst.write(":INIT:CONT ON")
            time.sleep(0.3)

    def read_voltage(self):
        return float(self.inst.query("FETCh?").strip())

    def close(self):
        try:
            self.inst.close()
        finally:
            self.rm.close()


class Simulated6221:
    """无仪器时用于测试记录和实时绘图。"""

    def idn(self):
        return "SIMULATED,6221"

    def setup_dc_current(self, current_a=1e-4, compliance_v=10):
        pass

    def output_off(self):
        pass

    def close(self):
        pass


class Simulated2182A:
    """生成带少量波动的模拟电压，并提高采样速度以压测绘图。"""

    def __init__(self):
        self.start_time = time.monotonic()

    def idn(self):
        return "SIMULATED,2182A"

    def setup_voltage(self, nplc=0.1):
        pass

    def read_voltage(self):
        elapsed = time.monotonic() - self.start_time
        time.sleep(0.01)
        return 2e-3 + 2e-4 * math.sin(2 * math.pi * elapsed / 5)

    def close(self):
        pass


# =====================================================
# 直接运行本文件时：测试 6221 + 2182A 电压随时间记录
# 被其他文件 import 时，下面不会执行
# =====================================================
if __name__ == "__main__":

    SIMULATE = "--simulate" in sys.argv

    ADDR_6221 = visa_resource("keithley_6221")
    ADDR_2182 = visa_resource("keithley_2182a")

    CURRENT_A = 200e-6          # 100 uA
    NPLC = 1
    SAVE_FILE = data_path("iv/keithley_iv.csv")

    # CSV 仍保存每一个测量点；实时图只显示最近的数据并限制刷新频率，
    # 避免长时间测量时 GUI 绘图命令堆积而出现“配额不足”。
    PLOT_MAX_POINTS = 1000
    PLOT_REFRESH_INTERVAL_S = 0.25

    src = None
    nvm = None
    f = None
    plotter = None

    try:
        if SIMULATE:
            src = Simulated6221()
            nvm = Simulated2182A()
            save_file = data_path("diagnostics/plot_stress_test.csv")
            print("模拟模式：不连接仪器，按 Ctrl+C 停止测试")
        else:
            src = Keithley6221(ADDR_6221, auto_config=False)
            nvm = Keithley2182A(ADDR_2182, auto_config=True)
            save_file = SAVE_FILE

        print(src.idn())
        print(nvm.idn())

        # 6221 输出固定电流
        src.setup_dc_current(current_a=CURRENT_A)

        # 2182A 连续测电压
        nvm.setup_voltage(nplc=NPLC)

        # CSV 实时保存
        save_dir = os.path.dirname(save_file)
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
        f = open(save_file, "w", newline="")
        writer = csv.writer(f)
        writer.writerow(["time_s", "current_A", "voltage_V", "resistance_Ohm"])

        # 实时图在独立进程中运行，上下显示 V-t 和 R-t。
        plotter = LivePlotProcess(
            title="Voltage and Resistance vs Time",
            max_points=PLOT_MAX_POINTS,
            refresh_s=PLOT_REFRESH_INTERVAL_S,
            panels=[
                {
                    "title": "Voltage vs Time",
                    "xlabel": "Time (s)",
                    "ylabel": "Voltage (V)",
                    "series": ["Voltage"],
                },
                {
                    "title": "Resistance vs Time",
                    "xlabel": "Time (s)",
                    "ylabel": "Resistance (Ohm)",
                    "series": ["Resistance"],
                },
            ],
        )
        plotter.start()

        t0 = time.monotonic()
        last_file_flush = time.monotonic()
        last_console_print = 0.0

        print("\n开始记录电压，Ctrl+C 停止...\n")

        while True:
            t = time.monotonic() - t0
            v = nvm.read_voltage()
            r = v / CURRENT_A

            writer.writerow([t, CURRENT_A, v, r])
            now = time.monotonic()
            if now - last_file_flush >= 1.0:
                f.flush()
                last_file_flush = now

            # 只把用于显示的 t、V、R 发送给绘图进程。
            plotter.add(t, v, r)

            if t - last_console_print >= 0.5:
                print(
                    f"t = {t:8.3f} s, V = {v: .9e} V, "
                    f"R = {r: .6f} Ohm"
                )
                last_console_print = t

    except KeyboardInterrupt:
        print("\n手动停止记录")

    finally:
        if f is not None:
            f.close()

        if src is not None:
            src.output_off()
            src.close()

        if nvm is not None:
            nvm.close()

        try:
            input("按 Enter 退出...")
        finally:
            if plotter is not None:
                plotter.close()
