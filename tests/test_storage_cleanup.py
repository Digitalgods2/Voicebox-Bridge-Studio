from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from voicebox_sts_bridge.storage_cleanup import StorageCleanup


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


def write_job(root: Path, *, status: str, updated: datetime, source_type: str = "youtube", video_input_id: str | None = None) -> Path:
    job_id = str(uuid4())
    job_dir = root / "video_jobs" / job_id
    job_dir.mkdir(parents=True)
    manifest = {
        "job_id": job_id,
        "status": status,
        "stage": status,
        "updated_at": updated.isoformat().replace("+00:00", "Z"),
        "source_type": source_type,
    }
    if video_input_id:
        manifest["video_input_id"] = video_input_id
    (job_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return job_dir


def write_video_input(root: Path, video_input_id: str, modified: datetime) -> Path:
    directory = root / "video_inputs"
    directory.mkdir(parents=True, exist_ok=True)
    media = directory / f"{video_input_id}.mp4"
    metadata = directory / f"{video_input_id}.json"
    media.write_bytes(b"video")
    metadata.write_text(json.dumps({"video_input_id": video_input_id}), encoding="utf-8")
    timestamp = modified.timestamp()
    for path in (media, metadata):
        path.touch()
        os.utime(path, (timestamp, timestamp))
    return media


class StorageCleanupTests(unittest.TestCase):
    def test_startup_cleanup_recovers_jobs_prunes_intermediates_and_removes_stale_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            referenced_id = str(uuid4())
            orphan_id = str(uuid4())
            latest_id = str(uuid4())
            recent = write_job(
                root,
                status="completed",
                updated=NOW - timedelta(days=2),
                source_type="local_upload",
                video_input_id=referenced_id,
            )
            (recent / "output.mkv").write_bytes(b"final")
            (recent / "audio").mkdir()
            (recent / "audio" / "source.wav").write_bytes(b"intermediate")
            (recent / "chunks").mkdir()
            (recent / "conversion-progress.json").write_text("{}", encoding="utf-8")

            stale = write_job(root, status="completed", updated=NOW - timedelta(days=31))
            (stale / "output.mkv").write_bytes(b"old final")
            failed = write_job(root, status="failed", updated=NOW - timedelta(days=2))
            interrupted = write_job(root, status="running", updated=NOW - timedelta(minutes=5))
            write_video_input(root, referenced_id, NOW - timedelta(days=2))
            write_video_input(root, orphan_id, NOW - timedelta(days=3))
            write_video_input(root, latest_id, NOW - timedelta(hours=2))

            result = StorageCleanup(root).run_startup_cleanup(now=NOW)

            self.assertEqual(result["recovered_interrupted_jobs"], 1)
            self.assertEqual(result["removed_video_jobs"], 2)
            self.assertGreaterEqual(result["pruned_intermediate_paths"], 3)
            self.assertFalse(stale.exists())
            self.assertFalse(failed.exists())
            self.assertTrue(interrupted.exists())
            self.assertTrue((recent / "output.mkv").is_file())
            self.assertFalse((recent / "audio").exists())
            self.assertFalse((recent / "chunks").exists())
            self.assertTrue((root / "video_inputs" / f"{referenced_id}.mp4").is_file())
            self.assertFalse((root / "video_inputs" / f"{orphan_id}.mp4").exists())
            self.assertTrue((root / "video_inputs" / f"{latest_id}.mp4").is_file())

    def test_latest_unreferenced_video_input_is_preserved_indefinitely(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            older_id = str(uuid4())
            latest_id = str(uuid4())
            write_video_input(root, older_id, NOW - timedelta(days=90))
            write_video_input(root, latest_id, NOW - timedelta(days=31))

            result = StorageCleanup(root).collect(now=NOW)

            self.assertEqual(result["removed_orphan_video_inputs"], 2)
            self.assertFalse((root / "video_inputs" / f"{older_id}.mp4").exists())
            self.assertFalse((root / "video_inputs" / f"{older_id}.json").exists())
            self.assertTrue((root / "video_inputs" / f"{latest_id}.mp4").is_file())
            self.assertTrue((root / "video_inputs" / f"{latest_id}.json").is_file())

    def test_invalid_job_manifest_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job_dir = root / "video_jobs" / str(uuid4())
            job_dir.mkdir(parents=True)
            (job_dir / "manifest.json").write_text("not json", encoding="utf-8")

            result = StorageCleanup(root).collect(now=NOW)

            self.assertEqual(result["invalid_manifests"], 1)
            self.assertTrue(job_dir.exists())


if __name__ == "__main__":
    unittest.main()
