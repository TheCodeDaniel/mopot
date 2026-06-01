"""iOS platform adapter stub — not yet implemented. Planned for v2.0."""

from typing import List

from platforms.base_adapter import (
    BuildResult,
    CrashLog,
    DeployResult,
    EmulatorSession,
    MobilePlatformAdapter,
    ScreenshotResult,
)

_NOT_IMPLEMENTED = "iOS adapter is not yet implemented. Planned for Mopot v2.0."


class IOSAdapter(MobilePlatformAdapter):

    def build(self, project_path: str, config: dict) -> BuildResult:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def launch_emulator(self, device_config: dict) -> EmulatorSession:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def install_app(self, session: EmulatorSession, artifact_path: str) -> bool:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def take_screenshot(self, session: EmulatorSession, label: str) -> ScreenshotResult:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def tap(self, session: EmulatorSession, x: int, y: int) -> bool:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_crash_logs(self, session: EmulatorSession) -> List[CrashLog]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def run_tests(self, project_path: str) -> dict:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def deploy(self, artifact_path: str, store_config: dict) -> DeployResult:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def teardown(self, session: EmulatorSession) -> bool:
        raise NotImplementedError(_NOT_IMPLEMENTED)
