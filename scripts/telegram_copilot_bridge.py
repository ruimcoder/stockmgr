from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True)
class BridgeConfig:
    telegram_bot_token: str
    copilot_command_template: str
    allowed_user_id: int | None
    allowed_chat_id: int | None
    poll_timeout_seconds: int
    request_timeout_seconds: int
    max_history_messages: int
    state_path: Path

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        command_template = os.getenv("COPILOT_COMMAND_TEMPLATE", "").strip()
        if not token:
            raise RuntimeError("Missing TELEGRAM_BOT_TOKEN.")
        if not command_template:
            raise RuntimeError("Missing COPILOT_COMMAND_TEMPLATE.")
        allowed_user_raw = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
        allowed_chat_raw = os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "").strip()
        state_path_raw = os.getenv("TELEGRAM_BRIDGE_STATE_PATH", ".telegram-copilot-bridge.state.json")
        return cls(
            telegram_bot_token=token,
            copilot_command_template=command_template,
            allowed_user_id=int(allowed_user_raw) if allowed_user_raw else None,
            allowed_chat_id=int(allowed_chat_raw) if allowed_chat_raw else None,
            poll_timeout_seconds=max(5, int(os.getenv("TELEGRAM_POLL_TIMEOUT_SECONDS", "30"))),
            request_timeout_seconds=max(5, int(os.getenv("TELEGRAM_REQUEST_TIMEOUT_SECONDS", "40"))),
            max_history_messages=max(2, int(os.getenv("TELEGRAM_MAX_HISTORY_MESSAGES", "12"))),
            state_path=Path(state_path_raw).resolve(),
        )


class TelegramCopilotBridge:
    def __init__(self, config: BridgeConfig):
        self.config = config
        self.api_base = f"https://api.telegram.org/bot{self.config.telegram_bot_token}"
        self.state: dict[str, Any] = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        if not self.config.state_path.exists():
            return {"offset": 0, "histories": {}}
        with self.config.state_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"offset": 0, "histories": {}}
        data.setdefault("offset", 0)
        data.setdefault("histories", {})
        return data

    def _save_state(self) -> None:
        self.config.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.state_path.open("w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def run_forever(self) -> None:
        print("Telegram Copilot bridge started.")
        while True:
            try:
                self._poll_once()
            except Exception as exc:
                print(f"Bridge loop error: {exc}")
                time.sleep(2)

    def _poll_once(self) -> None:
        updates = self._telegram(
            "getUpdates",
            {
                "offset": int(self.state.get("offset", 0)) + 1,
                "timeout": self.config.poll_timeout_seconds,
                "allowed_updates": ["message", "edited_message"],
            },
        )
        for update in updates:
            update_id = int(update.get("update_id", 0))
            if update_id:
                self.state["offset"] = update_id
            self._handle_update(update)
        self._save_state()

    def _handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or update.get("edited_message")
        if not isinstance(message, dict):
            return
        text = str(message.get("text", "")).strip()
        if not text:
            return

        from_user = message.get("from") or {}
        chat = message.get("chat") or {}
        user_id = int(from_user.get("id", 0))
        chat_id = int(chat.get("id", 0))
        if not self._authorized(user_id=user_id, chat_id=chat_id):
            self._send_text(chat_id, "Unauthorized sender/chat.")
            return

        if text.lower() in {"/start", "/help"}:
            self._send_text(
                chat_id,
                (
                    "Telegram Copilot bridge is active.\n"
                    "Send any prompt to chat with Copilot CLI.\n"
                    "Use /reset to clear conversation context."
                ),
            )
            return
        if text.lower() == "/reset":
            self._history(chat_id).clear()
            self._send_text(chat_id, "Conversation context reset.")
            return

        reply = self._ask_copilot(chat_id=chat_id, user_text=text)
        self._send_text(chat_id, reply)

    def _authorized(self, *, user_id: int, chat_id: int) -> bool:
        if self.config.allowed_user_id is not None and user_id != self.config.allowed_user_id:
            return False
        if self.config.allowed_chat_id is not None and chat_id != self.config.allowed_chat_id:
            return False
        return True

    def _history(self, chat_id: int) -> list[dict[str, str]]:
        histories = self.state.setdefault("histories", {})
        key = str(chat_id)
        if key not in histories or not isinstance(histories[key], list):
            histories[key] = []
        return histories[key]

    def _ask_copilot(self, *, chat_id: int, user_text: str) -> str:
        history = self._history(chat_id)
        history.append({"role": "user", "content": user_text})
        history[:] = history[-self.config.max_history_messages :]
        prompt = self._build_prompt(history)
        try:
            answer = self._run_copilot(prompt)
        except Exception as exc:
            answer = f"Copilot CLI error: {exc}"
        history.append({"role": "assistant", "content": answer})
        history[:] = history[-self.config.max_history_messages :]
        return answer

    def _build_prompt(self, history: list[dict[str, str]]) -> str:
        lines = [
            "You are GitHub Copilot CLI. Reply clearly and concisely.",
            "Conversation:",
        ]
        for entry in history:
            role = "User" if entry["role"] == "user" else "Assistant"
            lines.append(f"{role}: {entry['content']}")
        lines.append("Assistant:")
        return "\n".join(lines)

    def _run_copilot(self, prompt: str) -> str:
        template = self.config.copilot_command_template
        if "{prompt}" in template:
            command = template.replace("{prompt}", prompt.replace('"', '\\"'))
            proc = subprocess.run(
                command,
                shell=True,
                text=True,
                capture_output=True,
                timeout=self.config.request_timeout_seconds,
            )
        else:
            proc = subprocess.run(
                template,
                shell=True,
                text=True,
                input=prompt,
                capture_output=True,
                timeout=self.config.request_timeout_seconds,
            )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            raise RuntimeError(stderr or stdout or f"exit-code={proc.returncode}")
        output = (proc.stdout or "").strip() or (proc.stderr or "").strip()
        if not output:
            raise RuntimeError("Copilot command returned empty output.")
        return output

    def _send_text(self, chat_id: int, text: str) -> None:
        chunks = _chunk_text(text, max_chars=3900)
        for chunk in chunks:
            self._telegram(
                "sendMessage",
                {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
            )

    def _telegram(self, method: str, payload: dict[str, Any]) -> Any:
        with httpx.Client(timeout=self.config.request_timeout_seconds) as client:
            response = client.post(f"{self.api_base}/{method}", json=payload)
        response.raise_for_status()
        body = response.json()
        if not body.get("ok"):
            raise RuntimeError(f"Telegram API rejected request: {body}")
        return body.get("result")


def _chunk_text(text: str, *, max_chars: int) -> list[str]:
    normalized = text.strip()
    if len(normalized) <= max_chars:
        return [normalized]
    chunks: list[str] = []
    cursor = 0
    while cursor < len(normalized):
        chunks.append(normalized[cursor : cursor + max_chars])
        cursor += max_chars
    return chunks


def main() -> None:
    config = BridgeConfig.from_env()
    TelegramCopilotBridge(config).run_forever()


if __name__ == "__main__":
    main()
