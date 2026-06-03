"""FastAPI webhook server — receives GitHub push events and orchestrates the Mopot pipeline."""

import dataclasses
import hashlib
import hmac
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

# Ensure project root is importable when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.fixer_agent import run_fixer
from agents.tester_agent import run_tester
from platforms.android_adapter import AndroidAdapter

app = FastAPI(title="Mopot Pipeline Server", version="1.0.0")

_PORT = int(os.environ.get("MOPOT_PORT", 7432))
_RUNS_DIR = Path.home() / ".mopot" / "runs"
_RUNS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    config_path = Path.home() / ".mopot" / "config.json"
    try:
        return json.loads(config_path.read_text()) if config_path.exists() else {}
    except Exception:
        return {}


def _inject_config_env() -> None:
    """Populate os.environ from ~/.mopot/config.json for any keys not already set.
    This lets the server run without manually exporting env vars when a wizard
    config file is present."""
    config = _load_config()
    mapping = {
        "ANTHROPIC_API_KEY":     config.get("anthropicKey"),
        "GITHUB_TOKEN":          config.get("githubToken"),
        "GITHUB_REPO":           config.get("githubRepo"),
        "GITHUB_DEFAULT_BRANCH": config.get("defaultBranch"),
        "FLUTTER_PROJECT_PATH":  config.get("flutterProjectPath"),
        "MOPOT_AVD":             config.get("avdName"),
        "WEBHOOK_SECRET":        config.get("webhookSecret"),
    }
    for env_key, value in mapping.items():
        if value and not os.environ.get(env_key):
            os.environ[env_key] = value


# Inject config values into the environment as soon as the module loads
_inject_config_env()


def _verify_github_signature(payload: bytes, sig_header: str) -> bool:
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if not secret:
        return True  # allow unsigned requests when no secret is set (dev mode)
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header)


def _log_path(run_id: str) -> Path:
    return _RUNS_DIR / f"{run_id}.json"


def _update_run(run_id: str, updates: dict) -> None:
    path = _log_path(run_id)
    data: dict = {}
    if path.exists():
        data = json.loads(path.read_text())
    data.update(updates)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, indent=2))


def _init_run(run_id: str, base: dict) -> None:
    data = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "queued",
        **base,
    }
    _log_path(run_id).write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

async def _run_pipeline(run_context: dict) -> None:
    run_id = run_context["run_id"]
    adapter = AndroidAdapter()

    try:
        # STEP 1 — Build
        _update_run(run_id, {"status": "building"})
        build_result = adapter.build(
            run_context["project_path"],
            config={"env": "debug"},
        )
        if not build_result.success:
            _update_run(run_id, {"status": "failed", "error": f"Build failed: {build_result.error}"})
            return

        run_context["apk_path"] = build_result.artifact_path
        run_context["build_result"] = dataclasses.asdict(build_result)
        _update_run(run_id, {"status": "testing", "apk_path": build_result.artifact_path})

        # STEP 2 — Test (up to 2 attempts if fixes are applied)
        bug_report: Optional[dict] = None
        fix_result: Optional[dict] = None

        for attempt in range(2):
            _update_run(run_id, {"status": "testing", "fix_attempt": attempt})
            bug_report = run_tester(run_context)
            _update_run(run_id, {"bug_report": bug_report})

            if not bug_report.get("bugs"):
                break  # clean run — no fixing needed

            if attempt == 0:
                # STEP 3 — Fix
                _update_run(run_id, {"status": "fixing"})
                fix_result = run_fixer(run_context, bug_report)
                _update_run(run_id, {"fix_pr_url": fix_result.get("pr_url", ""), "fix_result": fix_result})

                if fix_result.get("error"):
                    break  # fixer failed — skip retest, proceed to assets anyway

                # Rebuild on the fixed branch before retesting
                _update_run(run_id, {"status": "rebuilding"})
                build_result = adapter.build(run_context["project_path"], config={"env": "debug"})
                if not build_result.success:
                    break
                run_context["apk_path"] = build_result.artifact_path

        _update_run(run_id, {"status": "complete"})

    except Exception as exc:
        _update_run(run_id, {"status": "failed", "error": str(exc)})
        raise


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": "1.0.0"})


@app.get("/runs/{run_id}")
async def get_run(run_id: str) -> JSONResponse:
    path = _log_path(run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return JSONResponse(json.loads(path.read_text()))


@app.get("/runs")
async def list_runs() -> JSONResponse:
    runs = []
    for p in sorted(_RUNS_DIR.glob("*.json"), reverse=True)[:20]:
        try:
            data = json.loads(p.read_text())
            runs.append({
                "run_id": data.get("run_id"),
                "status": data.get("status"),
                "started_at": data.get("started_at"),
                "repo": data.get("repo", ""),
                "branch": data.get("branch", ""),
            })
        except json.JSONDecodeError:
            pass
    return JSONResponse(runs)


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
) -> JSONResponse:
    payload_bytes = await request.body()

    if not _verify_github_signature(payload_bytes, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    if x_github_event != "push":
        return JSONResponse({"message": f"Ignored event: {x_github_event}"})

    payload = json.loads(payload_bytes)
    run_id = str(uuid.uuid4())[:12]
    config = _load_config()

    run_context: dict[str, Any] = {
        "run_id": run_id,
        "repo": payload.get("repository", {}).get("full_name", ""),
        "branch": payload.get("ref", "").replace("refs/heads/", ""),
        "commit_sha": payload.get("after", ""),
        "project_path": os.environ.get("FLUTTER_PROJECT_PATH") or config.get("flutterProjectPath", "."),
        "avd_name": os.environ.get("MOPOT_AVD") or config.get("avdName", "Pixel_9_Pro"),
    }

    _init_run(run_id, run_context)
    background_tasks.add_task(_run_pipeline, run_context)

    return JSONResponse({"run_id": run_id, "message": "Pipeline started"}, status_code=202)


@app.post("/trigger")
async def manual_trigger(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    run_id = str(uuid.uuid4())[:12]
    config = _load_config()

    run_context: dict[str, Any] = {
        "run_id": run_id,
        "repo":         body.get("repo")         or os.environ.get("GITHUB_REPO")             or config.get("githubRepo", ""),
        "branch":       body.get("branch")        or os.environ.get("GITHUB_DEFAULT_BRANCH")   or config.get("defaultBranch", "main"),
        "commit_sha":   body.get("commit_sha", "manual"),
        "project_path": body.get("project_path") or os.environ.get("FLUTTER_PROJECT_PATH")    or config.get("flutterProjectPath", "."),
        "avd_name":                                   os.environ.get("MOPOT_AVD")              or config.get("avdName", "Pixel_9_Pro"),
    }

    _init_run(run_id, run_context)
    background_tasks.add_task(_run_pipeline, run_context)

    return JSONResponse({"run_id": run_id, "message": "Pipeline started manually"}, status_code=202)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("webhook.main:app", host="0.0.0.0", port=_PORT, reload=False)
