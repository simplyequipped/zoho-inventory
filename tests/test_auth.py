import time

import httpx
import pytest

from zoho_inventory import auth
from zoho_inventory.config import Credentials, credentials_path
from conftest import ACCOUNTS


def test_exchange_grant_stores_refresh_token(tmp_dirs, mock):
    mock.post(f"{ACCOUNTS}/oauth/v2/token").respond(
        json={"access_token": "at1", "refresh_token": "rt1", "expires_in": 3600, "api_domain": "https://www.zohoapis.com", "token_type": "Bearer"}
    )
    c = auth.exchange_grant("cid", "sec", "code123")
    assert c.refresh_token == "rt1"
    assert c.access_token == "at1"
    assert c.access_expires_at > time.time() + 3500
    sent = mock.calls.last.request
    assert b"grant_type=authorization_code" in sent.content
    assert b"code=code123" in sent.content


def test_exchange_without_refresh_token_is_an_error(tmp_dirs, mock):
    mock.post(f"{ACCOUNTS}/oauth/v2/token").respond(json={"access_token": "x", "expires_in": 3600})
    with pytest.raises(auth.AuthError):
        auth.exchange_grant("cid", "sec", "code")


def test_token_error_surfaces(tmp_dirs, mock):
    mock.post(f"{ACCOUNTS}/oauth/v2/token").respond(json={"error": "invalid_code"})
    with pytest.raises(auth.AuthError, match="invalid_code"):
        auth.exchange_grant("cid", "sec", "code")


def test_ensure_reuses_cached_token(creds, mock):
    route = mock.post(f"{ACCOUNTS}/oauth/v2/token")
    tok = auth.ensure_access_token(creds)
    assert tok == "at-valid"
    assert not route.called


def test_ensure_refreshes_when_near_expiry(creds, mock):
    creds.access_expires_at = time.time() + 30  # inside the 60s margin
    mock.post(f"{ACCOUNTS}/oauth/v2/token").respond(json={"access_token": "at2", "expires_in": 3600})
    tok = auth.ensure_access_token(creds)
    assert tok == "at2"
    on_disk = Credentials.load()
    assert on_disk.access_token == "at2"
    assert on_disk.refresh_token == "rt"  # refresh response carries no refresh_token; keep ours


def test_credentials_file_is_private(creds):
    mode = credentials_path().stat().st_mode & 0o777
    assert mode == 0o600
