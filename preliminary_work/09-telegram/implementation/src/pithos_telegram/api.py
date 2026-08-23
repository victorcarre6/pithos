"""Small Telegram Bot API client with secret-safe errors."""

import json
import urllib.request


class TelegramAPI:
    """Call only the Bot API methods required by the broker."""

    def __init__(self, token: str) -> None:
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"

    def call(self, method: str, payload: dict) -> dict:
        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            f"{self.base_url}/{method}",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                result = json.load(response)
        except Exception as error:
            message = str(error).replace(self.token, "[secret]")
            raise RuntimeError(f"Telegram unavailable: {message}") from None
        if not result.get("ok"):
            description = str(result.get("description", "unknown error"))
            description = description.replace(self.token, "[secret]")
            raise RuntimeError(f"Telegram rejected request: {description}")

        return result.get("result")

    def send(self, user_id: str, text: str) -> dict:
        return self.call("sendMessage", {"chat_id": user_id, "text": text})

    def updates(self, offset: int) -> list[dict]:
        result = self.call(
            "getUpdates",
            {"offset": offset, "timeout": 30, "allowed_updates": ["message"]},
        )

        return result or []

    def probe(self) -> dict:
        return self.call("getMe", {})
