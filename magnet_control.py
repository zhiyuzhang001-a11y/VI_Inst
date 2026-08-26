import serial
import time
import numpy as np

from app_config import serial_port
from live_plot_process import LivePlotProcess


class Magnet:
    def __init__(self, port=None):
        port = port or serial_port("magnet")
        self.ser = serial.Serial(
            port=port,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_ODD,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        )
        time.sleep(0.2)

    def close(self):
        self.ser.close()

    def clear(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    def write(self, cmd):
        self.clear()
        print(f">>> {cmd}")
        self.ser.write((cmd + "\r\n").encode())
        self.ser.flush()
        time.sleep(0.03)

    def query(self, cmd):
        self.write(cmd)
        resp = self.ser.readline().decode(errors="ignore").strip()
        print(f"<<< {resp}")
        return resp

    def get_field(self):
        return float(self.query("FIELD?"))

    def get_mode(self):
        return self.query("MODE?")

    def set_field_direct(self, H):
        self.write(f"FIELD {H}")

    # ===============================
    # 稳定版：到一个点后等待稳定
    # ===============================
    def set_field(self, target, step=100, delay=0.3,
                  tol=0.5, stable_count_need=3, timeout=120):

        current = self.get_field()
        print(f"\n当前磁场: {current:.2f} → 目标: {target:.2f}")

        if step <= 0:
            raise ValueError("step 必须大于 0")

        if target > current:
            path = np.arange(current, target, step)
        else:
            path = np.arange(current, target, -step)

        path = list(path) + [target]

        for H in path:
            print(f"设定 -> {H:.2f} Gs")
            self.set_field_direct(H)
            time.sleep(delay)

        self._wait_stable_internal(
            target=target,
            tol=tol,
            stable_count_need=stable_count_need,
            delay=delay,
            timeout=timeout
        )

    # ===============================
    # 快速版：只设场，不等待稳定
    # ===============================
    def set_field_fast(self, target, step=100, delay=0.02):

        current = self.get_field()
        print(f"\n快速扫场: {current:.2f} → {target:.2f}")

        if step <= 0:
            raise ValueError("step 必须大于 0")

        if target > current:
            path = np.arange(current, target, step)
        else:
            path = np.arange(current, target, -step)

        path = list(path) + [target]

        for H in path:
            print(f"设定 -> {H:.2f} Gs")
            self.set_field_direct(H)
            time.sleep(delay)

    # ===============================
    # 等待稳定
    # ===============================
    def _wait_stable_internal(self, target, tol=0.5,
                              stable_count_need=3, delay=0.3,
                              timeout=120):
        t0 = time.time()
        stable_count = 0

        while True:
            H = self.get_field()
            diff = abs(H - target)

            print(f"H={H:.2f}, Δ={diff:.2f}")

            if diff < tol:
                stable_count += 1
            else:
                stable_count = 0

            if stable_count >= stable_count_need:
                print("✅ 稳定完成")
                return True

            if time.time() - t0 > timeout:
                print("⚠️ 等待超时")
                return False

            time.sleep(delay)

    # ===============================
    # 扫磁场
    # ===============================
    def sweep_field(
        self,
        H_start,
        H_stop,
        H_step,
        *,
        mode="single",
        step=100,
        delay=0.02,
        tol=1,
        stable_count_need=1,
        timeout=120,
        average_count=1,
        average_delay=0,
        return_to_zero=True,
        live_plot=True,
        fast=True,
    ):

        if H_step == 0:
            raise ValueError("H_step 不能为 0")

        if tol is None:
            tol = max(0.2, abs(H_step) * 0.1)

        if H_start < H_stop and H_step < 0:
            raise ValueError("当 H_start < H_stop 时，H_step 应为正")
        if H_start > H_stop and H_step > 0:
            raise ValueError("当 H_start > H_stop 时，H_step 应为负")

        forward = np.arange(H_start, H_stop + H_step, H_step)

        if mode == "single":
            H_values = forward
        elif mode == "roundtrip":
            backward = np.arange(H_stop - H_step, H_start - H_step, -H_step)
            H_values = np.concatenate([forward, backward])
        else:
            raise ValueError("mode 只能是 'single' 或 'roundtrip'")

        data = []

        plotter = None
        if live_plot:
            plotter = LivePlotProcess(
                "Step index",
                "Field (Gs)",
                "Magnetic field sweep",
                max_points=1000,
                refresh_s=0.2,
                series=["Target Field", "Real Field"],
            )
            plotter.start()

        print("\n===== 开始扫磁场 =====")
        print(f"mode = {mode}, fast = {fast}, tol = {tol}")

        for idx, H in enumerate(H_values, start=1):

            print(f"\n[{idx}/{len(H_values)}] 目标磁场: {H:.2f} Gs")

            if fast and idx != 1:
                self.set_field_fast(
                    target=float(H),
                    step=step,
                    delay=delay,
                )
            else:
                self.set_field(
                    target=float(H),
                    step=step,
                    delay=delay,
                    tol=tol,
                    stable_count_need=stable_count_need,
                    timeout=timeout,
                )

            vals = []
            for _ in range(average_count):
                vals.append(self.get_field())
                time.sleep(average_delay)

            H_real = sum(vals) / len(vals)

            print(f"实际磁场: {H_real:.3f} Gs")

            data.append((float(H), float(H_real)))

            if live_plot:
                plotter.add(idx, H, H_real)

        if return_to_zero:
            print("\n===== 扫场结束，返回 0 Gs =====")

            if fast:
                self.set_field_fast(
                    target=0.0,
                    step=step,
                    delay=delay,
                )
            else:
                self.set_field(
                    target=0.0,
                    step=step,
                    delay=delay,
                    tol=tol,
                    stable_count_need=stable_count_need,
                    timeout=timeout,
                )
        else:
            print("\n===== 扫场结束，不返回 0 Gs =====")

        try:
            input("\n按 Enter 退出...")
        finally:
            if plotter is not None:
                plotter.close()
        return data


# ===============================
# 直接运行本文件测试
# ===============================
"""
if __name__ == "__main__":

    mag = Magnet()

    try:
        if mag.get_mode() != "FIELD":
            raise RuntimeError("请先切到 FIELD 模式")

        data = mag.sweep_field(
            H_start=-10,
            H_stop=10,
            H_step=0.5,
            tol=0.3,
            mode="roundtrip",
            return_to_zero=True,
            live_plot=True,

            fast=False,          # True = 快速扫，不等稳定
            step=100,
            delay=0.03,
            stable_count_need=1,
            average_count=1,
            average_delay=0,
        )

        print(data)

    finally:
        mag.close()
"""
