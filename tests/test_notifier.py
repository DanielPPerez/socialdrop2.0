from typing import Any

import pytest

from socialdrop.notifier import DiscordWebhook, EmailSMTP, Notifier


class DummyNotifier(Notifier):
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def send(self, event: str, payload: dict) -> None:
        self.events.append((event, payload))


@pytest.mark.asyncio
async def test_dummy_notifier():
    n = DummyNotifier()
    await n.send("publish.succeeded", {"drop_id": "1"})
    assert n.events == [("publish.succeeded", {"drop_id": "1"})]


@pytest.mark.asyncio
async def test_discord_webhook(monkeypatch: pytest.MonkeyPatch):
    called: dict[str, Any] = {}

    async def fake_post(self, url, **kwargs):
        called["url"] = url
        called["payload"] = kwargs.get("json")

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    notifier = DiscordWebhook("https://discord.com/webhook/test")
    await notifier.send("publish.failed", {"drop_id": "1", "platform": "youtube"})
    assert called["url"] == "https://discord.com/webhook/test"
    assert "publish.failed" in called["payload"]["content"]


@pytest.mark.asyncio
async def test_email_smtp(monkeypatch: pytest.MonkeyPatch):
    called: dict[str, Any] = {}

    class DummySMTP:
        def __init__(self, host, port):
            called["host"] = host
            called["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self):
            pass

        def login(self, username, password):
            called["username"] = username
            called["password"] = password

        def send_message(self, msg):
            called["subject"] = msg["Subject"]

    import smtplib

    monkeypatch.setattr(smtplib, "SMTP", DummySMTP)
    notifier = EmailSMTP(
        host="smtp.test",
        port=587,
        username="user",
        password="pass",
        from_addr="from@test",
        to_addrs=["to@test"],
    )
    await notifier.send("publish.succeeded", {"drop_id": "1"})
    assert called["subject"] == "socialdrop publish.succeeded"
