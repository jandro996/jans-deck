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
    # f1-f10 are reserved for jans bindings
}

_TMUX_BASE = "jans"


def _run(args: list[str], input_text: str | None = None) -> str:
    result = subprocess.run(args, capture_output=True, text=True, input=input_text)
    return result.stdout


class TerminalWidget(Widget, can_focus=True):
    DEFAULT_CSS = """
    TerminalWidget {
        height: 100%;
        width: 100%;
        padding: 0;
        border: none;
        overflow-y: auto;
        overflow-x: hidden;
    }
    TerminalWidget Static {
        width: 100%;
        padding: 0;
        border: none;
        height: auto;
    }
    """

    def __init__(self, cmd: list[str], cwd: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.cmd = cmd
        self.cwd = cwd
        self._session: str | None = None
        self._poll_task: asyncio.Task | None = None
        self._char_buffer: list[str] = []
        self._flush_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Static("", id="screen", markup=False)

    def on_mount(self) -> None:
        try:
            self._start()
            self.call_after_refresh(self._sync_size)
            self._poll_task = asyncio.get_event_loop().create_task(self._poll_loop())
        except Exception:
            log.error("failed to mount terminal:\n%s", traceback.format_exc())

    def _session_exists(self, name: str) -> bool:
        result = subprocess.run(
            ["tmux", "has-session", "-t", name],
            capture_output=True
        )
        return result.returncode == 0

    def _start(self) -> None:
        w = max(self.size.width, 80)
        h = max(self.size.height, 24)
        name = f"{_TMUX_BASE}-{self.id}"
        self._session = name

        if self._session_exists(name):
            # Reconnect to existing session - process kept running while jans was closed.
            # Clear scrollback history to avoid accumulating redraw artifacts from resizes.
            log.info("reconnecting to existing tmux session %s", name)
            _run(["tmux", "clear-history", "-t", f"{name}:0"])
            self._resize(w, h)
            return

        _run(["tmux", "new-session", "-d", "-s", name, "-x", str(w), "-y", str(h)])
        _run(["tmux", "set-option", "-t", name, "history-limit", "10000"])
        # Copy mode: y copies selection to macOS clipboard
        _run(["tmux", "set-option", "-t", name, "mode-keys", "vi"])
        _run(["tmux", "bind-key", "-T", "copy-mode-vi", "y",
              "send-keys", "-X", "copy-pipe-and-cancel", "pbcopy"])
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
                    # Auto-scroll to bottom only if user hasn't scrolled up
                    if self.scroll_y >= self.max_scroll_y - 3:
                        self.scroll_end(animate=False)
            except Exception:
                log.error("poll error:\n%s", traceback.format_exc())
            await asyncio.sleep(0.05)

    def _capture(self) -> str:
        return _run([
            "tmux", "capture-pane",
            "-t", f"{self._session}:0",
            "-p",        # print to stdout
            "-e",        # include ANSI escape codes
            "-S", "-5000" # 5000 lines of scrollback history
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

    def enter_copy_mode(self) -> None:
        """F9: enter tmux vi copy mode. Navigate with arrows, v to select, y to copy."""
        if self._session:
            _run(["tmux", "copy-mode", "-t", f"{self._session}:0"])

    def paste_from_clipboard(self) -> None:
        """F10: paste macOS clipboard content into the session."""
        if self._session:
            result = subprocess.run(["pbpaste"], capture_output=True, text=True)
            if result.stdout:
                self._send_text(result.stdout)

    def on_paste(self, event) -> None:
        """Handle paste / bracketed-paste - covers Wispr Flow clipboard mode and Cmd+V."""
        if not self._session:
            return
        text = getattr(event, "text", "") or ""
        if text:
            log.debug("paste: %d chars -> tmux", len(text))
            self._send_text(text)
            event.stop()

    def _send_text(self, text: str) -> None:
        """Send arbitrary text to tmux in one shot."""
        _run(["tmux", "load-buffer", "-"], input_text=text)
        _run(["tmux", "paste-buffer", "-t", f"{self._session}:0", "-d"])

    def on_key(self, event) -> None:
        if not self._session:
            return

        tmux_key = _KEY_MAP.get(event.key)
        if tmux_key:
            # Special key - flush any buffered chars first
            self._flush_char_buffer()
            _run(["tmux", "send-keys", "-t", f"{self._session}:0", tmux_key])
        elif event.character and len(event.character) == 1:
            # Buffer regular characters and flush in bulk after 30ms silence
            # This prevents losing chars when input arrives faster than subprocess latency
            self._char_buffer.append(event.character)
            if self._flush_task:
                self._flush_task.cancel()
            self._flush_task = asyncio.get_event_loop().call_later(
                0.03, self._flush_char_buffer
            )
        else:
            return
        event.stop()

    def _flush_char_buffer(self) -> None:
        if self._char_buffer and self._session:
            text = "".join(self._char_buffer)
            self._char_buffer = []
            log.debug("flush %d chars -> tmux", len(text))
            self._send_text(text)
        self._flush_task = None

    def cleanup(self, kill: bool = False) -> None:
        if self._poll_task:
            self._poll_task.cancel()
        if self._session:
            if kill:
                _run(["tmux", "kill-session", "-t", self._session])
                log.info("killed tmux session %s", self._session)
            else:
                log.info("detached from tmux session %s (still running)", self._session)
            self._session = None
