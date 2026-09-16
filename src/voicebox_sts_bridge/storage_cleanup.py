from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from uuid import UUID

LOGGER = logging.getLogger(__name__)

_VIDEO_JOB_TRANSIENT_DIRECTORIES = {"audio", "chunks", "download"}
_VIDEO_JOB_TRANSIENT_FILES = {"conversion-progress.json"}


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            mode="w",
            encoding="utf-8",
            newline="\n",
            delete=False,
        ) as temporary:
            json.dump(payload, temporary, indent=2, ensure_ascii=False, allow_nan=False)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


class StorageCleanup:
    """Safely collect disposable local video data at bridge startup.

    Final outputs are retained for a bounded period, while the large files
    used to produce them are disposable once a job has completed. The newest
    uploaded local video remains available as the user's active working source;
    older unreferenced uploads are collected after their grace period. Failed
    jobs are retained briefly for diagnostics and then removed as a unit.
    """

    def __init__(
        self,
        data_dir: str | Path,
        *,
        completed_job_retention: timedelta = timedelta(days=30),
        failed_job_retention: timedelta = timedelta(hours=24),
        orphan_video_input_retention: timedelta = timedelta(hours=24),
    ) -> None:
        for value, label in (
            (completed_job_retention, "completed_job_retention"),
            (failed_job_retention, "failed_job_retention"),
            (orphan_video_input_retention, "orphan_video_input_retention"),
        ):
            if not isinstance(value, timedelta) or value.total_seconds() <= 0:
                raise ValueError(f"{label} must be a positive timedelta")
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.video_jobs_dir = self.data_dir / "video_jobs"
        self.video_inputs_dir = self.data_dir / "video_inputs"
        self.completed_job_retention = completed_job_retention
        self.failed_job_retention = failed_job_retention
        self.orphan_video_input_retention = orphan_video_input_retention

    def run_startup_cleanup(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Recover abandoned jobs, then remove only known disposable data."""
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        recovered = self.recover_interrupted_video_jobs(now=current)
        collected = self.collect(now=current)
        collected["recovered_interrupted_jobs"] = recovered
        return collected

    def recover_interrupted_video_jobs(self, *, now: datetime | None = None) -> int:
        """Mark queued/running jobs from a prior process as failed."""
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        recovered = 0
        for job_dir in self._job_directories():
            manifest_path = job_dir / "manifest.json"
            manifest = self._read_manifest(manifest_path)
            if manifest is None or manifest.get("status") not in {"queued", "running"}:
                continue
            manifest.update(
                {
                    "status": "failed",
                    "stage": "failed",
                    "updated_at": current.isoformat().replace("+00:00", "Z"),
                    "failed_at": current.isoformat().replace("+00:00", "Z"),
                    "error": {
                        "type": "Interrupted",
                        "message": "Server stopped; submit a new video job.",
                    },
                }
            )
            try:
                _atomic_json(manifest_path, manifest)
            except (OSError, TypeError, ValueError) as exc:
                LOGGER.warning("Could not recover video job %s: %s", job_dir.name, exc)
                continue
            recovered += 1
        return recovered

    def collect(self, *, now: datetime | None = None) -> dict[str, Any]:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        removed_jobs = 0
        pruned_intermediates = 0
        invalid_manifests = 0
        referenced_video_inputs: set[str] = set()

        for job_dir in self._job_directories():
            manifest = self._read_manifest(job_dir / "manifest.json")
            if manifest is None:
                invalid_manifests += 1
                continue

            status = manifest.get("status")
            updated = _parse_timestamp(manifest.get("updated_at"))
            if updated is None:
                invalid_manifests += 1
                continue
            age = current - updated
            retention = (
                self.completed_job_retention
                if status == "completed"
                else self.failed_job_retention
                if status == "failed"
                else None
            )
            if retention is not None and age >= retention:
                try:
                    self._remove_job_directory(job_dir)
                except OSError as exc:
                    LOGGER.warning("Could not remove stale video job %s: %s", job_dir.name, exc)
                    continue
                removed_jobs += 1
                continue

            if status == "completed":
                pruned_intermediates += self._prune_job_intermediates(job_dir)

            if manifest.get("source_type") == "local_upload":
                video_input_id = manifest.get("video_input_id")
                try:
                    referenced_video_inputs.add(str(UUID(str(video_input_id))))
                except (ValueError, TypeError, AttributeError):
                    invalid_manifests += 1

        latest_video_input_id = self._latest_video_input_id()
        removed_video_inputs = self._collect_orphan_video_inputs(
            referenced_video_inputs,
            cutoff=current - self.orphan_video_input_retention,
            protected_video_input_id=latest_video_input_id,
        )
        return {
            "removed_video_jobs": removed_jobs,
            "pruned_intermediate_paths": pruned_intermediates,
            "removed_orphan_video_inputs": removed_video_inputs,
            "invalid_manifests": invalid_manifests,
        }

    def _job_directories(self) -> list[Path]:
        if not self.video_jobs_dir.is_dir() or self.video_jobs_dir.is_symlink():
            return []
        return [
            path
            for path in self.video_jobs_dir.iterdir()
            if path.is_dir() and not path.is_symlink()
        ]

    @staticmethod
    def _read_manifest(path: Path) -> dict[str, Any] | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _remove_job_directory(self, target: Path) -> None:
        root = self.video_jobs_dir.resolve(strict=False)
        absolute = Path(os.path.abspath(target))
        if absolute.parent != Path(os.path.abspath(root)) or not absolute.is_relative_to(root):
            raise OSError(f"Refusing to remove a path outside video_jobs: {absolute}")
        if absolute.is_symlink() or absolute.is_file():
            absolute.unlink(missing_ok=True)
        elif absolute.is_dir():
            shutil.rmtree(absolute)

    def _prune_job_intermediates(self, job_dir: Path) -> int:
        removed = 0
        for name in _VIDEO_JOB_TRANSIENT_DIRECTORIES:
            path = job_dir / name
            try:
                if path.is_symlink() or path.is_file():
                    path.unlink(missing_ok=True)
                    removed += 1
                elif path.is_dir():
                    shutil.rmtree(path)
                    removed += 1
            except OSError as exc:
                LOGGER.warning("Could not prune video job intermediate %s: %s", path, exc)
        for name in _VIDEO_JOB_TRANSIENT_FILES:
            path = job_dir / name
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink(missing_ok=True)
                    removed += 1
            except OSError as exc:
                LOGGER.warning("Could not prune video job intermediate %s: %s", path, exc)
        return removed

    def _latest_video_input_id(self) -> str | None:
        if not self.video_inputs_dir.is_dir() or self.video_inputs_dir.is_symlink():
            return None
        latest: tuple[datetime, str] | None = None
        for path in self.video_inputs_dir.iterdir():
            if path.suffix.lower() == ".json" or not path.is_file():
                continue
            try:
                video_input_id = str(UUID(path.stem))
            except (ValueError, AttributeError):
                continue
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            except OSError:
                continue
            if latest is None or modified > latest[0]:
                latest = (modified, video_input_id)
        return latest[1] if latest is not None else None

    def _collect_orphan_video_inputs(
        self,
        referenced: set[str],
        *,
        cutoff: datetime,
        protected_video_input_id: str | None = None,
    ) -> int:
        if not self.video_inputs_dir.is_dir() or self.video_inputs_dir.is_symlink():
            return 0
        grouped: dict[str, list[Path]] = {}
        for path in self.video_inputs_dir.iterdir():
            if not path.is_file() and not path.is_symlink():
                continue
            stem = path.stem
            try:
                key = str(UUID(stem))
            except (ValueError, AttributeError):
                if path.name.startswith(".") and path.suffix in {".upload", ".tmp"}:
                    self._remove_if_old(path, cutoff)
                continue
            grouped.setdefault(key, []).append(path)

        removed = 0
        for video_input_id, paths in grouped.items():
            if video_input_id in referenced or video_input_id == protected_video_input_id:
                continue
            timestamps = []
            for path in paths:
                try:
                    timestamps.append(datetime.fromtimestamp(path.stat().st_mtime, timezone.utc))
                except OSError:
                    timestamps.append(datetime.now(timezone.utc))
            if not timestamps or max(timestamps) >= cutoff:
                continue
            for path in paths:
                try:
                    if path.is_symlink() or path.is_file():
                        path.unlink(missing_ok=True)
                        removed += 1
                except OSError as exc:
                    LOGGER.warning("Could not remove orphan video input %s: %s", path, exc)
        return removed

    @staticmethod
    def _remove_if_old(path: Path, cutoff: datetime) -> None:
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            if modified < cutoff:
                path.unlink(missing_ok=True)
        except OSError as exc:
            LOGGER.warning("Could not remove stale upload temporary %s: %s", path, exc)
