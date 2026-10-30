"""In-process access to the workspace's voice profiles for speech-to-speech.

STS used to reach voice profiles through the separate VoiceBox REST API.
Now that both run in one application, it reads the same database and
sample files the TTS features use, with no HTTP hop and no cached copies.
"""

from __future__ import annotations

import json
import math
import wave
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any
from uuid import UUID

from .. import config


class VoiceWorkspaceError(RuntimeError):
    """Raised when a workspace voice profile or sample cannot be used for STS."""


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"{label} must be a UUID") from exc


def inspect_wav(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        header = handle.read(12)
    if len(header) < 12 or header[:4] not in (b"RIFF", b"RF64") or header[8:12] != b"WAVE":
        raise VoiceWorkspaceError("Voice sample is not a RIFF/RF64 WAVE file")

    details: dict[str, Any] = {"container": header[:4].decode("ascii"), "size_bytes": path.stat().st_size}
    try:
        with closing(wave.open(str(path), "rb")) as wav:
            frame_rate = wav.getframerate()
            frames = wav.getnframes()
            details.update(
                channels=wav.getnchannels(),
                sample_rate_hz=frame_rate,
                sample_width_bytes=wav.getsampwidth(),
                frames=frames,
                duration_seconds=round(frames / frame_rate, 3) if frame_rate else None,
            )
    except (EOFError, wave.Error):
        # Some valid WAVE files use codecs unsupported by Python's wave module.
        details["pcm_details_available"] = False
    return details


def default_pitch_semitones(effects_chain: str | None) -> float:
    """The voice's enabled pitch-shift effect, clamped to the STS range; 0 if none.

    A voice tuned with a pitch effect for TTS starts the voice changer at the
    same pitch, as the pre-merge bridge did.
    """
    try:
        effects = json.loads(effects_chain) if effects_chain else []
    except (TypeError, ValueError):
        return 0.0
    for effect in effects if isinstance(effects, list) else []:
        if not isinstance(effect, dict) or effect.get("type") != "pitch_shift" or effect.get("enabled") is False:
            continue
        try:
            semitones = float((effect.get("params") or {}).get("semitones"))
        except (TypeError, ValueError):
            continue
        if math.isfinite(semitones):
            return max(-6.0, min(6.0, semitones))
    return 0.0


def _default_session() -> Any:
    # SessionLocal is assigned by init_db(); read it at call time, not import time.
    from ..database import session

    if session.SessionLocal is None:
        raise VoiceWorkspaceError("The voice database has not been initialized")
    return session.SessionLocal()


class WorkspaceVoices:
    """Read voice profiles and reference samples straight from the workspace database."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] = _default_session,
        max_reference_bytes: int = 100 * 1024 * 1024,
    ) -> None:
        self._session_factory = session_factory
        self.max_reference_bytes = max_reference_bytes

    def health(self) -> dict[str, Any]:
        with closing(self._session_factory()) as db:
            from ..database import VoiceProfile

            return {"status": "healthy", "profiles": db.query(VoiceProfile).count()}

    def profiles(self) -> list[dict[str, Any]]:
        from sqlalchemy import func

        from ..database import ProfileSample, VoiceProfile

        with closing(self._session_factory()) as db:
            counts = dict(
                db.query(ProfileSample.profile_id, func.count(ProfileSample.id))
                .group_by(ProfileSample.profile_id)
                .all()
            )
            rows = db.query(VoiceProfile).order_by(VoiceProfile.created_at.desc()).all()
            return [self._profile(row, counts.get(row.id, 0)) for row in rows]

    def profile(self, profile_id: str) -> dict[str, Any]:
        from ..database import ProfileSample, VoiceProfile

        profile_id = _uuid(profile_id, "profile_id")
        with closing(self._session_factory()) as db:
            row = db.query(VoiceProfile).filter_by(id=profile_id).first()
            if row is None:
                raise LookupError("Voice profile not found")
            return self._profile(row, db.query(ProfileSample).filter_by(profile_id=profile_id).count())

    def samples(self, profile_id: str) -> list[dict[str, Any]]:
        from ..database import ProfileSample

        profile_id = _uuid(profile_id, "profile_id")
        with closing(self._session_factory()) as db:
            rows = db.query(ProfileSample).filter_by(profile_id=profile_id).all()
            return [
                {
                    "id": row.id,
                    "profile_id": row.profile_id,
                    "reference_text": row.reference_text,
                    "audio_url": f"/samples/{row.id}",
                }
                for row in rows
            ]

    def fetch_reference(
        self,
        profile_id: str,
        sample_id: str,
        data_dir: Path | None = None,
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Resolve and validate the sample's WAV in place.

        ``data_dir`` and ``overwrite`` are accepted for compatibility with the
        services' former HTTP client, which downloaded a cached copy; workspace
        samples need neither.
        """
        from ..database import ProfileSample

        profile_id = _uuid(profile_id, "profile_id")
        sample_id = _uuid(sample_id, "sample_id")
        with closing(self._session_factory()) as db:
            row = db.query(ProfileSample).filter_by(id=sample_id, profile_id=profile_id).first()
            if row is None:
                raise VoiceWorkspaceError("The selected sample does not belong to the selected profile")
            audio_path, reference_text = row.audio_path, row.reference_text

        wav_path = config.resolve_storage_path(audio_path)
        if wav_path is None or not wav_path.is_file():
            raise VoiceWorkspaceError("The selected sample's audio file is missing from the workspace")
        size = wav_path.stat().st_size
        if size > self.max_reference_bytes:
            raise VoiceWorkspaceError(f"Voice sample exceeds the {self.max_reference_bytes}-byte safety limit")
        return {
            "profile_id": profile_id,
            "sample_id": sample_id,
            "reference_text": reference_text,
            "wav_path": str(wav_path),
            "audio": inspect_wav(wav_path),
            "cached": True,
        }

    @staticmethod
    def _profile(row: Any, sample_count: int) -> dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "language": row.language,
            "voice_type": row.voice_type or "cloned",
            "sample_count": sample_count,
            "default_pitch_semitones": default_pitch_semitones(row.effects_chain),
        }
