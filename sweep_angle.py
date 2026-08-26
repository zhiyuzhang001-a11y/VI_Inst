import serial
import time
from typing import Optional, List

from app_config import serial_port


class RotatorBE1102:
    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: int = 9600,
        address: int = 1,      # 注意：说明书例子是地址 1
        mode: int = 0x01,      # 单步模式
        func_byte: int = 0x31, # 脉冲数控制
        accel: int = 200,
        decel: int = 200,
        timeout: float = 0.5,
    ):
        self.port = port or serial_port("rotator")
        self.baudrate = baudrate
        self.address = address
        self.mode = mode
        self.func_byte = func_byte
        self.accel = accel
        self.decel = decel
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None

    def open(self):
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
            write_timeout=self.timeout,
        )
        time.sleep(0.2)

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @staticmethod
    def _u16(value: int) -> List[int]:
        if not (0 <= value <= 0xFFFF):
            raise ValueError(f"16-bit value out of range: {value}")
        return [(value >> 8) & 0xFF, value & 0xFF]

    @staticmethod
    def _u24(value: int) -> List[int]:
        if not (0 <= value <= 0xFFFFFF):
            raise ValueError(f"24-bit value out of range: {value}")
        return [(value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF]

    @staticmethod
    def _crc_xor(data: List[int]) -> int:
        crc = 0
        for b in data:
            crc ^= b
        return crc & 0xFF

    @staticmethod
    def angle_to_pulses(angle_deg: float) -> int:
        """
        已标定：
        1 degree = 800 pulses
        """
        return int(round(abs(angle_deg) * 800))

    def build_move_cmd(
        self,
        freq_base: int,
        pulse_count: int,
        direction: int,
        count_byte: int = 0x03,
    ) -> bytes:
        f_hi, f_lo = self._u16(freq_base)
        p_hi, p_mid, p_lo = self._u24(pulse_count)
        a_hi, a_lo = self._u16(self.accel)
        d_hi, d_lo = self._u16(self.decel)

        data15 = [
            0xBA,
            self.mode,
            f_hi,
            f_lo,
            self.address,
            count_byte,
            direction,
            self.func_byte,
            p_hi,
            p_mid,
            p_lo,
            a_hi,
            a_lo,
            d_hi,
            d_lo,
        ]

        crc = self._crc_xor(data15)
        return bytes(data15 + [crc, 0xFE])

    def send_cmd(self, cmd: bytes, read_n: int = 2, delay_s: float = 0.05) -> bytes:
        if self.ser is None or not self.ser.is_open:
            raise RuntimeError("Serial port is not open")

        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        self.ser.write(cmd)
        self.ser.flush()
        time.sleep(delay_s)

        if read_n > 0:
            return self.ser.read(read_n)

        return b""

    def move_pulses(
        self,
        pulses: int,
        forward: bool = True,
        freq_base: int = 63000,
        verbose: bool = True,
        max_retry: int = 5,
        retry_wait_s: float = 0.5,
    ) -> bytes:
        direction = 0x01 if forward else 0x02

        cmd = self.build_move_cmd(
            freq_base=freq_base,
            pulse_count=pulses,
            direction=direction,
        )

        last_reply = b""

        for i in range(max_retry):
            if verbose:
                print("MOVE SEND:", cmd.hex(" ").upper())

            reply = self.send_cmd(cmd, read_n=2)
            last_reply = reply

            if verbose:
                print("MOVE RECV:", reply.hex(" ").upper() if reply else "<NO REPLY>")

            if len(reply) >= 1 and reply[0] == 0xB1:
                return reply

            if len(reply) >= 1 and reply[0] == 0xB5:
                print("收到 B5：当前步未进入运行状态，尝试 STOP + 清状态后重试一次...")

                # 1) 发停止命令，强制释放实时控制状态
                try:
                    self.stop(freq_base=freq_base)
                except Exception as e:
                    print("STOP 清状态失败:", e)

                time.sleep(1.0)

                # 2) 查询几次，把状态/残留返回读掉
                for _ in range(5):
                    self.query_running_status(verbose=True)
                    time.sleep(0.3)

                # 3) 再重发当前这一步
                print("重新发送当前步命令...")
                reply = self.send_cmd(cmd, read_n=2)

                if verbose:
                    print("MOVE RETRY RECV:", reply.hex(" ").upper() if reply else "<NO REPLY>")

                if len(reply) >= 1 and reply[0] == 0xB1:
                    return reply

                raise RuntimeError(
                    "控制器连续返回 B5：STOP 清状态后仍未执行。程序停止，避免角度累计错误。"
                )

            if len(reply) >= 1 and reply[0] == 0xB2:
                raise RuntimeError("控制器返回 B2：数据存储错误，命令未执行")

            time.sleep(retry_wait_s)

        raise RuntimeError(
            f"运动命令重试 {max_retry} 次仍未执行，最后返回: "
            f"{last_reply.hex(' ').upper() if last_reply else '<NO REPLY>'}"
        )

    def move_relative(
        self,
        delta_angle_deg: float,
        freq_base: int = 63000,
        verbose: bool = True,
    ) -> bytes:
        pulses = self.angle_to_pulses(delta_angle_deg)
        forward = delta_angle_deg >= 0

        if verbose:
            print(
                f"Move relative: {delta_angle_deg:+.3f} deg "
                f"-> {pulses} pulses, "
                f"{'forward' if forward else 'reverse'}"
            )

        return self.move_pulses(
            pulses=pulses,
            forward=forward,
            freq_base=freq_base,
            verbose=verbose,
        )

    def stop(self, freq_base: int = 63000) -> bytes:
        cmd = self.build_move_cmd(
            freq_base=freq_base,
            pulse_count=0,
            direction=0x03,
        )

        print("STOP SEND:", cmd.hex(" ").upper())
        reply = self.send_cmd(cmd, read_n=2)
        print("STOP RECV:", reply.hex(" ").upper() if reply else "<NO REPLY>")
        return reply

    def build_query_cmd(self, query_type: int) -> bytes:
        """
        查询指令：
        B6 [addr] [query_type] [crc] FE

        query_type:
            0: 当前运行状态，返回 [addr] [status]
               status = 0 停止
               status = 1 运行中
            1: 剩余脉冲高位
            2: 剩余脉冲中位
            3: 剩余脉冲低位
            4: 剩余往返次数
            5: 输入开关状态
            6: 电位器输入电压
            8: 硬件唯一编号
            251: 固件版本
        """
        data = [0xB6, self.address, query_type]
        crc = self._crc_xor(data)
        return bytes(data + [crc, 0xFE])

    def query_running_status(self, verbose: bool = False) -> Optional[int]:
        """
        返回：
            0x00: 停止
            0x01: 运行中
            None: 没有读到有效状态
        """
        cmd = self.build_query_cmd(0x00)

        if verbose:
            print("STATUS SEND:", cmd.hex(" ").upper())

        reply = self.send_cmd(cmd, read_n=2, delay_s=0.05)

        if verbose:
            print("STATUS RECV:", reply.hex(" ").upper() if reply else "<NO REPLY>")

        if len(reply) < 2:
            return None
        #兼容B0 addr:位置控制完成
        if reply[0] == 0xB0:
            return 0x00
        
        addr = reply[0]
        status = reply[1]

        if addr != self.address:
            if verbose:
                print(f"地址不匹配: expected {self.address}, got {addr}")
            return None

        if status in (0x00, 0x01):
            return status

        return None

    def wait_until_stopped(
        self,
        timeout_s: float = 30.0,
        poll_s: float = 0.2,
        settle_s: float = 0.3,
        verbose: bool = True,
    ) -> None:
        """
        发完运动命令后调用。
        不断查询当前运行状态，直到 status=0。
        """
        t0 = time.time()

        while True:
            status = self.query_running_status(verbose=verbose)

            if status == 0x00:
                if verbose:
                    print("电机状态: 停止")
                time.sleep(settle_s)
                return

            elif status == 0x01:
                if verbose:
                    print("电机状态: 运行中")

            else:
                if verbose:
                    print("电机状态: 无效/无回复")

            if time.time() - t0 > timeout_s:
                raise TimeoutError("等待电机停止超时")

            time.sleep(poll_s)


def frange(start: float, stop: float, step: float):
    if step == 0:
        raise ValueError("step cannot be 0")

    x = start
    eps = abs(step) * 1e-9

    if step > 0:
        while x <= stop + eps:
            yield round(x, 10)
            x += step
    else:
        while x >= stop - eps:
            yield round(x, 10)
            x += step


def sweep_angle(
    rot: RotatorBE1102,
    start_angle: float,
    stop_angle: float,
    step_angle: float,
    dwell_s: float = 1.0,
    freq_base: int = 63000,
    wait_timeout_s: float = 30.0,
    poll_s: float = 0.2,
    settle_s: float = 0.3,
):
    if step_angle == 0:
        raise ValueError("step_angle cannot be 0")

    if start_angle < stop_angle and step_angle < 0:
        raise ValueError("start < stop 时，step_angle 必须为正")

    if start_angle > stop_angle and step_angle > 0:
        raise ValueError("start > stop 时，step_angle 必须为负")

    angle_points = list(frange(start_angle, stop_angle, step_angle))

    if len(angle_points) < 2:
        raise ValueError("扫描点太少")

    print("Sweep points:")
    print(angle_points)
    print(f"默认当前物理位置 = {angle_points[0]:.3f} deg")
    print("-" * 60)

    software_current = angle_points[0]

    for target in angle_points[1:]:
        delta = target - software_current

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

        rot.wait_until_stopped(
            timeout_s=wait_timeout_s,
            poll_s=poll_s,
            settle_s=settle_s,
            verbose=True,
        )

        software_current = target

        print(f"到达目标点（软件记录）: {software_current:.3f} deg")
        print(f"停留/测量: {dwell_s} s")
        time.sleep(dwell_s)

        print("-" * 60)

    print("扫描完成。")


if __name__ == "__main__":
    PORT = serial_port("rotator")

    ADDRESS = 0

    START_ANGLE = 0
    STOP_ANGLE = -20
    STEP_ANGLE = -1

    FREQ_BASE = 30000

    ACCEL = 100
    DECEL = 100

    DWELL_S = 0

    with RotatorBE1102(
        port=PORT,
        address=ADDRESS,
        accel=ACCEL,
        decel=DECEL,
    ) as rot:
        sweep_angle(
            rot=rot,
            start_angle=START_ANGLE,
            stop_angle=STOP_ANGLE,
            step_angle=STEP_ANGLE,
            dwell_s=DWELL_S,
            freq_base=FREQ_BASE,
            wait_timeout_s=10.0,
            poll_s=0.2,
            settle_s=0.3,
        )
