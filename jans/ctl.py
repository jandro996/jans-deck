"""jans-ctl - CLI to control a running jans instance from Claude."""
import json
import sys
from pathlib import Path

from jans.core.commands import send_command


COLORS = ["red", "orange", "yellow", "green", "blue", "purple", "pink", "teal"]


def usage():
    print(f"""jans-ctl <command> [args]

Commands:
  list                        List all sessions and their states
  new-research <name>         Create a new research session in ~/research/<name>/
  new-task <repo> <name> [ticket]  Create a task worktree, optionally linked to a feature
  new-tool <name>             Create a new tooling session in ~/tools/<name>/
  new-feature <ticket> <nickname> [desc]  Create a feature manifest
  feature-status <ticket>     Show sessions linked to a feature and their states
  new-review <url>            Create a review session from a GitHub PR URL
  load <path> [name]          Load an existing directory as a session
  rename <current> <new>      Rename a session
  delete <name>               Remove a session from jans
  color <name> <color>        Set a color tag for a session ({", ".join(COLORS)})
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
        if len(rest) < 2:
            print("Error: repo and name required", file=sys.stderr)
            sys.exit(1)
        ticket = rest[2] if len(rest) > 2 else None
        result = send_command("new-task", repo=rest[0], name=rest[1], ticket=ticket)
    elif cmd == "new-feature":
        if len(rest) < 2:
            print("Error: ticket and nickname required", file=sys.stderr)
            sys.exit(1)
        result = send_command("new-feature", ticket=rest[0], nickname=rest[1],
                              description=" ".join(rest[2:]) if len(rest) > 2 else "")
    elif cmd == "feature-status":
        if not rest:
            print("Error: ticket required", file=sys.stderr)
            sys.exit(1)
        result = send_command("feature-status", ticket=rest[0])
    elif cmd == "new-tool":
        if not rest:
            print("Error: name required", file=sys.stderr)
            sys.exit(1)
        result = send_command("new-tool", name=rest[0])
    elif cmd == "new-review":
        if not rest:
            print("Error: GitHub PR URL required", file=sys.stderr)
            sys.exit(1)
        result = send_command("new-review", url=rest[0])
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
    elif cmd == "color":
        if len(rest) < 2:
            print(f"Error: name and color required. Colors: {', '.join(COLORS)}", file=sys.stderr)
            sys.exit(1)
        result = send_command("color", name=rest[0], color=rest[1])
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
