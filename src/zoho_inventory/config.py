"""Paths, credentials, and settings.

Credentials live in a single JSON file, mode 0600, outside the repo:

    ~/.config/zoho-inventory/credentials.json
    {
      "client_id": "...",
      "client_secret": "...",
      "refresh_token": "...",
      "organization_id": "...",
      "accounts_url": "https://accounts.zoho.com",
      "api_domain":   "https://www.zohoapis.com",
      "access_token": "...",        # cached, managed by auth.py
      "access_expires_at": 1760000000.0
    }

Settings (non-secret) live next to it in settings.json and can be overridden
by environment variables:

    ZOHO_INVENTORY_CONFIG_DIR     directory holding both files   (default ~/.config/zoho-inventory)
    ZOHO_INVENTORY_CACHE_DIR      rate-limiter state             (default ~/.cache/zoho-inventory)
    ZOHO_INVENTORY_RPM            requests per minute budget     (default 60; Zoho allows 100)
    ZOHO_INVENTORY_DAILY          requests per day budget        (default 1000; set to your plan)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

DEFAULT_ACCOUNTS_URL = "https://accounts.zoho.com"
DEFAULT_API_DOMAIN = "https://www.zohoapis.com"
API_PREFIX = "/inventory/v1"


def config_dir() -> Path:
    return Path(os.environ.get("ZOHO_INVENTORY_CONFIG_DIR", Path.home() / ".config" / "zoho-inventory"))


def cache_dir() -> Path:
    return Path(os.environ.get("ZOHO_INVENTORY_CACHE_DIR", Path.home() / ".cache" / "zoho-inventory"))


def credentials_path() -> Path:
    return config_dir() / "credentials.json"


def settings_path() -> Path:
    return config_dir() / "settings.json"


@dataclass
class Credentials:
    client_id: str
    client_secret: str
    refresh_token: str
    organization_id: str = ""
    accounts_url: str = DEFAULT_ACCOUNTS_URL
    api_domain: str = DEFAULT_API_DOMAIN
    access_token: str = ""
    access_expires_at: float = 0.0

    @classmethod
    def load(cls) -> "Credentials":
        p = credentials_path()
        if not p.exists():
            raise ConfigError(
                f"No credentials at {p}. Run `zoho auth init` first."
            )
        data = json.loads(p.read_text())
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self) -> None:
        p = credentials_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)


@dataclass
class Settings:
    requests_per_minute: int = 60
    requests_per_day: int = 1000
    daily_warn_fraction: float = 0.8
    default_per_page: int = 200
    sku_match: str = "exact"  # or "fuzzy"
    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        p = settings_path()
        if p.exists():
            data = json.loads(p.read_text())
            for k, v in data.items():
                if k in cls.__dataclass_fields__:
                    setattr(s, k, v)
                else:
                    s.extra[k] = v
        if v := os.environ.get("ZOHO_INVENTORY_RPM"):
            s.requests_per_minute = int(v)
        if v := os.environ.get("ZOHO_INVENTORY_DAILY"):
            s.requests_per_day = int(v)
        return s

    def save(self) -> None:
        p = settings_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        d = asdict(self)
        d.pop("extra")
        p.write_text(json.dumps(d, indent=2) + "\n")


class ConfigError(Exception):
    pass
