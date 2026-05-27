import json
import time
from pathlib import Path

JANS_DIR = Path.home() / ".jans"
CMD_FILE = JANS_DIR / "pending_cmd.json"
RESULT_FILE = JANS_DIR / "cmd_result.json"
TIMEOUT_SECS = 5


def send_command(action: str, **kwargs) -> dict:
    JANS_DIR.mkdir(exist_ok=True)
    RESULT_FILE.unlink(missing_ok=True)
    CMD_FILE.write_text(json.dumps({"action": action, **kwargs}))
    deadline = time.monotonic() + TIMEOUT_SECS
    while time.monotonic() < deadline:
        if RESULT_FILE.exists():
            result = json.loads(RESULT_FILE.read_text())
            RESULT_FILE.unlink(missing_ok=True)
            return result
        time.sleep(0.05)
    CMD_FILE.unlink(missing_ok=True)
    return {"error": "jans is not running or not responding"}


def read_pending_command() -> dict | None:
    if not CMD_FILE.exists():
        return None
    try:
        cmd = json.loads(CMD_FILE.read_text())
        CMD_FILE.unlink(missing_ok=True)
        return cmd
    except Exception:
        CMD_FILE.unlink(missing_ok=True)
        return None


def write_result(result: dict) -> None:
    RESULT_FILE.write_text(json.dumps(result))
