"""Asset agent — generates Play Store release content from git history using Claude."""

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any

import anthropic

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 2048

_SYSTEM_PROMPT = (
    "You are a mobile app product writer. "
    "Return ONLY valid JSON — no markdown, no code fences, no explanation. "
    "All character limits are hard limits; truncate content to fit."
)

_LIMITS = {
    "release_notes": 500,
    "short_description": 80,
    "full_description": 4000,
    "whats_new": 500,
}


def _git_output(args: list, cwd: str) -> str:
    result = subprocess.run(["git", "-C", cwd] + args, capture_output=True, text=True, timeout=30)
    return result.stdout


def _enforce_limits(assets: dict) -> dict:
    for key, limit in _LIMITS.items():
        if key in assets and isinstance(assets[key], str):
            assets[key] = assets[key][:limit]
    return assets


def run_asset_agent(run_context: dict, bug_report: dict) -> dict:
    """
    Generate Play Store release notes and descriptions from git history.

    run_context keys:
      run_id, project_path
    Returns AssetPackage:
      {run_id, release_notes, short_description, full_description, whats_new, screenshots, error}
    """
    run_id = run_context["run_id"]
    project_path = run_context["project_path"]

    result: dict[str, Any] = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "release_notes": "",
        "short_description": "",
        "full_description": "",
        "whats_new": "",
        "screenshots": [s.get("path", "") for s in bug_report.get("screenshots", [])],
        "error": None,
    }

    git_log = _git_output(["log", "--oneline", "-20"], project_path)
    git_diff = _git_output(["diff", "HEAD~1", "HEAD"], project_path)[:8000]

    fixes_summary = ""
    if bug_report.get("bugs"):
        fixes_summary = "\n".join(
            f"- Fixed: {b['description'][:100]}"
            for b in bug_report["bugs"]
            if b.get("description")
        )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    "Generate Google Play Store release content from the following context.\n\n"
                    f"Recent git commits:\n{git_log}\n\n"
                    f"Code changes (diff):\n{git_diff}\n\n"
                    f"Bugs fixed in this release:\n{fixes_summary or 'None reported'}\n\n"
                    "Return JSON with these exact keys:\n"
                    "{\n"
                    f'  "release_notes": "plain text, max {_LIMITS["release_notes"]} chars",\n'
                    f'  "short_description": "one sentence, max {_LIMITS["short_description"]} chars",\n'
                    f'  "full_description": "markdown ok, max {_LIMITS["full_description"]} chars",\n'
                    f'  "whats_new": "bullet list of changes, max {_LIMITS["whats_new"]} chars"\n'
                    "}"
                ),
            }
        ],
    )

    raw = response.content[0].text.strip()
    try:
        assets = json.loads(raw)
        assets = _enforce_limits(assets)
        result.update(assets)
    except json.JSONDecodeError:
        result["error"] = f"Claude returned non-JSON: {raw[:200]}"

    return result


if __name__ == "__main__":
    import sys
    bug_report_path = sys.argv[1] if len(sys.argv) > 1 else "bug_report.json"
    with open(bug_report_path) as f:
        report = json.load(f)

    ctx = {
        "run_id": report.get("run_id", str(uuid.uuid4())[:8]),
        "project_path": os.environ.get("FLUTTER_PROJECT_PATH", "."),
    }
    assets = run_asset_agent(ctx, report)
    print(json.dumps(assets, indent=2))
