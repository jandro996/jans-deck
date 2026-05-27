"""jans-ctl - CLI to control a running jans instance from Claude."""
import json
import sys
from pathlib import Path

from jans.core.commands import send_command


def usage():
    print("""jans-ctl <command> [args]

Commands:
  list                        List all sessions and their states
  new-research <name>         Create a new research session in ~/research/<name>/
  new-task <name>             Create a new task session
  load <path> [name]          Load an existing directory as a session
  rename <current> <new>      Rename a session
  delete <name>               Remove a session from jans
  home                        Switch right panel back to orchestrator
  switch <name>               Switch right panel to a named session
  state                       Show current app state (sessions + status)
""")


def main():
    args = sys.argv[1:]
    if not args:
        usage()
        sys.exit(1)

    cmd = args[0]
    rest = args[1:]

    if cmd == "list":
        result = send_command("list")
    elif cmd == "new-research":
        if not rest:
            print("Error: name required", file=sys.stderr)
            sys.exit(1)
        result = send_command("new-research", name=rest[0])
    elif cmd == "new-task":
        if not rest:
            print("Error: name required", file=sys.stderr)
            sys.exit(1)
        result = send_command("new-task", name=rest[0])
    elif cmd == "load":
        if not rest:
            print("Error: path required", file=sys.stderr)
            sys.exit(1)
        path = rest[0]
        name = rest[1] if len(rest) > 1 else None
        result = send_command("load", path=path, name=name)
    elif cmd == "rename":
        if len(rest) < 2:
            print("Error: current name and new name required", file=sys.stderr)
            sys.exit(1)
        result = send_command("rename", current=rest[0], new=rest[1])
    elif cmd == "delete":
        if not rest:
            print("Error: name required", file=sys.stderr)
            sys.exit(1)
        result = send_command("delete", name=rest[0])
    elif cmd == "home":
        result = send_command("home")
    elif cmd == "switch":
        if not rest:
            print("Error: name required", file=sys.stderr)
            sys.exit(1)
        result = send_command("switch", name=rest[0])
    elif cmd == "state":
        result = send_command("list")
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        usage()
        sys.exit(1)

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
