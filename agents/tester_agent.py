"""Tester agent — navigates the running app via ADB, uses Claude vision to find bugs."""

import base64
import dataclasses
import json
import os
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import anthropic

from platforms.android_adapter import AndroidAdapter
from platforms.base_adapter import CrashLog, EmulatorSession, ScreenshotResult

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 1024
_SCREENSHOT_WINDOW = 3  # keep last N screenshots in conversation to limit context size

_SYSTEM_PROMPT = """You are a mobile QA agent inspecting a Flutter Android app via screenshots.
On each turn you receive a screenshot of the current app screen.

You MUST respond with ONLY valid JSON matching this exact schema — no other text:
{
  "screen_name": "string — identify the screen shown",
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "type": "crash|overflow|navigation|visual|logic",
      "description": "string — describe the bug clearly",
      "file_hint": "string — best guess at the Dart source file, e.g. lib/main.dart",
      "fix_hint": "string — how to fix it"
    }
  ],
  "next_tap": {"x": 540, "y": 960},
  "done": false
}

Rules:
- Set done=true when you have explored all screens or cannot make further progress.
- Set next_tap to {"x": 0, "y": 0} when done=true.
- Look for: null pointer crashes, layout overflows (yellow/black stripes), broken navigation, missing widgets, wrong text.
- Do not include markdown, code fences, or explanation outside the JSON object."""


def _encode_screenshot(path: str) -> str:
    return base64.standard_b64encode(Path(path).read_bytes()).decode()


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_claude_json(content: str) -> Optional[dict]:
    try:
        return json.loads(_strip_fences(content))
    except json.JSONDecodeError:
        return None


def convert_flutter_json_to_junit_xml(flutter_json: dict) -> str:
    """Convert flutter test --reporter json output to JUnit XML for UiPath Test Cloud."""
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite", name="flutter_tests")

    events = flutter_json.get("events", [])
    test_map: dict[int, dict] = {}

    for event in events:
        event_type = event.get("type")
        if event_type == "testStart":
            tid = event["test"]["id"]
            test_map[tid] = {"name": event["test"]["name"], "result": "unknown", "error": ""}
        elif event_type in ("testDone", "error"):
            tid = event.get("testID", event.get("test", {}).get("id"))
            if tid in test_map:
                if event_type == "error":
                    test_map[tid]["result"] = "error"
                    test_map[tid]["error"] = event.get("error", "")
                else:
                    test_map[tid]["result"] = event.get("result", "unknown")

    failures = 0
    errors = 0
    for tid, data in test_map.items():
        tc = ET.SubElement(suite, "testcase", name=data["name"])
        if data["result"] in ("error", "failure"):
            failures += 1
            fail = ET.SubElement(tc, "failure", message=data["error"])
            fail.text = data["error"]
        elif data["result"] == "error":
            errors += 1
            ET.SubElement(tc, "error", message=data["error"]).text = data["error"]

    suite.set("tests", str(len(test_map)))
    suite.set("failures", str(failures))
    suite.set("errors", str(errors))
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def run_tester(run_context: dict) -> dict:
    """
    Navigate the app with Claude vision and return a BugReport dict.

    run_context keys:
      run_id (str), project_path (str), avd_name (str), max_screens (int, default 15)
    """
    run_id = run_context["run_id"]
    project_path = run_context["project_path"]
    avd_name = run_context.get("avd_name", "Pixel_9_Pro")
    max_screens = run_context.get("max_screens", 15)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    adapter = AndroidAdapter()

    bug_report: dict[str, Any] = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app_package": "",
        "total_screens_visited": 0,
        "bugs": [],
        "test_results": {},
        "crash_logs": [],
        "screenshots": [],
        "build_result": run_context.get("build_result", {}),
    }

    # Run flutter tests first
    test_raw = adapter.run_tests(project_path)
    bug_report["test_results"] = {
        "raw": test_raw,
        "junit_xml": convert_flutter_json_to_junit_xml(test_raw),
    }

    apk_path = run_context.get("apk_path", "")
    if not apk_path or not Path(apk_path).exists():
        bug_report["error"] = f"APK not found at {apk_path}"
        return bug_report

    session: Optional[EmulatorSession] = None
    try:
        session = adapter.launch_emulator({"avd_name": avd_name, "headless": True})
        adapter.install_app(session, apk_path)

        # Launch the app
        import subprocess
        subprocess.run(
            [
                os.path.join(
                    os.path.expanduser(os.environ.get("ANDROID_SDK_ROOT", "~/Library/Android/sdk")),
                    "platform-tools", "adb",
                ),
                "-s", session.device_id, "shell", "monkey",
                "-p", run_context.get("package_name", "com.mopot.sample_flutter_app"),
                "-c", "android.intent.category.LAUNCHER", "1",
            ],
            capture_output=True,
        )

        messages: list = []
        screenshot_buffer: list[tuple[str, str]] = []  # (screen_name, path)
        bug_counter = 0
        prev_screen_name = ""
        same_screen_count = 0
        known_crashes_hashes: set[str] = set()

        for screen_num in range(1, max_screens + 1):
            shot: ScreenshotResult = adapter.take_screenshot(session, f"screen_{screen_num:02d}")
            bug_report["screenshots"].append(dataclasses.asdict(shot))

            # Collect any new crash logs
            all_crashes = adapter.get_crash_logs(session)
            for crash in all_crashes:
                key = hash((crash.error_type, crash.stack_trace[:100]))
                if key not in known_crashes_hashes:
                    known_crashes_hashes.add(key)
                    crash_dict = dataclasses.asdict(crash)
                    bug_report["crash_logs"].append(crash_dict)
                    bug_counter += 1
                    bug_report["bugs"].append({
                        "bug_id": f"bug-{bug_counter:03d}",
                        "severity": "critical",
                        "type": "crash",
                        "screen_name": f"screen_{screen_num:02d}",
                        "description": f"{crash.error_type}: {crash.stack_trace[:200]}",
                        "screenshot_path": shot.path,
                        "file_hint": "lib/main.dart",
                        "fix_hint": "Check for null references and unhandled exceptions.",
                        "stack_trace": crash.stack_trace,
                    })

            # Sliding window: keep last _SCREENSHOT_WINDOW images in messages
            screenshot_buffer.append((f"screen_{screen_num:02d}", shot.path))
            if len(screenshot_buffer) > _SCREENSHOT_WINDOW:
                screenshot_buffer.pop(0)

            visited_summary = ", ".join(n for n, _ in screenshot_buffer)

            # Build user message with current screenshot
            user_content: list = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": _encode_screenshot(shot.path),
                    },
                },
                {
                    "type": "text",
                    "text": (
                        f"Screen {screen_num} of max {max_screens}. "
                        f"Screens visited so far: [{visited_summary}]. "
                        "Analyze ALL visible bugs, then choose the best next tap to explore further."
                    ),
                },
            ]

            # Keep messages list to only the last _SCREENSHOT_WINDOW turns + summaries
            if len(messages) > _SCREENSHOT_WINDOW * 2:
                messages = messages[-((_SCREENSHOT_WINDOW * 2)):]

            messages.append({"role": "user", "content": user_content})

            # Call Claude with retry on JSON parse failure
            claude_response = None
            for attempt in range(2):
                response = client.messages.create(
                    model=_MODEL,
                    max_tokens=_MAX_TOKENS,
                    system=_SYSTEM_PROMPT,
                    messages=messages,
                )
                raw_text = response.content[0].text
                parsed = _parse_claude_json(raw_text)
                if parsed:
                    claude_response = parsed
                    messages.append({"role": "assistant", "content": raw_text})
                    break
                # Retry: ask Claude to return valid JSON only
                messages.append({"role": "assistant", "content": raw_text})
                messages.append({
                    "role": "user",
                    "content": "Your previous response was not valid JSON. Return ONLY the JSON object.",
                })

            if not claude_response:
                # Could not get valid JSON — stop gracefully
                break

            # Merge Claude's issues into bug report
            screen_name = claude_response.get("screen_name", f"screen_{screen_num:02d}")
            for issue in claude_response.get("issues", []):
                bug_counter += 1
                bug_report["bugs"].append({
                    "bug_id": f"bug-{bug_counter:03d}",
                    "severity": issue.get("severity", "medium"),
                    "type": issue.get("type", "visual"),
                    "screen_name": screen_name,
                    "description": issue.get("description", ""),
                    "screenshot_path": shot.path,
                    "file_hint": issue.get("file_hint", "lib/main.dart"),
                    "fix_hint": issue.get("fix_hint", ""),
                    "stack_trace": "",
                })

            bug_report["total_screens_visited"] = screen_num

            if claude_response.get("done"):
                break

            # Stall detection
            if screen_name == prev_screen_name:
                same_screen_count += 1
                if same_screen_count >= 2:
                    break
            else:
                same_screen_count = 0
            prev_screen_name = screen_name

            # Execute the tap
            tap = claude_response.get("next_tap", {})
            x, y = tap.get("x", 0), tap.get("y", 0)
            if x or y:
                adapter.tap(session, x, y)

    finally:
        if session:
            adapter.teardown(session)

    return bug_report


if __name__ == "__main__":
    import sys
    ctx = {
        "run_id": str(uuid.uuid4())[:8],
        "project_path": sys.argv[1] if len(sys.argv) > 1 else ".",
        "avd_name": os.environ.get("MOPOT_AVD", "Pixel_9_Pro"),
        "apk_path": sys.argv[2] if len(sys.argv) > 2 else "",
    }
    report = run_tester(ctx)
    print(json.dumps(report, indent=2))
