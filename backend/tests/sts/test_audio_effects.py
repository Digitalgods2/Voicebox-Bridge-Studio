from __future__ import annotations

from array import array
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import wave

from pydantic import ValidationError

from backend.routes import sts as sts_routes
from backend.routes.sts import (
    ConversionRequest,
    LocalVideoJobRequest,
    STSRuntime,
    YouTubeJobRequest,
)
from backend.sts.audio_effects import (
    AudioEffectsError,
    AudioEffectsProcessor,
    inspect_pcm_wav,
    validate_audio_adjustments,
)
from backend.sts.settings import STSSettings


def write_wave(path: Path, frames: int = 4_096, *, sample_rate: int = 22_050) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = array(
        "h",
        (
            round(10_000 * math.sin(2 * math.pi * 220 * index / sample_rate))
            for index in range(frames)
        ),
    )
    payload = samples.tobytes()
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(payload)
    return payload


class AudioAdjustmentValidationTests(unittest.TestCase):
    def test_accepts_bounds_and_normalizes_negative_zero(self) -> None:
        self.assertEqual(validate_audio_adjustments(-6, 6), (-6.0, 6.0))
        self.assertEqual(validate_audio_adjustments(-0.0, -0.0), (0.0, 0.0))

    def test_rejects_non_finite_and_out_of_range_values(self) -> None:
        for pitch, brightness in ((float("nan"), 0), (6.1, 0), (0, float("inf")), (0, -6.1)):
            with self.subTest(pitch=pitch, brightness=brightness), self.assertRaises(ValueError):
                validate_audio_adjustments(pitch, brightness)

    def test_api_models_bound_both_controls(self) -> None:
        request = ConversionRequest(
            input_id="input",
            profile_id="profile",
            sample_id="sample",
            pitch_semitones=-2.5,
            brightness_db=-3,
        )
        self.assertEqual(request.pitch_semitones, -2.5)
        self.assertEqual(request.brightness_db, -3)
        with self.assertRaises(ValidationError):
            ConversionRequest(
                input_id="input",
                profile_id="profile",
                sample_id="sample",
                pitch_semitones=7,
            )
        with self.assertRaises(ValidationError):
            YouTubeJobRequest(
                youtube_url="https://youtu.be/abc",
                profile_id="profile",
                sample_id="sample",
                brightness_db=-7,
                authorized=True,
            )
        local_video = LocalVideoJobRequest(
            video_input_id="input",
            profile_id="profile",
            sample_id="sample",
            pitch_semitones=1.5,
            brightness_db=-2,
            authorized=True,
        )
        self.assertEqual(local_video.pitch_semitones, 1.5)
        with self.assertRaises(ValidationError):
            LocalVideoJobRequest(
                video_input_id="input",
                profile_id="profile",
                sample_id="sample",
                pitch_semitones=-7,
            )


class AudioEffectsProcessorTests(unittest.TestCase):
    def test_zero_adjustments_bypass_ffmpeg(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.wav"
            write_wave(source)

            def unexpected_runner(*_args, **_kwargs):
                raise AssertionError("FFmpeg must not run for neutral settings")

            result = AudioEffectsProcessor(runner=unexpected_runner).apply(source, source)

            self.assertFalse(result["applied"])
            self.assertEqual(result["audio"]["frames"], 4_096)

    def test_filter_chain_uses_quality_pitch_formants_tone_and_exact_frames(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wav"
            original = write_wave(source)
            calls: list[list[str]] = []

            def runner(command, **_options):
                command = [str(item) for item in command]
                calls.append(command)
                shutil.copyfile(Path(command[command.index("-i") + 1]), Path(command[-1]))
                return subprocess.CompletedProcess(command, 0, "", "")

            result = AudioEffectsProcessor(ffmpeg_path="ffmpeg", runner=runner).apply(
                source,
                source,
                pitch_semitones=-2,
                brightness_db=-3.5,
            )

            self.assertTrue(result["applied"])
            self.assertEqual(source.read_bytes()[-len(original) :], original)
            self.assertEqual(result["audio"]["frames"], 4_096)
            filter_chain = calls[0][calls[0].index("-af") + 1]
            self.assertIn("rubberband=tempo=1", filter_chain)
            self.assertIn("formant=preserved", filter_chain)
            self.assertIn("pitchq=quality", filter_chain)
            self.assertIn("highshelf=frequency=2500", filter_chain)
            self.assertIn("gain=-3.500", filter_chain)
            self.assertIn("alimiter=limit=0.98", filter_chain)
            self.assertIn("apad=whole_len=4096", filter_chain)
            self.assertIn("atrim=end_sample=4096", filter_chain)

    def test_failed_filter_preserves_original_and_cleans_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wav"
            original = write_wave(source)

            def runner(command, **_options):
                return subprocess.CompletedProcess(command, 1, "", "rubberband failed")

            with self.assertRaisesRegex(AudioEffectsError, "rubberband failed"):
                AudioEffectsProcessor(runner=runner).apply(source, source, pitch_semitones=1)

            self.assertEqual(source.read_bytes()[-len(original) :], original)
            self.assertEqual(list(root.glob(".*.effects.*.wav")), [])

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is required for the application")
    def test_real_ffmpeg_preserves_exact_frames_and_decodes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.wav"
            write_wave(source, 22_050)

            result = AudioEffectsProcessor().apply(
                source,
                source,
                pitch_semitones=-2,
                brightness_db=-2,
            )

            self.assertEqual(result["audio"]["frames"], 22_050)
            self.assertEqual(result["audio"]["sample_rate_hz"], 22_050)
            self.assertEqual(inspect_pcm_wav(source)["duration_seconds"], 1.0)


class STSRouterContractTests(unittest.TestCase):
    def test_router_exposes_the_voice_changer_workflows(self) -> None:
        routes = {
            (route.path, method)
            for route in sts_routes.router.routes
            for method in route.methods
        }
        for expected in (
            ("/sts/status", "GET"),
            ("/sts/voices", "GET"),
            ("/sts/inputs", "POST"),
            ("/sts/video-inputs", "POST"),
            ("/sts/audio/jobs", "POST"),
            ("/sts/speech", "POST"),
            ("/sts/youtube/cache", "GET"),
            ("/sts/youtube/cache", "DELETE"),
            ("/sts/youtube/jobs", "POST"),
            ("/sts/video/status", "GET"),
            ("/sts/video/jobs", "POST"),
            ("/sts/media/youtube-cache/source", "GET"),
            ("/sts/media/video-jobs/{job_id}", "GET"),
        ):
            self.assertIn(expected, routes)

    def test_status_advertises_features_without_loading_the_model(self) -> None:
        class OfflineEngine:
            def status(self) -> dict:
                return {"ready": False, "checks": {"python": False}}

        with tempfile.TemporaryDirectory() as directory:
            runtime = STSRuntime(
                STSSettings(data_dir=Path(directory) / "data"),
                voices=object(),
                engine=OfflineEngine(),
            )
            sts_routes.set_runtime(runtime)
            try:
                status = sts_routes.sts_status()
                cache_status = sts_routes.youtube_cache_status()
                clear_status = sts_routes.clear_youtube_cache()
            finally:
                sts_routes.set_runtime(None)

        for feature in (
            "youtube-source-cache-v1",
            "local-video-upload-v1",
            "secure-openvoice-runtime-v1",
            "video-output-formats-v1",
            "workspace-voices-v1",
        ):
            self.assertIn(feature, status["features"])
        self.assertFalse(status["engine"]["ready"])
        self.assertIn("ffmpeg", status["video"]["checks"])
        self.assertIn("ffprobe", status["video"]["checks"])
        self.assertFalse(cache_status["active"])
        self.assertFalse(clear_status["cleared"])


if __name__ == "__main__":
    unittest.main()
