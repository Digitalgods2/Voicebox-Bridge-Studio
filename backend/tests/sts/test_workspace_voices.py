from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
import wave

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import config
from backend.database import Base, ProfileSample, VoiceProfile
from backend.sts.workspace_voices import VoiceWorkspaceError, WorkspaceVoices, inspect_wav


def write_wav(path: Path, frames: int = 16_000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16_000)
        output.writeframes(b"\x00\x00" * frames)
    return path


class WorkspaceVoicesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._previous_data_dir = config.get_data_dir()
        self._directory = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._directory.name)
        config.set_data_dir(self.data_dir)
        self.engine = create_engine(f"sqlite:///{self.data_dir / 'workspace.db'}")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.voices = WorkspaceVoices(session_factory=self.sessions)

        self.profile_id, self.sample_id = str(uuid4()), str(uuid4())
        relative = Path("profiles") / self.profile_id / f"{self.sample_id}.wav"
        write_wav(self.data_dir / relative)
        with self.sessions() as db:
            db.add(VoiceProfile(id=self.profile_id, name="Narrator", language="en", voice_type="cloned"))
            db.add(VoiceProfile(id=str(uuid4()), name="Preset", language="en", voice_type="preset"))
            db.add(
                ProfileSample(
                    id=self.sample_id,
                    profile_id=self.profile_id,
                    audio_path=str(relative),
                    reference_text="Authorized sample",
                )
            )
            db.commit()

    def tearDown(self) -> None:
        # Windows cannot delete the database while pooled connections hold it open.
        self.engine.dispose()
        config.set_data_dir(self._previous_data_dir)
        self._directory.cleanup()

    def test_inspects_pcm_wave(self) -> None:
        details = inspect_wav(write_wav(self.data_dir / "probe.wav"))
        self.assertEqual(details["sample_rate_hz"], 16_000)
        self.assertEqual(details["duration_seconds"], 1.0)

    def test_rejects_non_wave_file(self) -> None:
        path = self.data_dir / "not-audio.wav"
        path.write_bytes(b"not audio")
        with self.assertRaisesRegex(VoiceWorkspaceError, "WAVE"):
            inspect_wav(path)

    def test_lists_profiles_with_sample_counts(self) -> None:
        profiles = {profile["name"]: profile for profile in self.voices.profiles()}
        self.assertEqual(profiles["Narrator"]["sample_count"], 1)
        self.assertEqual(profiles["Preset"]["sample_count"], 0)
        self.assertEqual(profiles["Preset"]["voice_type"], "preset")
        self.assertEqual(self.voices.health()["profiles"], 2)

    def test_lists_samples_with_workspace_audio_urls(self) -> None:
        samples = self.voices.samples(self.profile_id)
        self.assertEqual(samples[0]["id"], self.sample_id)
        self.assertEqual(samples[0]["audio_url"], f"/samples/{self.sample_id}")

    def test_resolves_reference_in_place_without_copying(self) -> None:
        result = self.voices.fetch_reference(self.profile_id, self.sample_id, self.data_dir)
        expected = (self.data_dir / "profiles" / self.profile_id / f"{self.sample_id}.wav").resolve()
        self.assertEqual(Path(result["wav_path"]), expected)
        self.assertEqual(result["reference_text"], "Authorized sample")
        self.assertEqual(result["audio"]["duration_seconds"], 1.0)
        self.assertFalse((self.data_dir / "references").exists())

    def test_rejects_sample_from_another_profile(self) -> None:
        with self.assertRaisesRegex(VoiceWorkspaceError, "does not belong"):
            self.voices.fetch_reference(str(uuid4()), self.sample_id)

    def test_rejects_missing_sample_audio(self) -> None:
        (self.data_dir / "profiles" / self.profile_id / f"{self.sample_id}.wav").unlink()
        with self.assertRaisesRegex(VoiceWorkspaceError, "missing"):
            self.voices.fetch_reference(self.profile_id, self.sample_id)

    def test_rejects_oversized_reference(self) -> None:
        voices = WorkspaceVoices(session_factory=self.sessions, max_reference_bytes=10)
        with self.assertRaisesRegex(VoiceWorkspaceError, "safety limit"):
            voices.fetch_reference(self.profile_id, self.sample_id)

    def test_unknown_profile_and_bad_ids(self) -> None:
        with self.assertRaises(LookupError):
            self.voices.profile(str(uuid4()))
        with self.assertRaisesRegex(ValueError, "UUID"):
            self.voices.samples("not-a-uuid")


if __name__ == "__main__":
    unittest.main()
