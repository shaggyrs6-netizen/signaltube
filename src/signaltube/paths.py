"""Source installs retain var/; desktop/wheel installs use private XDG data."""
import os
from pathlib import Path
SOURCE_ROOT = Path(__file__).resolve().parents[2]
def data_dir():
    override = os.environ.get("SIGNALTUBE_DATA_DIR")
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise ValueError("SIGNALTUBE_DATA_DIR must be absolute")
        return path
    if (SOURCE_ROOT / "run.sh").is_file():
        return SOURCE_ROOT / "var"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home()/".local/share"))) / "signaltube"
STATE = data_dir()
