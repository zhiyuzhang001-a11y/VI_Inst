import time
import csv
from datetime import datetime

import numpy as np
from app_config import data_path, serial_port, visa_resource
from magnet_control import Magnet
from keithley_2400 import Keithley2400
from live_plot_process import LivePlotProcess


def main():

    # =========================
    # 基本参数
    # =========================
    COM_MAGNET = serial_port("magnet")
    ADDR_2400 = visa_resource("keithley_2400")

    current_a = 1000e-6
    compliance_v = 10
    nplc = 1

    remote_sense = True     # True = 四线 Hall；False = 普通两线
    save_file = data_path("hall/Hall_2400_test.csv")

    # =========================
    # 扫场参数
    # =========================
    H_start = -20
    H_stop = 20
    H_step = 1

    mode = "roundtrip"
    field_tol = 0.2

    fast = False
    magnet_step = 100
    magnet_delay = 0.03
    stable_count_need = 1

    # =========================
    # 初始化
    # =========================
    mag = None
    smu = None
    f = None
    plotter = None

    try:
        mag = Magnet(COM_MAGNET)
        smu = Keithley2400(ADDR_2400)

        print("2400:")
        print(smu.idn())

        if mag.get_mode() != "FIELD":
            raise RuntimeError("请先切到 FIELD 模式")

        # 2400：输出电流，同时测 Sense 端电压
        smu.setup_current_source(
            current_a=current_a,
            compliance_v=compliance_v,
            nplc=nplc,
            remote_sense=remote_sense,
        )

        # =========================
        # 生成磁场序列
        # =========================
        forward = np.arange(H_start, H_stop + H_step, H_step)

        if mode == "single":
            fields = forward
        elif mode == "roundtrip":
            backward = np.arange(H_stop - H_step, H_start - H_step, -H_step)
            fields = np.concatenate([forward, backward])
        else:
            raise ValueError("mode 只能是 single 或 roundtrip")

        # =========================
        # CSV 文件
        # =========================
        f = open(save_file, "w", newline="")
        writer = csv.writer(f)

        writer.writerow([
            "index",
            "time_str",
            "time_s",
            "H_target_Gs",
            "H_real_Gs",
            "I_A",
            "Vxy_V",
            "Rxy_Ohm",
            "remote_sense",
            "nplc",
        ])
        f.flush()

        # =========================
        # 实时画图
        # =========================
        plotter = LivePlotProcess(
            "Magnetic field (Gs)",
            r"$R_{xy}$ ($\Omega$)",
            "Hall sweep by Keithley 2400",
        )
        plotter.start()

        t0 = time.time()

        print("\n===== 开始用 2400 扫场测 Hall =====")
        print(f"remote_sense = {remote_sense}")

        # =========================
        # 主循环
        # =========================
        for idx, h_target in enumerate(fields, start=1):

            print(f"\n[{idx}/{len(fields)}] 目标磁场: {h_target:.3f} Gs")

            if fast and idx != 1:
                mag.set_field_fast(
                    target=float(h_target),
                    step=magnet_step,
                    delay=magnet_delay,
                )
            else:
                mag.set_field(
                    target=float(h_target),
                    step=magnet_step,
                    delay=magnet_delay,
                    tol=field_tol,
                    stable_count_need=stable_count_need,
                    timeout=120,
                )

            h_real = mag.get_field()

            vxy = smu.read_voltage()

            if abs(current_a) < 1e-15:
                raise ValueError("current_a 不能为 0")

            rxy = vxy / current_a

            t_now = time.time() - t0
            time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            writer.writerow([
                idx,
                time_str,
                t_now,
                h_target,
                h_real,
                current_a,
                vxy,
                rxy,
                remote_sense,
                nplc,
            ])
            f.flush()

            print(
                f"H_real = {h_real: .3f} Gs, "
                f"Vxy = {vxy: .9e} V, "
                f"Rxy = {rxy: .6e} Ohm"
            )

            plotter.add(h_real, rxy)

        print("\n===== 扫场完成 =====")

    except KeyboardInterrupt:
        print("\n手动停止测量")

    finally:

        if f is not None:
            f.close()

        if smu is not None:
            smu.close()

        if mag is not None:
            try:
                mag.set_field(
                    target=0.0,
                    step=100,
                    delay=0.03,
                    tol=0.5,
                    stable_count_need=1,
                    timeout=120,
                )
            except Exception as e:
                print("返回 0 Gs 失败：", e)

            mag.close()

        try:
            input("按 Enter 退出...")
        finally:
            if plotter is not None:
                plotter.close()


if __name__ == "__main__":
    main()
