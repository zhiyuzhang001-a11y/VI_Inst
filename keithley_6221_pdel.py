import time
import csv
import pyvisa
import numpy as np

from app_config import data_path, visa_resource
from static_plot import save_svg, show_file


class Keithley6221PDEL:
    """
    Keithley 6221 PDEL sweep pulse 控制类。

    连接方式：
    电脑 --GPIB--> 6221
    6221 --RS232/Trigger Link--> 2182A

    读取的是 6221 PDEL buffer 中的 pulse 高电平电压。
    """

    def __init__(self, resource=None, timeout_ms=30000):
        resource = resource or visa_resource("keithley_6221")
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource)
        self.inst.write_termination = "\n"
        self.inst.read_termination = "\n"
        self.inst.timeout = timeout_ms

    # ======================
    # Basic communication
    # ======================
    def write(self, cmd, delay=0.05):
        print("6221 SEND:", cmd)
        self.inst.write(cmd)
        time.sleep(delay)

    def query(self, cmd, delay=0.05):
        print("6221 QUERY:", cmd)
        ans = self.inst.query(cmd).strip()
        print("6221 RECV:", ans[:500] + (" ..." if len(ans) > 500 else ""))
        time.sleep(delay)
        return ans

    def idn(self):
        return self.query("*IDN?")

    def check_error(self):
        while True:
            err = self.query("SYST:ERR?")
            if err.startswith("0"):
                break
            raise RuntimeError(f"6221 error: {err}")

    def reset(self):
        self.write("*RST", delay=1.0)
        self.check_error()

    def stop(self):
        """
        温和停止输出。
        不主动 PDEL:SWE OFF，避免有时影响下一次 PDEL/Trigger Link 握手。
        """
        for cmd in ["OUTP OFF", "*CLS"]:
            try:
                self.write(cmd, delay=0.2)
            except Exception:
                pass

    def close(self):
        try:
            self.inst.close()
        except Exception:
            pass

        try:
            self.rm.close()
        except Exception:
            pass

    # ======================
    # Configure PDEL sweep
    # ======================
    def configure_sweep_pulse(
        self,
        start_a=1e-3,
        stop_a=10e-3,
        step_a=1e-3,
        pulse_width_s=100e-6,
        low_current_a=100e-6,
        delay_s=0.5,
        sdel_s=60e-6,
        lme=1,
        compliance_v=30,
    ):
        """
        配置 6221 PDEL sweep pulse。

        start_a       : pulse 高电平起始电流, A
        stop_a        : pulse 高电平终止电流, A
        step_a        : pulse 高电平步进, A
        pulse_width_s : pulse 宽度, s
        low_current_a : pulse 间隔低电平电流, A
        delay_s       : 每个 pulse 点之间的等待时间, s
        sdel_s        : PDEL:SDEL, 通常先用 60 us
        lme           : PDEL:LME, 常用 1
        compliance_v  : PDEL:COMP, 常用 30
        """

        self.write(f"SOUR:CURR:COMP {compliance_v}")
        self.write("PDEL:SWE ON")

        # Buffer data format: voltage, timestamp, source current
        self.write("FORM:ELEM READ,TST,SOUR")

        # Sweep high level
        self.write("SWE:SPAC LIN")
        self.write(f"CURR:START {start_a}")
        self.write(f"CURR:STOP {stop_a}")
        self.write(f"CURR:STEP {step_a}")
        self.write(f"DEL {delay_s}")
        self.write("SWE:RANG BEST")

        # Pulse parameters
        self.write(f"PDEL:WIDT {pulse_width_s}")
        self.write(f"PDEL:SDEL {sdel_s}")
        self.write(f"PDEL:LOW {low_current_a}")
        self.write(f"PDEL:LME {lme}")

        self.check_error()

    def arm(self, wait_s=3.0):
        self.write("PDEL:ARM")
        time.sleep(wait_s)
        self.check_error()

    def start(self):
        self.write("INIT:IMM")

    # ======================
    # Data read and parse
    # ======================
    @staticmethod
    def calc_n_points(start_a, stop_a, step_a):
        return int(round((stop_a - start_a) / step_a)) + 1

    @staticmethod
    def parse_trace_data(data_str):
        """
        解析 FORM:ELEM READ,TST,SOUR 后的返回：
        V1,t1,I1,V2,t2,I2,...
        """
        vals = np.array([
            float(x)
            for x in data_str.replace("\n", ",").split(",")
            if x.strip()
        ])

        if len(vals) % 3 != 0:
            print(f"警告：返回数据长度 {len(vals)} 不是 3 的整数倍，可能格式不是 READ,TST,SOUR")
            vals = vals[:len(vals) // 3 * 3]

        arr = vals.reshape(-1, 3)

        voltage_v = arr[:, 0]
        time_s = arr[:, 1]
        current_a = arr[:, 2]

        return time_s, voltage_v, current_a

    def read_trace_data(self, n_points, start_index=0):
        data_str = self.query(f"TRAC:DATA:SEL? {start_index},{n_points}")
        return self.parse_trace_data(data_str)

    # ======================
    # Save and plot
    # ======================
    @staticmethod
    def save_csv(filename, time_s, voltage_v, current_a):
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "time_s",
                "voltage_V",
                "current_A",
                "current_mA",
                "voltage_mV",
            ])

            for t, v, i in zip(time_s, voltage_v, current_a):
                writer.writerow([t, v, i, i * 1e3, v * 1e3])

    @staticmethod
    def plot_result(
        time_s,
        voltage_v,
        current_a,
        delay_s,
        pulse_width_s,
        low_current_a,
        fig_file=None,
        show_plot=True,
    ):
        t_plot = []
        i_plot = []

        for k, I in enumerate(current_a):
            t0p = k * delay_s

            # pulse rise
            t_plot.extend([t0p, t0p])
            i_plot.extend([low_current_a, I])

            # pulse width
            t_plot.extend([t0p, t0p + pulse_width_s])
            i_plot.extend([I, I])

            # back to low level
            t_plot.extend([t0p + pulse_width_s, (k + 1) * delay_s])
            i_plot.extend([low_current_a, low_current_a])

        figure_path = data_path(fig_file or "pdel/pdel_sweep_pulse.svg")
        figure_path = save_svg(
            figure_path,
            [
                {
                    "title": "Pulse IV",
                    "xlabel": "Pulse current (mA)",
                    "ylabel": "Voltage (mV)",
                    "series": [
                        {
                            "x": np.asarray(current_a) * 1e3,
                            "y": np.asarray(voltage_v) * 1e3,
                            "label": "Pulse IV",
                        }
                    ],
                },
                {
                    "title": "Theoretical pulse sequence",
                    "xlabel": "Time (s)",
                    "ylabel": "Current (mA)",
                    "series": [
                        {
                            "x": t_plot,
                            "y": np.asarray(i_plot) * 1e3,
                            "label": "Current",
                        }
                    ],
                },
            ],
            title="Keithley 6221 PDEL sweep",
            width=900,
            height=900,
        )
        print("图像已保存：", figure_path)
        if show_plot:
            show_file(figure_path)
        return figure_path

    # ======================
    # One-shot run
    # ======================
    def run_sweep_pulse(
        self,
        start_a=1e-3,
        stop_a=10e-3,
        step_a=1e-3,
        pulse_width_s=100e-6,
        low_current_a=100e-6,
        delay_s=0.5,
        save_file="pdel_sweep_pulse.csv",
        fig_file=None,
        reset=True,
        plot=True,
        show_plot=True,
        lme=1,
        compliance_v=30,
    ):
        save_file = data_path(save_file)
        if fig_file is not None:
            fig_file = data_path(fig_file)

        if reset:
            self.reset()

        self.configure_sweep_pulse(
            start_a=start_a,
            stop_a=stop_a,
            step_a=step_a,
            pulse_width_s=pulse_width_s,
            low_current_a=low_current_a,
            delay_s=delay_s,
            lme=lme,
            compliance_v=compliance_v,
        )

        self.arm()
        self.start()

        n_points = self.calc_n_points(start_a, stop_a, step_a)
        wait_s = n_points * delay_s + 0.5

        print(f"等待 sweep pulse 完成，约 {wait_s:.1f} s ...")
        time.sleep(wait_s)

        self.check_error()

        time_s, voltage_v, current_a = self.read_trace_data(n_points)

        print("读取到数据点数：", len(voltage_v))

        self.save_csv(save_file, time_s, voltage_v, current_a)
        print("数据已保存：", save_file)

        if plot:
            self.plot_result(
                time_s,
                voltage_v,
                current_a,
                delay_s=delay_s,
                pulse_width_s=pulse_width_s,
                low_current_a=low_current_a,
                fig_file=fig_file,
                show_plot=show_plot,
            )

        return time_s, voltage_v, current_a


if __name__ == "__main__":
    src = Keithley6221PDEL(visa_resource("keithley_6221"))

    try:
        print(src.idn())

        src.run_sweep_pulse(
            start_a=2e-3,
            stop_a=-2e-3,
            step_a=-0.2e-3, #注意正负
            pulse_width_s=100e-6,
            low_current_a=100e-6,
            delay_s=0.5,
            save_file="pdel_sweep_pulse.csv",
            fig_file="pdel/pdel_sweep_pulse.svg",
            reset=True,
            plot=True,
            show_plot=True,
            lme=1,
            compliance_v=30,
        )

    finally:
        src.close()
