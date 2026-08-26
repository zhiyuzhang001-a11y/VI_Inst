"""Windows-friendly launcher. Each measurement still runs in its own process."""

from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox


PROJECT_DIR = Path(__file__).resolve().parent
CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0

PROGRAMS = [
    ("Environment check", "check_environment.py", [], False),
    ("Live plot simulation", "keithley_iv.py", ["--simulate"], False),
    ("Keithley 6221 + 2182 monitor", "keithley_iv.py", [], True),
    ("Hall: 6221 + 2182 + magnet", "Hall_plot.py", [], True),
    ("Hall: Keithley 2400 + magnet", "2400_Hall_plot.py", [], True),
    ("SMR angle scan", "SMR_plot.py", [], True),
    ("PDEL monitor", "switch_plot.py", [], True),
    ("PDEL sequence", "sequence_pdel_monitor.py", [], True),
    ("PDEL sweep pulse", "keithley_6221_pdel.py", [], True),
]


def launch(script, args, hazardous):
    if hazardous:
        accepted = messagebox.askyesno(
            "Measurement confirmation",
            "Confirm wiring, sample current/compliance, GPIB addresses, COM ports, "
            "and instrument output state before continuing.\n\nStart measurement?",
        )
        if not accepted:
            return

    subprocess.Popen(
        [sys.executable, str(PROJECT_DIR / script), *args],
        cwd=PROJECT_DIR,
        creationflags=CREATE_NEW_CONSOLE,
    )


def edit_config():
    config = PROJECT_DIR / "config.local.toml"
    if not config.exists():
        config.write_text((PROJECT_DIR / "config.toml").read_text(encoding="utf-8"), encoding="utf-8")
    if sys.platform == "win32":
        subprocess.Popen(["notepad.exe", str(config)])
    else:
        messagebox.showinfo("Configuration", str(config))


def main():
    root = tk.Tk()
    root.title("VI_Inst launcher")
    root.geometry("520x560")
    root.minsize(460, 480)

    tk.Label(root, text="VI_Inst", font=("Segoe UI", 18, "bold")).pack(pady=(18, 4))
    tk.Label(
        root,
        text="Run the environment check first. Measurements open in a separate console.",
        font=("Segoe UI", 10),
        wraplength=460,
    ).pack(pady=(0, 14))

    frame = tk.Frame(root)
    frame.pack(fill="both", expand=True, padx=28)
    for label, script, args, hazardous in PROGRAMS:
        tk.Button(
            frame,
            text=label,
            command=lambda s=script, a=args, h=hazardous: launch(s, a, h),
            font=("Segoe UI", 10),
            height=1,
        ).pack(fill="x", pady=3)

    tk.Button(root, text="Edit local configuration", command=edit_config).pack(pady=12)
    tk.Label(
        root,
        text="Data is saved outside the program folder by default.",
        font=("Segoe UI", 9),
        fg="#555555",
    ).pack(pady=(0, 14))
    root.mainloop()


if __name__ == "__main__":
    main()

