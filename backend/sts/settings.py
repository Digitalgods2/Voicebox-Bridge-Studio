from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import config

_DEVICE_PATTERN = re.compile(r"(?:cpu|cuda(?::\d+)?)")


def _env(name: str, default: str) -> str:
    """Read an STS_* variable, accepting the pre-merge BRIDGE_* spelling."""
    legacy = "BRIDGE_" + name.removeprefix("STS_")
    return os.getenv(name) or os.getenv(legacy) or default


@dataclass(frozen=True, slots=True)
class STSSettings:
    """Speech-to-speech settings. STS shares the app's workspace data directory."""

    data_dir: Path = field(default_factory=config.get_data_dir)
    max_reference_bytes: int = 100 * 1024 * 1024
    engine_device: str = "cuda:0"
    video_job_retention_days: int = 30
    failed_video_job_retention_hours: int = 24
    orphan_video_input_retention_hours: int = 24

    def __post_init__(self) -> None:
        if self.max_reference_bytes <= 0:
            raise ValueError("Maximum reference size must be positive")
        for value, label in (
            (self.video_job_retention_days, "Video job retention days"),
            (self.failed_video_job_retention_hours, "Failed video job retention hours"),
            (self.orphan_video_input_retention_hours, "Orphan video input retention hours"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{label} must be a positive integer")
        if not isinstance(self.engine_device, str) or _DEVICE_PATTERN.fullmatch(self.engine_device) is None:
            raise ValueError("Engine device must be 'cpu', 'cuda', or 'cuda:<index>'")
        object.__setattr__(self, "data_dir", Path(self.data_dir).resolve())

    @classmethod
    def from_env(cls) -> STSSettings:
        defaults = cls()
        return cls(
            data_dir=defaults.data_dir,
            engine_device=_env("STS_ENGINE_DEVICE", defaults.engine_device),
            video_job_retention_days=int(
                _env("STS_VIDEO_JOB_RETENTION_DAYS", str(defaults.video_job_retention_days))
            ),
            failed_video_job_retention_hours=int(
                _env(
                    "STS_FAILED_VIDEO_JOB_RETENTION_HOURS",
                    str(defaults.failed_video_job_retention_hours),
                )
            ),
            orphan_video_input_retention_hours=int(
                _env(
                    "STS_ORPHAN_VIDEO_INPUT_RETENTION_HOURS",
                    str(defaults.orphan_video_input_retention_hours),
                )
            ),
        )
