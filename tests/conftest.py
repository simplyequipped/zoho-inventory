import json
import time

import httpx
import pytest
import respx

from zoho_inventory.config import Credentials, Settings
from zoho_inventory.client import ZohoClient
from zoho_inventory.ratelimit import RateLimiter

ACCOUNTS = "https://accounts.zoho.com"
API = "https://www.zohoapis.com/inventory/v1"


@pytest.fixture
def tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("ZOHO_INVENTORY_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ZOHO_INVENTORY_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path


@pytest.fixture
def creds(tmp_dirs):
    c = Credentials(
        client_id="cid",
        client_secret="sec",
        refresh_token="rt",
        organization_id="999",
        access_token="at-valid",
        access_expires_at=time.time() + 3600,
    )
    c.save()
    return c


@pytest.fixture
def limiter(tmp_dirs):
    return RateLimiter(rpm=1000, daily=100000, state_path=tmp_dirs / "cache" / "rl.json")


@pytest.fixture
def client(creds, limiter):
    return ZohoClient(creds=creds, settings=Settings(), limiter=limiter, http=httpx.Client())


@pytest.fixture
def mock():
    with respx.mock(assert_all_called=False) as m:
        yield m


def item(i, sku=None):
    return {"item_id": f"9000000000000{i:05d}", "name": f"Item {i}", "sku": sku or f"SKU-{i}", "purchase_rate": 1.0 * i}


def page(items, has_more):
    return {"code": 0, "message": "success", "items": items, "page_context": {"has_more_page": has_more}}
