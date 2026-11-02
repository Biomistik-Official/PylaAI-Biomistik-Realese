import tempfile
import unittest
from pathlib import Path

from vision.model_profiles import model_paths


class ModelProfileTests(unittest.TestCase):
    def test_new_default_never_mixes_with_old_models_and_legacy_is_selectable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for folder in [root/'models', root/'models/upstream-763c389']:
                folder.mkdir(parents=True, exist_ok=True)
                for name in ['mainInGameModel.onnx','tileDetector.onnx']:
                    (folder/name).touch()
            self.assertTrue(all('upstream-763c389' in path for path in model_paths({}, root)))
            self.assertTrue(all('upstream-' not in path for path in model_paths({'vision_model_profile':'legacy'}, root)))
            (root/'models/upstream-763c389/tileDetector.onnx').unlink()
            with self.assertRaises(FileNotFoundError):
                model_paths({}, root)

    def test_arbitrary_profile_paths_are_rejected(self):
        with self.assertRaises(ValueError):
            model_paths({'vision_model_profile':'../outside'})
