"""Build a data-free Windows source package from an explicit allowlist."""

from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "dist" / "VI_Inst-Windows.zip"

FILES = (
    ".gitignore",
    "2400_Hall_plot.py",
    "Hall_plot.py",
    "README.md",
    "SMR_plot.py",
    "address.py",
    "app_config.py",
    "build_release.py",
    "check_environment.py",
    "config.toml",
    "install_local_copy.bat",
    "keithley_2400.py",
    "keithley_6221_pdel.py",
    "keithley_iv.py",
    "launcher.py",
    "live_plot_process.py",
    "magnet_control.py",
    "requirements.txt",
    "run_windows.bat",
    "sequence_pdel_monitor.py",
    "set_H.py",
    "setup_windows.bat",
    "static_plot.py",
    "sweep_angle.py",
    "switch_plot.py",
    "waveform/sinesqr_1.py",
)

FORBIDDEN_SUFFIXES = {".csv", ".png", ".jpg", ".jpeg", ".wav", ".pyc"}
FORBIDDEN_NAMES = {"config.local.toml"}


def validate(files):
    missing = [name for name in files if not (ROOT / name).is_file()]
    forbidden = [
        name
        for name in files
        if Path(name).suffix.lower() in FORBIDDEN_SUFFIXES
        or Path(name).name in FORBIDDEN_NAMES
    ]
    if missing:
        raise FileNotFoundError(f"Missing release files: {missing}")
    if forbidden:
        raise RuntimeError(f"Forbidden files in release: {forbidden}")


def main():
    validate(FILES)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / name, arcname=f"VI_Inst/{name}")

    with zipfile.ZipFile(OUTPUT) as archive:
        members = archive.namelist()
        if len(members) != len(FILES):
            raise RuntimeError("Release audit failed: unexpected archive member count")
        validate([name.removeprefix("VI_Inst/") for name in members])

    print(f"Created data-free release: {OUTPUT}")
    print(f"Files included: {len(FILES)}")


if __name__ == "__main__":
    main()
