import sys
import traceback

from jans.core.log import LOG_FILE, log


def _set_tab_title(title: str) -> None:
    print(f"\x1b]0;{title}\x07", end="", flush=True)


def main():
    log.info("=" * 60)
    log.info("jans starting")
    _set_tab_title("jans")

    try:
        from jans.app import HelmApp
        app = HelmApp()
        app.run()
    except Exception:
        log.critical("fatal error during startup:\n%s", traceback.format_exc())
        print(f"Fatal error. Check log: {LOG_FILE}", file=sys.stderr)
        sys.exit(1)

    _set_tab_title(sys.argv[0])  # restore on exit
    log.info("jans exited cleanly")


if __name__ == "__main__":
    main()
