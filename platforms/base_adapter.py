"""Abstract base interface for all mobile platform adapters. Do not modify."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BuildResult:
    success: bool
    artifact_path: str
    build_log: str
    error: Optional[str] = None


@dataclass
class EmulatorSession:
    device_id: str
    platform: str
    is_running: bool


@dataclass
class ScreenshotResult:
    path: str
    screen_name: str
    timestamp: str


@dataclass
class CrashLog:
    timestamp: str
    error_type: str
    stack_trace: str
    screen: Optional[str] = None


@dataclass
class DeployResult:
    success: bool
    track: str
    version_code: int
    error: Optional[str] = None


class MobilePlatformAdapter(ABC):

    @abstractmethod
    def build(self, project_path: str, config: dict) -> BuildResult:
        """Build the app and return artifact path."""
        pass

    @abstractmethod
    def launch_emulator(self, device_config: dict) -> EmulatorSession:
        """Start emulator/simulator and return session."""
        pass

    @abstractmethod
    def install_app(self, session: EmulatorSession, artifact_path: str) -> bool:
        """Install app on running emulator."""
        pass

    @abstractmethod
    def take_screenshot(self, session: EmulatorSession, label: str) -> ScreenshotResult:
        """Capture current screen state."""
        pass

    @abstractmethod
    def tap(self, session: EmulatorSession, x: int, y: int) -> bool:
        """Simulate tap at coordinates."""
        pass

    @abstractmethod
    def get_crash_logs(self, session: EmulatorSession) -> List[CrashLog]:
        """Return all crashes since session start."""
        pass

    @abstractmethod
    def run_tests(self, project_path: str) -> dict:
        """Execute test suite and return results."""
        pass

    @abstractmethod
    def deploy(self, artifact_path: str, store_config: dict) -> DeployResult:
        """Submit build to app store."""
        pass

    @abstractmethod
    def teardown(self, session: EmulatorSession) -> bool:
        """Stop emulator and clean up."""
        pass
