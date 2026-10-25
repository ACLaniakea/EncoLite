"""Measure only the Enco Lite process, never other running applications."""
from pathlib import Path
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/".build-deps"))
import psutil


def verify():
    output = ROOT/"verification"
    output.mkdir(exist_ok=True)
    command = [sys.executable, str(ROOT/"main.py")]
    report = output/"source-smoke.json"
    if report.exists():
        report.unlink()
    completed = subprocess.run([*command, "--smoke-test", "--test-report", str(report)], timeout=40)
    if completed.returncode or not report.exists():
        raise RuntimeError(f"Source smoke failed: exit={completed.returncode}")
    if json.loads(report.read_text("utf-8"))["result"] != "PASS":
        raise RuntimeError(report.read_text("utf-8"))

    result = {"platform": "Windows x64", "renderer": "winit-software",
              "scope": "Enco Lite production client; connected OPPO Enco X3",
              "modes": {},
              "runtime": "Existing Windows CPython; standalone exe blocked by Application Control",
              "baseline_comparison": "Not measured; no reduction percentage claimed"}
    for mode, arguments in (("main", []), ("quick", ["--quick"]), ("tray", ["--tray-only"])):
        result["modes"][mode] = measure(command, arguments)
    result["existing_instance_reused"] = verify_reuse(command)
    (output/"memory-windows.json").write_text(json.dumps(result,indent=2),"utf-8")
    print(json.dumps(result,indent=2),flush=True)


def measure(command, arguments):
    launch = time.perf_counter()
    child = subprocess.Popen([*command, *arguments])
    process = psutil.Process(child.pid)
    try:
        time.sleep(3)
        if child.poll() is not None:
            raise RuntimeError("App unexpectedly exited")
        # Includes native tray, the real Bluetooth session, and production timers.
        samples = []
        for _ in range(3):
            memory = process.memory_info()
            samples.append({"working_set_mib": round(memory.rss/1048576,2),
                            "private_mib": round(memory.private/1048576,2),
                            "cpu_percent": process.cpu_percent(interval=1)})
        result = {"samples": samples,
                  "working_set_average_mib": round(sum(s["working_set_mib"] for s in samples)/len(samples),2),
                  "private_average_mib": round(sum(s["private_mib"] for s in samples)/len(samples),2),
                  "cpu_average_percent": round(sum(s["cpu_percent"] for s in samples)/len(samples),2),
                  "elapsed_seconds": round(time.perf_counter()-launch,2)}
        return result
    finally:
        if child.poll() is None:
            shutdown(child)


def shutdown(child):
    import ctypes
    u=ctypes.WinDLL('user32',use_last_error=True)
    u.FindWindowW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p];u.FindWindowW.restype=ctypes.c_void_p
    u.PostMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
    hwnd=u.FindWindowW('EncoLiteTray','Enco Lite tray')
    if hwnd:u.PostMessageW(hwnd,0x8002,3,0)
    try:child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        psutil.Process(child.pid).terminate();child.wait(timeout=5)


def verify_reuse(command):
    child = subprocess.Popen([*command, "--tray-only"])
    try:
        time.sleep(2)
        second = subprocess.run([*command, "--quick"], timeout=10)
        third = subprocess.run([*command], timeout=10)
        assert second.returncode == 0 and third.returncode == 0
        assert child.poll() is None
        return True
    finally:
        if child.poll() is None:
            shutdown(child)


if __name__ == "__main__":
    verify()
