from magnet_control import Magnet


TARGET_FIELD_GS = 500


def main():
    expected = f"SET {TARGET_FIELD_GS}"
    answer = input(
        f"即将设定磁场为 {TARGET_FIELD_GS} Gs。\n"
        "请确认接线、样品和仪器面板状态后，"
        f"输入 {expected} 继续："
    ).strip()
    if answer != expected:
        print("已取消，未连接仪器。")
        return

    mag = Magnet()
    try:
        if mag.get_mode() != "FIELD":
            raise RuntimeError("请先在面板切换到 FIELD 模式")
        mag.set_field(TARGET_FIELD_GS, tol=0.5)
    finally:
        mag.close()


if __name__ == "__main__":
    main()
