"""Configure, probe or run the Telegram broker."""

import argparse
import os
import threading
from pathlib import Path

from .api import TelegramAPI
from .broker import TelegramBroker
from .server import TelegramBrokerServer


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Pithos Telegram broker")
    parser.add_argument("mode", choices=("probe", "serve"))
    parser.add_argument("--socket", type=Path, default=Path("/private/tmp/pithos-telegram.sock"))
    parser.add_argument("--logs-root", type=Path, default=Path.home() / "logs" / "pithos")
    arguments = parser.parse_args()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    user_id = os.getenv("TELEGRAM_USER_ID", "")
    if not token or not user_id:
        parser.error("TELEGRAM_BOT_TOKEN and TELEGRAM_USER_ID are required")

    api = TelegramAPI(token)
    if arguments.mode == "probe":
        identity = api.probe()
        print(f"Telegram bot ready: @{identity.get('username', 'unknown')}")
        return 0

    broker = TelegramBroker(api, user_id, arguments.logs_root.expanduser())
    stop = threading.Event()

    def poll() -> None:
        while not stop.wait(1):
            try:
                broker.poll_once()
            except (RuntimeError, ValueError, KeyError, TypeError):
                stop.wait(5)

    thread = threading.Thread(target=poll, daemon=True)
    thread.start()
    try:
        with TelegramBrokerServer(arguments.socket, broker) as server:
            server.serve_forever()
    finally:
        stop.set()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
