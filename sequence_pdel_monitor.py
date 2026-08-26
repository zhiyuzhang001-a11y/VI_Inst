import time
import numpy as np

from app_config import data_path
from static_plot import save_svg, show_file
from switch_plot import run_pdel_and_monitor_2182


def make_sweep_sequence(amplitudes_mA):
    sweep_list = []

    for idx, amp_mA in enumerate(amplitudes_mA):
        amp_a = amp_mA * 1e-3

        if idx % 2 == 0:
            sweep_list.append((amp_a, -amp_a))
        else:
            sweep_list.append((-amp_a, amp_a))

    return sweep_list


def main():
    amplitudes_mA = [20, 22, 24, 26, 28, 30]

    sweep_list = make_sweep_sequence(amplitudes_mA)

    step_abs_a = 0.5e-3
    pulse_width_s = 100e-6
    low_current_a = 100e-6
    delay_s = 0.5
    nplc = 1

    all_curves = []

    for idx, (start_a, stop_a) in enumerate(sweep_list, start=1):

        if stop_a > start_a:
            step_a = step_abs_a
        else:
            step_a = -step_abs_a

        print("\n" + "=" * 70)
        print(f"Sweep {idx}: {start_a*1e3:.1f} mA -> {stop_a*1e3:.1f} mA")
        print("=" * 70)

        name = f"sweep_{idx:02d}_{start_a*1e3:.0f}mA_to_{stop_a*1e3:.0f}mA"

        t_list, v_list, eq_current_list = run_pdel_and_monitor_2182(
            start_a=start_a,
            stop_a=stop_a,
            step_a=step_a,
            pulse_width_s=pulse_width_s,
            low_current_a=low_current_a,
            delay_s=delay_s,
            nplc=nplc,
            read_mode="middle",
            save_file=f"pdel/sequence/{name}.csv",
            fig_file=f"pdel/sequence/{name}.svg",
            show_plot=True,   # 每扫完一条，立刻显示一张图
            compliance_v=30,
        )

        resistance = np.array(v_list) / low_current_a

        all_curves.append({
            "label": f"{start_a*1e3:.0f} → {stop_a*1e3:.0f} mA",
            "x": np.array(eq_current_list) * 1e3,
            "y": resistance,
        })

        time.sleep(1)

    figure_path = save_svg(
        data_path("pdel/sequence/all_switch_curves.svg"),
        [
            {
                "title": "All switch curves",
                "xlabel": "Equivalent pulse current (mA)",
                "ylabel": "Resistance at low current (Ω)",
                "series": [
                    {"x": curve["x"], "y": curve["y"], "label": curve["label"]}
                    for curve in all_curves
                ],
            }
        ],
        title="PDEL switch sequence",
        width=1000,
        height=760,
    )
    print("总图已保存：", figure_path)
    show_file(figure_path)


if __name__ == "__main__":
    main()
