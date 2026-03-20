import json
import pathlib
from typing import Any, Dict


def load_config(path: str = None) -> Dict[str, Any]:
    """Load the JSON configuration file.

    If path is None, it will look for `appConfig.json` next to this module.
    """
    if path is None:
        base = pathlib.Path(__file__).resolve().parent
        path = base / "appConfig.json"
    path = pathlib.Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    return config
