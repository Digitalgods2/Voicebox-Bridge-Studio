"""Copy an installed VoiceBox library into this app's workspace data directory.

The installed VoiceBox app keeps its database and voice profiles in its own
app-data folder. This copies them (read-only on the source side) so the
profiles, samples, history, and captures are available to every feature here,
including speech-to-speech:

    python scripts/import_voicebox_data.py --dry-run
    python scripts/import_voicebox_data.py

The database is copied with SQLite's online backup API, so the copy is
consistent even if VoiceBox is still running. Existing files in the target are
never overwritten. Downloaded runtime binaries (``backends/``) and regenerable
caches are skipped; model weights live in the shared Hugging Face cache and are
not copied.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_DIRS = ("profiles", "generations", "captures")
DATABASE = "voicebox.db"


def default_source() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "sh.voicebox.app"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "sh.voicebox.app"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "sh.voicebox.app"


def plan(source: Path, target: Path) -> tuple[list[tuple[Path, Path]], list[Path]]:
    copies: list[tuple[Path, Path]] = []
    skipped: list[Path] = []
    for name in LIBRARY_DIRS:
        base = source / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            destination = target / path.relative_to(source)
            if destination.exists():
                skipped.append(destination)
            else:
                copies.append((path, destination))
    return copies, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=default_source(), help="Installed VoiceBox data folder")
    parser.add_argument("--target", type=Path, default=ROOT / "data", help="Workspace data folder")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be copied without writing")
    args = parser.parse_args(argv)

    source, target = args.source.resolve(), args.target.resolve()
    source_db, target_db = source / DATABASE, target / DATABASE
    if not source_db.is_file():
        print(f"error: no VoiceBox database at {source_db}", file=sys.stderr)
        return 1
    if source == target:
        print("error: source and target are the same folder", file=sys.stderr)
        return 1
    if target_db.exists():
        print(
            f"error: {target_db} already exists; this workspace already has a library. "
            "Move it aside first to re-import.",
            file=sys.stderr,
        )
        return 1

    copies, skipped = plan(source, target)
    size = source_db.stat().st_size + sum(src.stat().st_size for src, _ in copies)
    print(f"Source: {source}\nTarget: {target}")
    print(f"Database + {len(copies)} library files ({size / 1_048_576:.1f} MiB); {len(skipped)} already present")
    if args.dry_run:
        return 0

    target.mkdir(parents=True, exist_ok=True)
    with (
        closing(sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)) as source_conn,
        closing(sqlite3.connect(target_db)) as target_conn,
    ):
        source_conn.backup(target_conn)

    for path, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)

    with closing(sqlite3.connect(f"file:{target_db}?mode=ro", uri=True)) as check:
        profiles = check.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
        stored_paths = [row[0] for row in check.execute("SELECT audio_path FROM profile_samples")]
    # Stored sample paths are relative to the data folder, with the source OS's separators.
    missing = sum(1 for stored in stored_paths if not (target / stored.replace("\\", "/")).is_file())
    samples = len(stored_paths)
    print(f"Imported {profiles} profiles and {samples} samples ({missing} sample files missing).")
    return 0 if missing == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
