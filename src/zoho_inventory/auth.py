"""OAuth for a Zoho Self Client.

Flow (one-time):   grant code  --exchange-->  refresh_token (+ access_token)
Flow (every hour): refresh_token --refresh-->  access_token (expires_in 3600)

The refresh token does not expire. The access token is cached in the
credentials file with its absolute expiry; it is reused until it is within
REFRESH_MARGIN seconds of expiring, or Zoho rejects it with HTTP 401, in which
case it is refreshed once and the request retried.

Zoho docs: https://www.zoho.com/accounts/protocol/oauth/self-client/authorization-code-flow.html
"""

from __future__ import annotations

import time

import httpx

from .config import Credentials, DEFAULT_ACCOUNTS_URL

TOKEN_PATH = "/oauth/v2/token"
REFRESH_MARGIN = 60  # seconds before expiry at which we proactively refresh


class AuthError(Exception):
    pass


def _token_request(accounts_url: str, data: dict, http: httpx.Client | None = None) -> dict:
    own = http is None
    http = http or httpx.Client(timeout=30)
    try:
        r = http.post(accounts_url.rstrip("/") + TOKEN_PATH, data=data)
    finally:
        if own:
            http.close()
    try:
        body = r.json()
    except ValueError:
        raise AuthError(f"Token endpoint returned non-JSON ({r.status_code}): {r.text[:200]}")
    if r.status_code != 200 or "error" in body or "access_token" not in body:
        raise AuthError(f"Token endpoint error: {body.get('error', body)}")
    return body


def exchange_grant(
    client_id: str,
    client_secret: str,
    grant_code: str,
    accounts_url: str = DEFAULT_ACCOUNTS_URL,
    http: httpx.Client | None = None,
) -> Credentials:
    """Exchange a Self Client grant code for a refresh token. Grant codes expire
    in minutes, so call this right after generating one in the API console."""
    body = _token_request(
        accounts_url,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": grant_code,
        },
        http,
    )
    if "refresh_token" not in body:
        raise AuthError(
            "Zoho returned an access token but no refresh token. Generate a new grant "
            "code and try again; make sure the client is a Self Client."
        )
    return Credentials(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=body["refresh_token"],
        accounts_url=accounts_url,
        api_domain=body.get("api_domain", Credentials.api_domain),
        access_token=body["access_token"],
        access_expires_at=time.time() + int(body.get("expires_in", 3600)),
    )


def refresh_access_token(creds: Credentials, http: httpx.Client | None = None) -> Credentials:
    body = _token_request(
        creds.accounts_url,
        {
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": creds.refresh_token,
        },
        http,
    )
    creds.access_token = body["access_token"]
    creds.access_expires_at = time.time() + int(body.get("expires_in", 3600))
    if body.get("api_domain"):
        creds.api_domain = body["api_domain"]
    creds.save()
    return creds


def ensure_access_token(creds: Credentials, http: httpx.Client | None = None, force: bool = False) -> str:
    """Return a usable access token, refreshing only when needed."""
    if force or not creds.access_token or time.time() >= creds.access_expires_at - REFRESH_MARGIN:
        refresh_access_token(creds, http)
    return creds.access_token
