from __future__ import annotations

import signal
import threading


def main() -> int:
    stop_requested = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop_requested.set()

    for signal_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, signal_name):
            signal.signal(getattr(signal, signal_name), request_stop)

    print("agent-runtime idle", flush=True)
    stop_requested.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
