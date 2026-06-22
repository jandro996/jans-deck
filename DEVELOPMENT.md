# jans - development log

## Qué es jans

Gestor de sesiones de Claude Code para macOS. Permite al usuario controlar múltiples sesiones simultáneas mediante voz (Wispr Flow) a través de un orquestador Claude Code. Tiene una GUI nativa tkinter y una CLI (`jans-ctl`) para IPC.

## Arquitectura

```
jans/
├── gui.py              # Ventana tkinter principal
├── ctl.py              # CLI jans-ctl (IPC via archivos)
├── models.py           # Session, SessionState
└── core/
    ├── commands.py     # IPC: pending_cmd.json / cmd_result.json en ~/.jans/
    ├── state_detector.py  # Lee ~/.claude/sessions/*.json y ~/.claude/projects/*.jsonl
    └── persistence.py  # Guarda/carga ~/.jans/state.json
```

**IPC**: `jans-ctl` escribe `~/.jans/pending_cmd.json`, la GUI lo lee cada 3s y escribe resultado en `~/.jans/cmd_result.json`.

**Estado de sesión**: Se detecta buscando el proceso Claude activo para el cwd (session files en `~/.claude/sessions/`) y analizando el último mensaje del JSONL de conversación.

## Ramas

- `main` - versión TUI (Textual), funciona pero problemas con copy-paste y click
- `menu-bar` - versión GUI tkinter, **activa**
- `web-app` - experimento FastAPI, aparcado

## Sesión orquestador

jans se ejecuta en `~/research/jans`. La sesión `jans` en la GUI apunta al orquestador (esta conversación). El comando `jans` en `~/bin/jans` lanza la GUI con el venv `.venv-menu`.

---

## Cambios - sesión 2026-06-06 / 2026-06-08

### Visual (gui.py)

- **Paleta Catppuccin**: BG=#1e1e2e, colores de estado (amarillo=processing, verde=waiting, rojo=needs_input, azul=paused)
- **Borde izquierdo de color**: 3px frame coloreado por estado en cada session row (en vez de solo el icono)
- **Separadores de sección**: línea horizontal + label "paused" / "active" (en vez de texto plano `── paused ──`)
- **Hover fix**: el hover ahora propaga `bg` a todos los labels hijo del row (antes solo cambiaba el frame padre)
- **Canvas resize**: el inner frame del canvas se expande al ancho de la ventana (`itemconfig("inner", width=e.width)`)
- **Status bar**: mueve resumen de estados (⚡ needs input / ● waiting / ▶ processing) bajo el header
- **Save en tick**: el estado se guarda a disco cada 3s, no solo al cerrar la ventana

### Detección de estado

**Problema**: Al reiniciar jans, las sesiones con tab abierto aparecían como PAUSED. La detección usaba nombres de tab, pero Claude Code sobreescribe el nombre del tab con el título de la tarea actual.

**Solución**: Usar la `tty` del proceso Claude como identificador estable.
- `find_claude_session_for_cwd(cwd) -> (session_id, pid)` - nuevo en state_detector.py
- `_iterm_open_ttys() -> set[str]` - AppleScript que devuelve ttys de todos los tabs de iTerm2
- `_pid_tty(pid) -> str | None` - obtiene `/dev/ttysXXX` de un proceso
- En cada tick: sesión activa = el proceso Claude de ese cwd tiene su tty en un tab de iTerm2

**Decisión**: No usar PID solo (sesiones en tmux tienen PIDs vivos pero no tabs). No usar nombre de tab (cambia dinámicamente). La tty es el único identificador fiable.

### Colores de usuario

- Campo `color: str | None` añadido a `Session`
- Persiste en `~/.jans/state.json`
- Paleta: red, orange, yellow, green, blue, purple, pink, teal
- **GUI**: chip rectangular 10×14px (`tk.Frame` con bg=color) junto al nombre
- **iTerm2**: escribe secuencias de escape directamente al tty del proceso:
  `\033]6;1;bg;red;brightness;N\a` etc.
  Se aplica automáticamente en el tick cuando el tab está abierto.
- **Comando**: `jans-ctl color <name> <color>`

### Focus por tty

`_focus_session_by_tty(tty)` - AppleScript busca el tab por tty en vez de por nombre. El nombre del tab cambia, la tty no.

---

## Pendiente / ideas

- [ ] Implementar handler `load` en `_execute_command` de la GUI
- [ ] Detectar cierre de tab en tiempo real (actualmente espera al siguiente tick de 3s)
- [ ] Comando `jans-ctl color <name> clear` para quitar color
- [ ] Mejorar detección de estado PROCESSING en tiempo real (el JSONL solo se actualiza al completar un turno)
