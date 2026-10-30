from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from backend import config
from backend.sts.settings import STSSettings


class STSSettingsTests(unittest.TestCase):
    def test_defaults_share_the_workspace_data_directory(self) -> None:
        settings = STSSettings()
        self.assertEqual(settings.data_dir, config.get_data_dir().resolve())
        self.assertTrue(settings.data_dir.is_absolute())
        self.assertEqual(settings.engine_device, "cuda:0")

    def test_resolves_explicit_data_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(STSSettings(data_dir=Path(directory)).data_dir, Path(directory).resolve())

    def test_rejects_invalid_device(self) -> None:
        with self.assertRaisesRegex(ValueError, "Engine device"):
            STSSettings(engine_device="tpu")

    def test_from_env_prefers_sts_names_and_accepts_legacy_bridge_names(self) -> None:
        with patch.dict("os.environ", {"BRIDGE_ENGINE_DEVICE": "cpu"}, clear=True):
            self.assertEqual(STSSettings.from_env().engine_device, "cpu")
        with patch.dict(
            "os.environ", {"STS_ENGINE_DEVICE": "cuda:1", "BRIDGE_ENGINE_DEVICE": "cpu"}, clear=True
        ):
            self.assertEqual(STSSettings.from_env().engine_device, "cuda:1")
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(STSSettings.from_env().video_job_retention_days, 30)


if __name__ == "__main__":
    unittest.main()
