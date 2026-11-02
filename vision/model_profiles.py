"""Select a complete model pair without overwriting the original fork models."""
from pathlib import Path


def model_paths(config=None, root=None):
    if config is None:
        from common.utils import load_toml_as_dict
        config = load_toml_as_dict('cfg/general_config.toml')
    profile = config.get('vision_model_profile', 'upstream-763c389')
    if profile not in {'legacy', 'upstream-763c389'}:
        raise ValueError('Unknown vision model profile.')
    folder = Path(root or Path(__file__).resolve().parents[1]) / 'models'
    if profile != 'legacy':
        folder /= profile
    pair = [folder/'mainInGameModel.onnx', folder/'tileDetector.onnx']
    for path in pair:
        if not path.is_file():
            raise FileNotFoundError(f'Missing model in selected profile: {path}')
    return [str(path) for path in pair]
