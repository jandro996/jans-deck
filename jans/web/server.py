"""jans web server - FastAPI backend for the web dashboard."""
import asyncio
import dataclasses
import json
import subprocess
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from jans.core.commands import read_pending_command, write_result
from jans.core.log import log
from jans.core.persistence import load_saved_sessions, save_sessions
from jans.core.state_detector import detect_state, find_real_session_id
from jans.models import Session, SessionState

_HERE = Path(__file__).parent
app = FastAPI(title="jans")
app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")

# In-memory session store shared across websocket connections
_sessions: list[Session] = []
_clients: set[WebSocket] = set()


def _sessions_as_json() -> list[dict]:
    return [
        {
            "name": s.name,
            "cwd": s.cwd,
            "session_id": s.session_id,
            "state": s.state.value,
            "last_activity": s.last_activity.isoformat(),
            "terminal_id": s.terminal_id,
        }
        for s in _sessions
    ]


async def _broadcast(event: str, data) -> None:
    dead = set()
    for ws in _clients:
        try:
            await ws.send_text(json.dumps({"event": event, "data": data}))
        except Exception:
            dead.add(ws)
    _clients -= dead


async def _refresh_loop() -> None:
    while True:
        try:
            changed = False
            new_sessions = []
            for s in _sessions:
                if s.state == SessionState.PAUSED:
                    new_sessions.append(s)
                    continue
                real_id = find_real_session_id(s.cwd)
                if real_id and real_id != s.session_id:
                    s = dataclasses.replace(s, session_id=real_id)
                new_state, last_activity = detect_state(s)
                if new_state != s.state or last_activity != s.last_activity:
                    s = dataclasses.replace(s, state=new_state, last_activity=last_activity)
                    changed = True
                new_sessions.append(s)
            _sessions[:] = new_sessions
            if changed:
                await _broadcast("sessions", _sessions_as_json())

            # Handle jans-ctl commands
            cmd = read_pending_command()
            if cmd:
                result = _execute_command(cmd)
                write_result(result)
                await _broadcast("sessions", _sessions_as_json())

        except Exception as e:
            log.error("refresh error: %s", e)
        await asyncio.sleep(3)


def _focus_iterm_session(session: Session) -> None:
    """Focus the iTerm2 tab for this session by matching its cwd."""
    script = f'''
tell application "iTerm2"
    activate
    repeat with w in windows
        repeat with t in tabs of w
            repeat with s in sessions of t
                if name of s contains "{session.name}" then
                    tell w to select
                    select t
                    return
                end if
            end repeat
        end repeat
    end repeat
end tell
'''
    subprocess.run(["osascript", "-e", script], capture_output=True)


def _open_iterm_session(session: Session) -> None:
    """Open a new iTerm2 tab for this session."""
    cwd = session.cwd
    cmd = f"cd '{cwd}' && claude --continue"
    script = f'''
tell application "iTerm2"
    activate
    tell current window
        create tab with default profile
        tell current session of current tab
            set name to "{session.name}"
            write text "{cmd}"
        end tell
    end tell
end tell
'''
    subprocess.run(["osascript", "-e", script], capture_output=True)


def _execute_command(cmd: dict) -> dict:
    import uuid
    action = cmd.get("action", "")
    if action == "list":
        return {"sessions": _sessions_as_json()}
    elif action == "new-research":
        name = cmd.get("name", "research")
        cwd = str(Path.home() / "research" / name)
        Path(cwd).mkdir(parents=True, exist_ok=True)
        s = Session(name=name, cwd=cwd, session_id=str(uuid.uuid4()))
        _sessions.append(s)
        _open_iterm_session(s)
        return {"ok": True, "name": name}
    elif action == "new-task":
        name = cmd.get("name", "task")
        cwd = str(Path.home() / "research" / name)
        Path(cwd).mkdir(parents=True, exist_ok=True)
        s = Session(name=name, cwd=cwd, session_id=str(uuid.uuid4()))
        _sessions.append(s)
        _open_iterm_session(s)
        return {"ok": True, "name": name}
    elif action == "delete":
        name = cmd.get("name")
        before = len(_sessions)
        _sessions[:] = [s for s in _sessions if s.name != name]
        return {"ok": len(_sessions) < before}
    elif action == "rename":
        current, new = cmd.get("current"), cmd.get("new")
        for i, s in enumerate(_sessions):
            if s.name == current:
                _sessions[i] = dataclasses.replace(s, name=new)
                return {"ok": True}
        return {"error": f"session '{current}' not found"}
    elif action == "home":
        return {"ok": True}
    return {"error": f"unknown action: {action}"}


@app.on_event("startup")
async def startup():
    global _sessions
    _sessions = load_saved_sessions()
    log.info("web server started, loaded %d sessions", len(_sessions))
    asyncio.create_task(_refresh_loop())


@app.on_event("shutdown")
async def shutdown():
    save_sessions(_sessions)
    log.info("web server shutdown, saved sessions")


@app.get("/", response_class=HTMLResponse)
async def index():
    return (_HERE / "static" / "index.html").read_text()


@app.get("/api/sessions")
async def get_sessions():
    return _sessions_as_json()


@app.post("/api/sessions")
async def create_session(body: dict):
    result = _execute_command(body)
    await _broadcast("sessions", _sessions_as_json())
    return result


@app.post("/api/sessions/{session_id}/focus")
async def focus_session(session_id: str):
    session = next((s for s in _sessions if s.session_id == session_id), None)
    if not session:
        return {"error": "not found"}
    if session.state == SessionState.PAUSED:
        _open_iterm_session(session)
        session = dataclasses.replace(session, state=SessionState.PROCESSING)
        idx = next(i for i, s in enumerate(_sessions) if s.session_id == session_id)
        _sessions[idx] = session
        await _broadcast("sessions", _sessions_as_json())
    else:
        _focus_iterm_session(session)
    return {"ok": True}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    before = len(_sessions)
    _sessions[:] = [s for s in _sessions if s.session_id != session_id]
    await _broadcast("sessions", _sessions_as_json())
    return {"ok": len(_sessions) < before}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    await ws.send_text(json.dumps({"event": "sessions", "data": _sessions_as_json()}))
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        _clients.discard(ws)


def main():
    import signal
    import sys

    def _save(sig, frame):
        save_sessions(_sessions)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _save)
    signal.signal(signal.SIGINT, _save)

    print("\033]0;jans\007", end="", flush=True)
    log.info("starting jans web server")
    uvicorn.run(app, host="127.0.0.1", port=7777, log_level="warning")
