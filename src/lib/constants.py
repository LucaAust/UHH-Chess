from pathlib import Path

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

GAME_DATA_SAVE_DIR: Path = Path().cwd() / "game_data"
GAME_DATA_SAVE_DIR.mkdir(parents=True, exist_ok=True)

class Color:
   PURPLE = '\033[95m'
   CYAN = '\033[96m'
   DARKCYAN = '\033[36m'
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'