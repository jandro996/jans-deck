import asyncio
import subprocess
import traceback

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from jans.core.log import log

_KEY_MAP: dict[str, str] = {
    "enter":      "Enter",
    "backspace":  "BSpace",
    "delete":     "Delete",
    "tab":        "Tab",
    "shift+tab":  "BTab",
    "escape":     "Escape",
    "up":         "Up",
    "down":       "Down",
    "left":       "Left",
    "right":      "Right",
    "home":       "Home",
    "end":        "End",
    "pageup":     "PPage",
    "pagedown":   "NPage",
    "ctrl+a":     "C-a",
    "ctrl+b":     "C-b",
    "ctrl+c":     "C-c",
    "ctrl+d":     "C-d",
    "ctrl+e":     "C-e",
    "ctrl+f":     "C-f",
    "ctrl+k":     "C-k",
    "ctrl+l":     "C-l",
    "ctrl+n":     "C-n",
    "ctrl+p":     "C-p",
    "ctrl+r":     "C-r",
    "ctrl+u":     "C-u",
    "ctrl+w":     "C-w",
    "ctrl+z":     "C-z",
    # f1-f6 are reserved for jans bindings
}

_TMUX_BASE = "jans"


def _run(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True)
    return result.stdout


class TerminalWidget(Widget, can_focus=True):
    DEFAULT_CSS = """
    TerminalWidget {
        height: 100%;
        width: 100%;
        padding: 0;
        border: none;
        overflow: hidden hidden;
    }
    TerminalWidget Static {
        height: 100%;
        width: 100%;
        padding: 0;
        border: none;
        overflow: hidden hidden;
        scrollbar-size: 0 0;
    }
    """

    def __init__(self, cmd: list[str], cwd: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.cmd = cmd
        self.cwd = cwd
        self._session: str | None = None
        self._poll_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Static("", id="screen", markup=False)

    def on_mount(self) -> None:
        try:
            self._start()
            self.call_after_refresh(self._sync_size)
            self._poll_task = asyncio.get_event_loop().create_task(self._poll_loop())
        except Exception:
            log.error("failed to mount terminal:\n%s", traceback.format_exc())

    def _start(self) -> None:
        w = max(self.size.width, 80)
        h = max(self.size.height, 24)
        name = f"{_TMUX_BASE}-{self.id}"
        self._session = name

        _run(["tmux", "new-session", "-d", "-s", name, "-x", str(w), "-y", str(h)])
        log.info("tmux session %s created (%dx%d)", name, w, h)

        if self.cwd:
            _run(["tmux", "send-keys", "-t", f"{name}:0", f"cd {self.cwd}", "Enter"])

        cmd_str = " ".join(self.cmd)
        _run(["tmux", "send-keys", "-t", f"{name}:0", cmd_str, "Enter"])
        log.info("started %s in session %s", self.cmd, name)

    async def _poll_loop(self) -> None:
        prev = ""
        static = self.query_one("#screen", Static)
        while self._session:
            try:
                content = await asyncio.get_event_loop().run_in_executor(
                    None, self._capture
                )
                if content != prev:
                    prev = content
                    text = Text.from_ansi(content)
                    static.update(text)
            except Exception:
                log.error("poll error:\n%s", traceback.format_exc())
            await asyncio.sleep(0.05)

    def _capture(self) -> str:
        return _run([
            "tmux", "capture-pane",
            "-t", f"{self._session}:0",
            "-p",   # print to stdout
            "-e",   # include ANSI escape codes
        ])

    def _sync_size(self) -> None:
        self._resize(self.size.width, self.size.height)

    def _resize(self, w: int, h: int) -> None:
        if not self._session or w <= 0 or h <= 0:
            return
        log.debug("resize %s: %dx%d", self._session, w, h)
        _run(["tmux", "resize-window", "-t", f"{self._session}:0",
              "-x", str(w), "-y", str(h)])

    def on_resize(self, event) -> None:
        self._resize(event.size.width, event.size.height)

    def on_key(self, event) -> None:
        if not self._session:
            return

        tmux_key = _KEY_MAP.get(event.key)
        if tmux_key:
            _run(["tmux", "send-keys", "-t", f"{self._session}:0", tmux_key])
        elif event.character and len(event.character) == 1:
            _run(["tmux", "send-keys", "-t", f"{self._session}:0",
                  "-l", event.character])
        else:
            return
        event.stop()

    def cleanup(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()
        if self._session:
            _run(["tmux", "kill-session", "-t", self._session])
            log.info("killed tmux session %s", self._session)
            self._session = None
