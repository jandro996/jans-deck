import signal
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
        from jans.core.persistence import save_sessions

        app = HelmApp()

        # Save sessions on any termination signal
        def _emergency_save(sig, frame):
            log.info("caught signal %d, saving sessions", sig)
            save_sessions(app._sessions)
            sys.exit(0)

        signal.signal(signal.SIGTERM, _emergency_save)
        signal.signal(signal.SIGINT, _emergency_save)

        app.run()
    except Exception:
        log.critical("fatal error during startup:\n%s", traceback.format_exc())
        print(f"Fatal error. Check log: {LOG_FILE}", file=sys.stderr)
        sys.exit(1)

    _set_tab_title(sys.argv[0])
    log.info("jans exited cleanly")


if __name__ == "__main__":
    main()
