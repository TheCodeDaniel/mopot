"""Android platform adapter — implements MobilePlatformAdapter using ADB and Flutter CLI."""

import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from platforms.base_adapter import (
    BuildResult,
    CrashLog,
    EmulatorSession,
    MobilePlatformAdapter,
    ScreenshotResult,
)

_SDK_ROOT = os.path.expanduser(
    os.environ.get("ANDROID_SDK_ROOT", "~/Library/Android/sdk")
)
_ADB = os.path.join(_SDK_ROOT, "platform-tools", "adb")
_EMULATOR_BIN = os.path.join(_SDK_ROOT, "emulator", "emulator")

_SCREENSHOT_DIR = Path("/tmp/mopot")
_EMULATOR_BOOT_TIMEOUT = 120  # seconds


def _run(cmd: List[str], cwd: Optional[str] = None, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)


class AndroidAdapter(MobilePlatformAdapter):

    def build(self, project_path: str, config: dict) -> BuildResult:
        log_lines: List[str] = []

        for cmd in [
            ["flutter", "clean"],
            ["flutter", "pub", "get"],
            ["flutter", "build", "apk", "--debug"],
        ]:
            result = _run(cmd, cwd=project_path, timeout=600)
            log_lines.append(f"$ {' '.join(cmd)}\n{result.stdout}{result.stderr}")
            if result.returncode != 0:
                return BuildResult(
                    success=False,
                    artifact_path="",
                    build_log="\n".join(log_lines),
                    error=result.stderr or result.stdout,
                )

        apk_path = os.path.join(
            project_path, "build", "app", "outputs", "flutter-apk", "app-debug.apk"
        )
        if not os.path.exists(apk_path):
            return BuildResult(
                success=False,
                artifact_path="",
                build_log="\n".join(log_lines),
                error="APK not found after build succeeded — possible Flutter output path change.",
            )

        return BuildResult(
            success=True,
            artifact_path=apk_path,
            build_log="\n".join(log_lines),
        )

    def launch_emulator(self, device_config: dict) -> EmulatorSession:
        avd_name = device_config.get("avd_name", "Pixel_9_Pro")
        headless = device_config.get("headless", True)

        cmd = [_EMULATOR_BIN, "-avd", avd_name]
        if headless:
            cmd += ["-no-window", "-no-audio", "-no-snapshot"]

        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Wait for emulator to appear in adb devices
        device_id: Optional[str] = None
        deadline = time.time() + _EMULATOR_BOOT_TIMEOUT
        while time.time() < deadline:
            time.sleep(2)
            result = _run([_ADB, "devices"])
            for line in result.stdout.splitlines():
                m = re.match(r"(emulator-\d+)\s+device", line)
                if m:
                    device_id = m.group(1)
                    break
            if device_id:
                break

        if not device_id:
            raise RuntimeError(f"Emulator {avd_name} did not appear in adb devices within {_EMULATOR_BOOT_TIMEOUT}s")

        # Wait for full boot
        while time.time() < deadline:
            result = _run([_ADB, "-s", device_id, "shell", "getprop", "sys.boot_completed"])
            if result.stdout.strip() == "1":
                return EmulatorSession(device_id=device_id, platform="android", is_running=True)
            time.sleep(2)

        raise RuntimeError(f"Emulator {avd_name} booted but sys.boot_completed never became 1")

    def install_app(self, session: EmulatorSession, artifact_path: str) -> bool:
        result = _run([_ADB, "-s", session.device_id, "install", "-r", artifact_path])
        return result.returncode == 0

    def take_screenshot(self, session: EmulatorSession, label: str) -> ScreenshotResult:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = _SCREENSHOT_DIR / session.device_id
        run_dir.mkdir(parents=True, exist_ok=True)
        out_path = str(run_dir / f"{label}_{ts}.png")

        # Binary PNG — must NOT go through a shell redirect (corrupts newlines)
        result = subprocess.run(
            [_ADB, "-s", session.device_id, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0 or not result.stdout:
            raise RuntimeError(f"screencap failed: {result.stderr}")

        Path(out_path).write_bytes(result.stdout)
        return ScreenshotResult(path=out_path, screen_name=label, timestamp=ts)

    def tap(self, session: EmulatorSession, x: int, y: int) -> bool:
        result = _run([_ADB, "-s", session.device_id, "shell", "input", "tap", str(x), str(y)])
        return result.returncode == 0

    def get_crash_logs(self, session: EmulatorSession) -> List[CrashLog]:
        result = _run([
            _ADB, "-s", session.device_id, "logcat",
            "-d", "-s", "AndroidRuntime:E", "Flutter:E", "*:F",
        ])
        crashes: List[CrashLog] = []
        lines = result.stdout.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if "FATAL EXCEPTION" in line or "FlutterError" in line or "E/Flutter" in line:
                # Grab timestamp from logcat prefix e.g. "06-01 12:34:56.789"
                ts_match = re.match(r"(\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)", line)
                timestamp = ts_match.group(1) if ts_match else ts

                error_type = "CrashException"
                if "FlutterError" in line:
                    error_type = "FlutterError"
                elif "FATAL EXCEPTION" in line:
                    error_type = "FatalException"

                # Collect stack trace lines that follow
                stack_lines = [line]
                j = i + 1
                while j < len(lines) and (lines[j].startswith("\tat ") or "at " in lines[j]):
                    stack_lines.append(lines[j])
                    j += 1

                crashes.append(CrashLog(
                    timestamp=timestamp,
                    error_type=error_type,
                    stack_trace="\n".join(stack_lines),
                ))
                i = j
            else:
                i += 1
        return crashes

    def run_tests(self, project_path: str) -> dict:
        result = _run(
            ["flutter", "test", "--reporter", "json"],
            cwd=project_path,
            timeout=300,
        )
        try:
            # flutter test --reporter json outputs one JSON object per line
            events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            return {"events": events, "exit_code": result.returncode, "raw": result.stdout}
        except json.JSONDecodeError:
            return {"events": [], "exit_code": result.returncode, "raw": result.stdout, "stderr": result.stderr}

    def teardown(self, session: EmulatorSession) -> bool:
        result = _run([_ADB, "-s", session.device_id, "emu", "kill"])
        return result.returncode == 0
