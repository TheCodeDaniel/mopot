"""Fixer agent — reads bug report, writes Claude-generated fixes, commits a PR."""

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any, Optional

import anthropic
import requests

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096

_SYSTEM_PROMPT = (
    "You are a Flutter/Dart expert. "
    "When given a file and a bug to fix, return ONLY the complete corrected file content. "
    "No explanation, no markdown code fences, no comments about the fix. "
    "Return the raw Dart source that should replace the file."
)


def _git(args: list, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", cwd] + args, capture_output=True, text=True)


def _fix_file(client: anthropic.Anthropic, project_path: str, bug: dict) -> Optional[str]:
    file_hint = bug.get("file_hint", "lib/main.dart")
    full_path = Path(project_path) / file_hint

    if not full_path.exists():
        return None

    current_content = full_path.read_text(encoding="utf-8")

    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"File: {file_hint}\n\n"
                    f"Current content:\n{current_content}\n\n"
                    f"Bug to fix:\n"
                    f"  Description: {bug.get('description', '')}\n"
                    f"  Fix hint: {bug.get('fix_hint', '')}\n"
                    f"  Severity: {bug.get('severity', 'medium')}"
                ),
            }
        ],
    )

    fixed = response.content[0].text.strip()
    # Safety: skip suspiciously short responses (likely a refusal or error)
    if len(fixed) < 50:
        return None
    return fixed


def _open_github_pr(
    repo: str,
    token: str,
    branch: str,
    base: str,
    title: str,
    body: str,
) -> dict:
    url = f"https://api.github.com/repos/{repo}/pulls"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"title": title, "head": branch, "base": base, "body": body},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def run_fixer(run_context: dict, bug_report: dict) -> dict:
    """
    Fix each reported bug with Claude, commit the changes, and open a GitHub PR.

    run_context keys:
      run_id, project_path, github_repo (owner/repo), github_default_branch
    Returns:
      {run_id, branch_name, pr_url, pr_number, files_fixed, fixes_applied, error}
    """
    run_id = run_context["run_id"]
    project_path = run_context["project_path"]
    github_repo = os.environ.get("GITHUB_REPO", run_context.get("github_repo", ""))
    github_token = os.environ["GITHUB_TOKEN"]
    base_branch = run_context.get("github_default_branch", os.environ.get("GITHUB_DEFAULT_BRANCH", "main"))
    branch_name = f"mopot/fix-{run_id}"

    result: dict[str, Any] = {
        "run_id": run_id,
        "branch_name": branch_name,
        "pr_url": "",
        "pr_number": 0,
        "files_fixed": [],
        "fixes_applied": [],
        "error": None,
    }

    bugs = bug_report.get("bugs", [])
    if not bugs:
        result["error"] = "No bugs in report — nothing to fix."
        return result

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Checkout a new fix branch
    _git(["checkout", "-b", branch_name], project_path)

    files_changed: set[str] = set()

    for bug in bugs:
        file_hint = bug.get("file_hint", "lib/main.dart")
        fixed_content = _fix_file(client, project_path, bug)
        if not fixed_content:
            continue

        full_path = Path(project_path) / file_hint
        full_path.write_text(fixed_content, encoding="utf-8")
        files_changed.add(file_hint)

        result["fixes_applied"].append({
            "bug_id": bug.get("bug_id", ""),
            "file": file_hint,
            "severity": bug.get("severity", ""),
            "description": bug.get("description", ""),
        })

    if not files_changed:
        result["error"] = "Claude could not produce fixes for any reported bug."
        return result

    result["files_fixed"] = list(files_changed)

    # Stage and commit
    _git(["add", "-A"], project_path)
    commit_summary = "\n".join(
        f"- [{f['bug_id']}] {f['description'][:80]}" for f in result["fixes_applied"]
    )
    commit_msg = (
        f"fix: mopot auto-fix for run {run_id}\n\n"
        f"Fixed {len(result['fixes_applied'])} bug(s):\n{commit_summary}"
    )
    _git(["commit", "-m", commit_msg], project_path)

    # Push using token-embedded URL (works without credential helper)
    remote_url = f"https://{github_token}@github.com/{github_repo}.git"
    _git(["push", remote_url, branch_name], project_path)

    # Open PR
    pr_body = (
        "## Mopot Automated Fix Report\n\n"
        f"Run ID: `{run_id}`\n\n"
        f"### Fixes Applied\n\n"
        + "\n".join(
            f"**{f['bug_id']}** ({f['severity']}) — `{f['file']}`\n> {f['description']}"
            for f in result["fixes_applied"]
        )
        + "\n\n---\n*Generated by [Mopot](https://github.com/thecodedaniel/mopot) — the autonomous mobile release pipeline.*"
    )
    pr_title = f"Mopot Auto-Fix: {len(result['fixes_applied'])} bug(s) from run {run_id}"

    try:
        pr = _open_github_pr(
            repo=github_repo,
            token=github_token,
            branch=branch_name,
            base=base_branch,
            title=pr_title,
            body=pr_body,
        )
        result["pr_url"] = pr.get("html_url", "")
        result["pr_number"] = pr.get("number", 0)
    except requests.HTTPError as exc:
        result["error"] = f"PR creation failed: {exc.response.text}"

    return result


if __name__ == "__main__":
    import sys
    bug_report_path = sys.argv[1] if len(sys.argv) > 1 else "bug_report.json"
    with open(bug_report_path) as f:
        report = json.load(f)

    ctx = {
        "run_id": report.get("run_id", str(uuid.uuid4())[:8]),
        "project_path": os.environ.get("FLUTTER_PROJECT_PATH", "."),
        "github_repo": os.environ.get("GITHUB_REPO", ""),
    }
    fix_result = run_fixer(ctx, report)
    print(json.dumps(fix_result, indent=2))
