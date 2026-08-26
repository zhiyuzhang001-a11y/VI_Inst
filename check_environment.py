"""安全的环境检查：不打开仪器、不改变输出状态。"""

import importlib
import platform
import struct
import sys

from app_config import output_root, serial_port, visa_resource


def check_import(module, display_name=None):
    name = display_name or module
    try:
        imported = importlib.import_module(module)
        version = getattr(imported, "__version__", "available")
        print(f"[OK] {name}: {version}")
        return imported
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        return None


def main():
    print("VI_Inst environment check")
    print(f"Python: {platform.python_version()} ({struct.calcsize('P') * 8}-bit)")
    print(f"OS: {platform.platform()}")
    print(f"Data directory: {output_root()}")
    print()

    failures = 0
    if sys.version_info < (3, 11):
        print("[FAIL] Python 3.11 or newer is required")
        failures += 1

    numpy = check_import("numpy", "NumPy")
    pyvisa = check_import("pyvisa", "PyVISA")
    serial = check_import("serial", "pySerial")
    tkinter = check_import("tkinter", "Tkinter (live plots)")
    failures += sum(item is None for item in (numpy, pyvisa, serial, tkinter))

    if tkinter is not None:
        try:
            patchlevel = tkinter.Tcl().eval("info patchlevel")
            print(f"[OK] Tcl/Tk runtime: {patchlevel}")
        except Exception as exc:
            print(f"[FAIL] Tcl/Tk runtime: {exc}")
            failures += 1

    print("\nConfigured instruments:")
    for name in ("keithley_6221", "keithley_2182a", "keithley_2400"):
        print(f"  {name}: {visa_resource(name)}")
    print(f"  magnet: {serial_port('magnet')}")
    print(f"  rotator: {serial_port('rotator')}")

    if pyvisa is not None:
        try:
            manager = pyvisa.ResourceManager()
            resources = manager.list_resources()
            print(f"\n[OK] VISA backend: {manager.visalib}")
            print("Visible VISA resources:")
            if resources:
                for resource in resources:
                    print(f"  {resource}")
            else:
                print("  (none; connect instruments and check NI MAX/Keysight Connection Expert)")
            manager.close()
        except Exception as exc:
            print(f"\n[FAIL] VISA backend: {exc}")
            print("Install NI-VISA or Keysight IO Libraries with matching 64-bit support.")
            failures += 1

    if serial is not None:
        try:
            from serial.tools import list_ports

            ports = list(list_ports.comports())
            print("\nVisible serial ports:")
            if ports:
                for port in ports:
                    print(f"  {port.device}: {port.description}")
            else:
                print("  (none)")
        except Exception as exc:
            print(f"[WARN] Could not list serial ports: {exc}")

    print()
    if failures:
        print(f"Environment check completed with {failures} required failure(s).")
        return 1
    print("Environment check passed. Instrument addresses still require manual confirmation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
