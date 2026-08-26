from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_config import data_path
from static_plot import save_svg, show_file

# =========================
# 参数
# =========================
N1 = 5000   # sine 部分点数
N2 = 5000   # square 部分点数

# =========================
# 第一段：sine
# =========================
t1 = np.linspace(0, 1, N1)

wave1 = np.sin(2 * np.pi * 5 * t1)

# =========================
# 第二段：square
# =========================
t2 = np.linspace(0, 1, N2)

wave2 = np.sign(np.sin(2 * np.pi * 5 * t2))

# =========================
# 拼接 waveform
# =========================
wave = np.concatenate([wave1, wave2])

# 时间轴
t = np.linspace(0, 2, len(wave))

csv_path = data_path("waveform/sine_square.csv")
np.savetxt(csv_path, wave, delimiter=",")

figure_path = save_svg(
    data_path("waveform/sine_square.svg"),
    [
        {
            "title": "Sine and square waveform",
            "xlabel": "Time (s)",
            "ylabel": "Amplitude",
            "series": [{"x": t, "y": wave, "label": "Waveform"}],
        }
    ],
    width=900,
    height=620,
)
print("saved:", csv_path)
print("figure:", figure_path)
show_file(figure_path)
