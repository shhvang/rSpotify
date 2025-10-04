"""Unit tests for the bot OAuth callback helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from rspotify_bot.bot import RSpotifyBot


class DummyOAuthCollection:
    """Simple in-memory stand-in for the oauth_codes collection."""

    def __init__(self, document: dict) -> None:
        self._document = document
        self.deleted_ids: list[ObjectId] = []

    def find_one(self, query: dict) -> dict | None:
        if query.get("_id") == self._document.get("_id"):
            return dict(self._document)
        return None

    def delete_one(self, query: dict) -> SimpleNamespace:
        self.deleted_ids.append(query.get("_id"))
        return SimpleNamespace(deleted_count=1)


@pytest.mark.asyncio
async def test_handle_oauth_code_updates_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bot should persist exchanged tokens using the stored auth code."""

    bot = RSpotifyBot(token="dummy")

    object_id = ObjectId()
    auth_code = "spotify-auth-code"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    oauth_collection = DummyOAuthCollection({
        "_id": object_id,
        "auth_code": auth_code,
    })

    bot.db_service = SimpleNamespace(
        database=SimpleNamespace(oauth_codes=oauth_collection)
    )

    status_message = SimpleNamespace(edit_text=AsyncMock())
    message = SimpleNamespace(reply_text=AsyncMock(return_value=status_message))
    update = SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(id=123456789),
    )
    
    # Add context parameter
    context = SimpleNamespace(user_data={})

    auth_service = SimpleNamespace(
        exchange_code_for_tokens=AsyncMock(
            return_value={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_at": expires_at,
            }
        )
    )
    monkeypatch.setattr(
        "rspotify_bot.services.auth.SpotifyAuthService",
        lambda: auth_service,
    )

    repo_instance = SimpleNamespace(
        update_spotify_tokens=AsyncMock(return_value=True),
        get_user=AsyncMock(return_value={"custom_name": "TestUser"})  # Add get_user mock
    )

    def repo_factory(database):
        assert database is bot.db_service.database
        return repo_instance

    monkeypatch.setattr(
        "rspotify_bot.services.repository.UserRepository",
        repo_factory,
    )

    await bot._handle_oauth_code(update, context, str(object_id), update.effective_user.id)

    auth_service.exchange_code_for_tokens.assert_awaited_once_with(auth_code)
    repo_instance.update_spotify_tokens.assert_awaited_once_with(
        update.effective_user.id,
        "access-token",
        "refresh-token",
        expires_at,
    )
    assert oauth_collection.deleted_ids == [object_id]

    assert status_message.edit_text.await_count == 1
    success_message = status_message.edit_text.await_args.args[0]
    assert "Spotify account connected successfully" in success_message
