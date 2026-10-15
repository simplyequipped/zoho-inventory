import time

import httpx
import pytest

from zoho_inventory.client import ZohoError
from conftest import ACCOUNTS, API, item, page


def test_adds_org_and_bearer(client, mock):
    route = mock.get(f"{API}/items").respond(json=page([item(1)], False))
    client.get("/items")
    req = route.calls.last.request
    assert req.url.params["organization_id"] == "999"
    assert req.headers["Authorization"] == "Zoho-oauthtoken at-valid"


def test_paginate_follows_has_more_page(client, mock):
    def responder(request):
        p = int(request.url.params["page"])
        assert request.url.params["per_page"] == "200"
        if p == 1:
            return httpx.Response(200, json=page([item(1), item(2)], True))
        return httpx.Response(200, json=page([item(3)], False))

    mock.get(f"{API}/items").mock(side_effect=responder)
    rows = list(client.paginate("/items", "items"))
    assert [r["sku"] for r in rows] == ["SKU-1", "SKU-2", "SKU-3"]


def test_paginate_without_page_context_stops_on_short_page(client, mock):
    mock.get(f"{API}/items").respond(json={"code": 0, "items": [item(1)]})
    rows = list(client.paginate("/items", "items", per_page=2))
    assert len(rows) == 1


def test_zoho_error_envelope(client, mock):
    mock.get(f"{API}/items/1").respond(400, json={"code": 1002, "message": "Item does not exist."})
    with pytest.raises(ZohoError) as e:
        client.get("/items/1")
    assert e.value.code == 1002
    assert "does not exist" in str(e.value)


def test_401_refreshes_once_and_retries(client, mock):
    calls = {"n": 0}

    def responder(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(401, json={"code": 57, "message": "You are not authorized"})
        assert request.headers["Authorization"] == "Zoho-oauthtoken at-new"
        return httpx.Response(200, json=page([item(1)], False))

    mock.get(f"{API}/items").mock(side_effect=responder)
    mock.post(f"{ACCOUNTS}/oauth/v2/token").respond(json={"access_token": "at-new", "expires_in": 3600})
    body = client.get("/items")
    assert body["items"][0]["sku"] == "SKU-1"
    assert calls["n"] == 2


def test_429_backs_off_then_succeeds(client, mock, monkeypatch):
    slept = []
    monkeypatch.setattr("zoho_inventory.client.time.sleep", lambda s: slept.append(s))
    seq = iter([httpx.Response(429, json={"code": 429, "message": "slow down"}), httpx.Response(200, json=page([], False))])
    mock.get(f"{API}/items").mock(side_effect=lambda r: next(seq))
    client.get("/items")
    assert slept == [2]


def test_dry_run_skips_writes_but_sends_reads(client, mock, capsys):
    client.dry_run = True
    post = mock.post(f"{API}/items")
    get = mock.get(f"{API}/items").respond(json=page([], False))
    res = client.post("/items", {"name": "x"})
    client.get("/items")
    assert res["dry_run"] is True
    assert not post.called
    assert get.called
    assert "[dry-run] POST" in capsys.readouterr().err
