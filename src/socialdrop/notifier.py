from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Notifier(ABC):
    @abstractmethod
    async def send(self, event: str, payload: dict[str, Any]) -> None:
        ...


class DiscordWebhook(Notifier):
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    async def send(self, event: str, payload: dict[str, Any]) -> None:
        import httpx

        content = f"**{event}**"
        if payload.get("drop_id"):
            content += f"\ndrop_id: `{payload['drop_id']}`"
        if payload.get("platform"):
            content += f"\nplatform: `{payload['platform']}`"
        if payload.get("message"):
            content += f"\n{payload['message']}"
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                self.webhook_url,
                json={"content": content},
            )


class EmailSMTP(Notifier):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addrs: list[str],
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs

    async def send(self, event: str, payload: dict[str, Any]) -> None:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = f"socialdrop {event}"
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        body = f"{event}\n\n"
        if payload.get("drop_id"):
            body += f"drop_id: {payload['drop_id']}\n"
        if payload.get("platform"):
            body += f"platform: {payload['platform']}\n"
        if payload.get("message"):
            body += f"{payload['message']}\n"
        msg.set_content(body)

        with smtplib.SMTP(self.host, self.port) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
