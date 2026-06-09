"""Tests for the HTTP transport, focused on firmware quirk handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.geekmagic.const import MODEL_PRO
from custom_components.geekmagic.profiles import detect_firmware_profile
from custom_components.geekmagic.transport import DeviceTransport


def _malformed_error(message: str) -> aiohttp.ClientResponseError:
    """Build a 400 error mimicking GeekMagic firmware's malformed HTTP."""
    return aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=400,
        message=message,
    )


def _session_raising(error: Exception) -> MagicMock:
    """Return a mock session whose GET raises ``error`` on enter."""
    response = MagicMock()
    response.__aenter__ = AsyncMock(side_effect=error)
    response.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.get = MagicMock(return_value=response)
    return session


@pytest.mark.asyncio
async def test_get_json_falls_back_on_data_after_close() -> None:
    """Pro firmware's 'Data after Connection: close' must not break get_json.

    Regression test for issue #155: a stricter bundled aiohttp started
    rejecting the Pro firmware's malformed responses, which broke firmware
    detection because get_json (unlike get_text/get_bytes) had no raw fallback.
    """
    transport = DeviceTransport("192.168.1.100")
    transport.session = _session_raising(_malformed_error("Data after `Connection: close`"))

    with patch.object(
        transport,
        "raw_http_get",
        AsyncMock(return_value=b'{"m": "SmallTV-PRO", "v": "V3.4.82EN"}'),
    ) as raw_get:
        data = await transport.get_json("/v.json")

    raw_get.assert_awaited_once_with("/v.json")
    assert data == {"m": "SmallTV-PRO", "v": "V3.4.82EN"}


@pytest.mark.asyncio
async def test_get_json_falls_back_on_duplicate_content_length() -> None:
    """Ultra firmware's 'Duplicate Content-Length' must also fall back cleanly."""
    transport = DeviceTransport("192.168.1.100")
    transport.session = _session_raising(_malformed_error("Duplicate Content-Length header"))

    with patch.object(
        transport,
        "raw_http_get",
        AsyncMock(return_value=b'{"theme": "3"}'),
    ):
        data = await transport.get_json("/app.json")

    assert data == {"theme": "3"}


@pytest.mark.asyncio
async def test_get_json_reraises_unrelated_response_error() -> None:
    """A genuine HTTP error (e.g. 404) must still propagate, not silently fall back."""
    transport = DeviceTransport("192.168.1.100")
    not_found = aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=404,
        message="Not Found",
    )
    transport.session = _session_raising(not_found)

    with (
        patch.object(transport, "raw_http_get", AsyncMock()) as raw_get,
        pytest.raises(aiohttp.ClientResponseError),
    ):
        await transport.get_json("/missing.json")

    raw_get.assert_not_called()


@pytest.mark.asyncio
async def test_detection_identifies_pro_through_malformed_response() -> None:
    """Detection must still recognize a Pro device when /v.json is malformed.

    Without the get_json fallback the Pro firmware would be misdetected as a
    non-Pro profile, which then issues /set?img= and gets a FAIL from the
    device (the user-visible symptom in issue #155).
    """
    transport = DeviceTransport("192.168.1.100")
    transport.session = _session_raising(_malformed_error("Data after `Connection: close`"))

    with patch.object(
        transport,
        "raw_http_get",
        AsyncMock(return_value=b'{"m": "SmallTV-PRO", "v": "V3.4.82EN"}'),
    ):
        profile = await detect_firmware_profile(transport)

    assert profile.capabilities.profile_id == MODEL_PRO
