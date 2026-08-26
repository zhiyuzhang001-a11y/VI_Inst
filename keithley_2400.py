import time
import csv

import pyvisa

from app_config import data_path, visa_resource
from live_plot_process import LivePlotProcess


class Keithley2400:
    def __init__(self, resource_name, timeout_ms=10000):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource_name)

        self.inst.timeout = timeout_ms
        self.inst.write_termination = "\n"
        self.inst.read_termination = "\n"

    def idn(self):
        return self.inst.query("*IDN?").strip()

    def setup_current_source(
        self,
        current_a=100e-6,
        compliance_v=10,
        nplc=1,
        remote_sense=True,
    ):

        self.inst.write("*RST")
        time.sleep(1)

        if remote_sense:
            self.inst.write(":SYST:RSEN ON")
        else:
            self.inst.write(":SYST:RSEN OFF")

        self.inst.write(":SOUR:FUNC CURR")
        self.inst.write(":SOUR:CURR:MODE FIX")
        self.inst.write(f":SOUR:CURR:LEV {current_a}")

        self.inst.write(":SENS:FUNC 'VOLT'")

        # 关闭 auto zero 提高速度
        self.inst.write(":SYST:AZER OFF")

        self.inst.write(f":SENS:VOLT:PROT {compliance_v}")
        self.inst.write(f":SENS:VOLT:NPLC {nplc}")

        # 固定量程（推荐）
        self.inst.write(":SENS:VOLT:RANG:AUTO ON")

        self.inst.write(":FORM:ELEM VOLT")

        self.inst.write(":OUTP ON")

        time.sleep(0.5)

    def read_voltage(self):
        value = self.inst.query(":READ?").strip()
        return float(value)

    def output_off(self):
        self.inst.write(":OUTP OFF")

    def close(self):
        try:
            self.output_off()
        except Exception:
            pass

        self.inst.close()
        self.rm.close()


def main():
    # =========================
    # 参数
    # =========================
    ADDR_2400 = visa_resource("keithley_2400")

    current_a = 100e-6       # 100 uA
    compliance_v = 10        # 电压保护
    nplc = 1                 # 越大越稳，越小越快。可试 0.1, 1, 5
    refresh_s = 0.1          # 读取间隔

    save_file = data_path("hall/Hall_2400_4wire.csv")

    # =========================
    # 连接仪器
    # =========================
    smu = Keithley2400(ADDR_2400)

    print("Instrument:")
    print(smu.idn())

    smu.setup_current_source(
        current_a=current_a,
        compliance_v=compliance_v,
        nplc=nplc,
        remote_sense=True,
    )

    print("2400 已设置为四线 Hall 测量模式")
    print("Ctrl+C 停止记录")

    # =========================
    # 打开 CSV
    # =========================
    f = open(save_file, "w", newline="")
    writer = csv.writer(f)

    writer.writerow([
        "time_s",
        "current_a",
        "voltage_v",
        "resistance_ohm",
    ])

    f.flush()

    # =========================
    # 实时画图
    # =========================
    plotter = LivePlotProcess(
        title="Keithley 2400 Hall monitor",
        max_points=1000,
        refresh_s=0.2,
        panels=[
            {
                "title": "Hall voltage vs Time",
                "xlabel": "Time (s)",
                "ylabel": "Hall voltage Vxy (V)",
                "series": ["Vxy"],
            },
            {
                "title": "Hall resistance vs Time",
                "xlabel": "Time (s)",
                "ylabel": "Rxy (Ohm)",
                "series": ["Rxy"],
            },
        ],
    )
    plotter.start()

    t0 = time.time()

    try:
        while True:
            t = time.time() - t0

            vxy = smu.read_voltage()
            rxy = vxy / current_a

            writer.writerow([
                t,
                current_a,
                vxy,
                rxy,
            ])
            f.flush()

            plotter.add(t, vxy, rxy)

            print(
                f"t = {t:8.2f} s | "
                f"Vxy = {vxy:+.6e} V | "
                f"Rxy = {rxy:+.6f} Ohm"
            )

            time.sleep(refresh_s)

    except KeyboardInterrupt:
        print("\n用户停止记录")

    finally:
        f.close()
        smu.close()

        print(f"数据已保存到: {save_file}")
        try:
            input("按 Enter 退出...")
        finally:
            plotter.close()


if __name__ == "__main__":
    main()
