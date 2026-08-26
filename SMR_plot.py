import time
import csv
from collections import deque

import numpy as np
from app_config import data_path, serial_port, visa_resource
from keithley_iv import Keithley6221, Keithley2182A
from sweep_angle import RotatorBE1102, frange
from live_plot_process import LivePlotProcess


def smr_angle_scan(
    rot,
    nvm,
    current_a,
    start_angle,
    stop_angle,
    step_angle,
    save_file,
    freq_base=30000,
    dwell_s=2.0,
    wait_timeout_s=20.0,
    poll_s=0.2,
    settle_s=0.5,
    live_plot=True,
):
    angles = list(frange(start_angle, stop_angle, step_angle))

    if len(angles) < 2:
        raise ValueError("角度点太少")

    print("角度点：")
    print(angles)
    print(f"默认当前物理角度 = {angles[0]} deg")

    t0 = time.time()
    software_current = angles[0]

    angle_data = deque(maxlen=5000)
    r_data = deque(maxlen=5000)

    if live_plot:
        plotter = LivePlotProcess(
            "Angle (deg)", "Resistance (Ohm)", "SMR angle scan"
        )
        plotter.start()
    else:
        plotter = None

    with open(save_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "time_s",
            "angle_deg",
            "current_A",
            "voltage_V",
            "resistance_Ohm",
        ])
        f.flush()

        def record_one_point(angle):
            time.sleep(dwell_s)

            v = nvm.read_voltage()
            r = v / current_a

            row = [
                time.time() - t0,
                angle,
                current_a,
                v,
                r
            ]

            writer.writerow(row)
            f.flush()

            angle_data.append(angle)
            r_data.append(r)

            print(
                f"Angle = {angle:8.3f} deg, "
                f"V = {v: .9e} V, "
                f"R = {r: .9e} Ohm"
            )

            if live_plot:
                plotter.add(angle, r)

        print("\n记录起点数据...")
        record_one_point(software_current)

        for step_index, target in enumerate(angles[1:], start=1):
            delta = target - software_current

            print("-" * 60)
            print(
                f"Current = {software_current:.3f} deg, "
                f"Target = {target:.3f} deg, "
                f"Delta = {delta:+.3f} deg"
            )

            rot.move_relative(
                delta_angle_deg=delta,
                freq_base=freq_base,
                verbose=True,
            )
            try:
                rot.wait_until_stopped(
                    timeout_s=wait_timeout_s,
                    poll_s=poll_s,
                    settle_s=settle_s,
                    verbose=False,
                )
            except TimeoutError:
                print("警告：状态查询超时，等待两秒后继续...")
                time.sleep(2)
            software_current = target

            record_one_point(software_current)
            
            if step_index % 20 == 0:
                print("主动清状态...")
                rot.stop(freq_base=freq_base)
                time.sleep(0.5)

                for _ in range(3):
                    rot.query_running_status(verbose=False)
                    time.sleep(0.2)
    print("\nSMR 角度扫描完成。")
    return plotter


if __name__ == "__main__":
    # =========================
    # 仪器地址
    # =========================
    ADDR_6221 = visa_resource("keithley_6221")
    ADDR_2182 = visa_resource("keithley_2182a")

    ROTATOR_PORT = serial_port("rotator")
    ROTATOR_ADDRESS = 0

    # =========================
    # 电流参数
    # =========================
    CURRENT_A = 1e-4
    COMPLIANCE_V = 10

    # =========================
    # 2182 参数
    # =========================
    NPLC = 1

    # =========================
    # 角度扫描参数
    # =========================
    START_ANGLE = 0
    STOP_ANGLE = -360
    STEP_ANGLE = -3 #step_1 需要约25min，误差2度。step_3,约15min，误差约2度。

    FREQ_BASE = 30000#这里设置较低频率比较稳定，扫角度不会报错
    ACCEL = 100
    DECEL = 100

    # =========================
    # 每个角度点测量
    # =========================
    DWELL_S = 0.2

    # =========================
    # 保存文件
    # =========================
    SAVE_FILE = data_path("smr/SMR_angle_scan.csv")

    src = None
    nvm = None
    plotter = None

    try:
        src = Keithley6221(ADDR_6221, auto_config=False)
        nvm = Keithley2182A(ADDR_2182, auto_config=True)

        print("6221:", src.idn())
        print("2182:", nvm.idn())

        print("\n配置 6221 恒流输出...")
        src.setup_dc_current(
            current_a=CURRENT_A,
            compliance_v=COMPLIANCE_V,
        )

        print("配置 2182 连续电压测量...")
        nvm.setup_voltage(nplc=NPLC)

        with RotatorBE1102(
            port=ROTATOR_PORT,
            address=ROTATOR_ADDRESS,
            accel=ACCEL,
            decel=DECEL,
        ) as rot:

            plotter = smr_angle_scan(
                rot=rot,
                nvm=nvm,
                current_a=CURRENT_A,
                start_angle=START_ANGLE,
                stop_angle=STOP_ANGLE,
                step_angle=STEP_ANGLE,
                save_file=SAVE_FILE,
                freq_base=FREQ_BASE,
                dwell_s=DWELL_S,
                wait_timeout_s=10.0,#电机最长等待10s，避免死循环
                poll_s=0.2, #每隔0.2s查询一次电机状态
                settle_s=1,#电机停止后等待0.5s再测量，确保机械振动衰减
                live_plot=True,
            )
    except KeyboardInterrupt:
        print("\n用户手动停止。")

    finally:
        print("\n关闭设备...")

        if src is not None:
            try:
                src.output_off()
                src.close()
            except Exception as e:
                print("关闭 6221 出错:", e)

        if nvm is not None:
            try:
                nvm.close()
            except Exception as e:
                print("关闭 2182 出错:", e)

        try:
            input("\n按 Enter 键退出...")
        finally:
            if plotter is not None:
                plotter.close()

        print("程序结束。")
