"""Deployer agent — uploads APK and metadata to Google Play Store internal testing track."""

import dataclasses
import json
import os
import uuid
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from platforms.base_adapter import DeployResult

_SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]


def run_deployer(run_context: dict, asset_package: dict) -> DeployResult:
    """
    Submit APK and release metadata to Play Store internal testing track.

    run_context keys:
      apk_path, run_id
    asset_package keys:
      release_notes, screenshots (list of paths)
    Environment:
      PLAY_STORE_JSON_PATH, PLAY_STORE_PACKAGE_NAME
    """
    apk_path = run_context.get("apk_path", "")
    package_name = os.environ["PLAY_STORE_PACKAGE_NAME"]
    service_account_path = os.environ["PLAY_STORE_JSON_PATH"]

    if not Path(apk_path).exists():
        return DeployResult(
            success=False,
            track="internal",
            version_code=0,
            error=f"APK not found: {apk_path}",
        )

    credentials = service_account.Credentials.from_service_account_file(
        service_account_path, scopes=_SCOPES
    )
    service = build("androidpublisher", "v3", credentials=credentials)

    edit_id = None
    try:
        # 1. Create edit session
        edit = service.edits().insert(packageName=package_name, body={}).execute()
        edit_id = edit["id"]

        # 2. Upload APK
        with open(apk_path, "rb") as apk_file:
            apk_response = (
                service.edits()
                .apks()
                .upload(
                    packageName=package_name,
                    editId=edit_id,
                    media_body=MediaIoBaseUpload(
                        apk_file,
                        mimetype="application/vnd.android.package-archive",
                        resumable=True,
                    ),
                )
                .execute()
            )
        version_code = apk_response["versionCode"]

        # 3. Assign to internal track
        release_notes_text = asset_package.get("release_notes", "Bug fixes and improvements.")
        service.edits().tracks().update(
            packageName=package_name,
            editId=edit_id,
            track="internal",
            body={
                "releases": [
                    {
                        "versionCodes": [version_code],
                        "status": "completed",
                        "releaseNotes": [
                            {"language": "en-US", "text": release_notes_text[:500]}
                        ],
                    }
                ]
            },
        ).execute()

        # 4. Commit the edit
        service.edits().commit(packageName=package_name, editId=edit_id).execute()

        return DeployResult(
            success=True,
            track="internal",
            version_code=version_code,
        )

    except Exception as exc:
        # Clean up orphaned edit to unblock future submissions
        if edit_id:
            try:
                service.edits().delete(packageName=package_name, editId=edit_id).execute()
            except Exception:
                pass
        return DeployResult(
            success=False,
            track="internal",
            version_code=0,
            error=str(exc),
        )


if __name__ == "__main__":
    import sys
    asset_path = sys.argv[1] if len(sys.argv) > 1 else "assets.json"
    with open(asset_path) as f:
        assets = json.load(f)

    ctx = {
        "run_id": assets.get("run_id", str(uuid.uuid4())[:8]),
        "apk_path": os.environ.get("MOPOT_APK_PATH", ""),
    }
    deploy_result = run_deployer(ctx, assets)
    print(json.dumps(dataclasses.asdict(deploy_result), indent=2))
