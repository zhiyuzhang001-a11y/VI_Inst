import time
import csv
from datetime import datetime
import numpy as np

from app_config import data_path, serial_port, visa_resource
from magnet_control import Magnet
from keithley_iv import Keithley6221, Keithley2182A
from live_plot_process import LivePlotProcess


def main():

    # =========================
    # 基本参数
    # =========================
    COM_MAGNET = serial_port("magnet")

    ADDR_6221 = visa_resource("keithley_6221")
    ADDR_2182 = visa_resource("keithley_2182a")

    current_a = 200e-6          # 100 uA
    nplc = 1                  # 正式测量建议 0.5 或 1

    save_file = data_path("hall/Hall_40um_-1V.csv")

    # =========================
    # 扫场参数
    # =========================
    H_start = 30
    H_stop = -30
    H_step = -1 #1 可能是最小值了

    mode = "roundtrip"
    field_tol = 0.2

    # 磁场速度/稳定参数
    fast = False
    magnet_step = 100
    magnet_delay = 0.03
    stable_count_need = 1

    # =========================
    # 初始化
    # =========================
    mag = None
    src = None
    nvm = None
    f = None
    plotter = None

    try:
        mag = Magnet(COM_MAGNET)
        src = Keithley6221(ADDR_6221, auto_config=False)
        nvm = Keithley2182A(ADDR_2182, auto_config=True)

        print(src.idn())
        print(nvm.idn())

        if mag.get_mode() != "FIELD":
            raise RuntimeError("请先切到 FIELD 模式")

        # 6221 输出固定电流
        src.setup_dc_current(current_a=current_a)

        # 2182A 设置电压测量
        nvm.setup_voltage(nplc=nplc)

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
            "V_V",
            "R_Ohm",
        ])

        # =========================
        # 实时画图
        # =========================
        plotter = LivePlotProcess(
            "Magnetic field (Gs)", r"$R_{xy}$ ($\Omega$)", "Hall sweep"
        )
        plotter.start()

        t0 = time.time()

        print("\n===== 开始扫场测 Hall =====")

        # =========================
        # 主循环
        # =========================
        for idx, h_target in enumerate(fields, start=1):

            print(f"\n[{idx}/{len(fields)}] 目标磁场: {h_target:.3f} Gs")

            # 第一个点建议稳定，后面按参数执行
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

            # 读实际磁场
            h_real = mag.get_field()

            # 读电压
            v_meas = nvm.read_voltage()

            if abs(current_a) < 1e-15:
                raise ValueError("current_a 不能为 0")

            r_meas = v_meas / current_a

            t_now = time.time() - t0
            time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            writer.writerow([
                idx,
                time_str,
                t_now,
                h_target,
                h_real,
                current_a,
                v_meas,
                r_meas,
            ])
            f.flush()

            print(
                f"H_real = {h_real: .3f} Gs, "
                f"V = {v_meas: .9e} V, "
                f"R= {r_meas: .6e} Ohm"
            )

            # 实时画图
            plotter.add(h_real, r_meas)

        print("\n===== 扫场完成 =====")

    except KeyboardInterrupt:
        print("\n手动停止测量")

    finally:

        if f is not None:
            f.close()

        if src is not None:
            src.output_off()
            src.close()

        if nvm is not None:
            nvm.close()

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
