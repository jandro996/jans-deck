# jans-impl - sesión de desarrollo

Estás en el worktree de desarrollo de jans. Repo principal: `~/research/jans` (rama `menu-bar`). Esta rama: `impl`.

Lee `DEVELOPMENT.md` para el historial completo de cambios y decisiones arquitectónicas antes de tocar código.

## Estructura clave

```
jans/gui.py              # GUI tkinter - ventana principal
jans/ctl.py              # jans-ctl CLI
jans/models.py           # Session, SessionState
jans/core/
  commands.py            # IPC via ~/.jans/pending_cmd.json
  state_detector.py      # Detección de estado via tty + JSONL
  persistence.py         # ~/.jans/state.json
```

## Para probar cambios

```bash
pkill -f "python.*jans.gui"; sleep 1
~/research/jans/.venv-menu/bin/python3 -m jans.gui &
```

El venv está en `~/research/jans/.venv-menu/` (compartido con el repo principal vía worktree).

## Decisiones importantes

- **Detección de estado**: tty del proceso Claude cruzada con ttys de iTerm2 (no nombres de tab, cambian dinámicamente)
- **Colores de tab iTerm2**: escape sequences escritas directamente al tty (`/dev/ttysXXX`)
- **Badge/título iTerm2**: badge se pone una vez al activar, título se restaura al nombre cuando está WAITING
- **IPC**: archivo JSON polling cada 3s - simple y fiable
- **Estado**: guardado a disco cada tick, no solo al cerrar

## Flujo de trabajo

Desarrolla aquí en `impl`. Cuando algo esté listo:
```bash
cd ~/research/jans && git merge impl
```
