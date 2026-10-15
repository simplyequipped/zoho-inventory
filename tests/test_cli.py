import json

import httpx
import pytest
from typer.testing import CliRunner

from zoho_inventory.cli import app
from conftest import API, item, page

runner = CliRunner()


@pytest.fixture(autouse=True)
def _env(creds, tmp_dirs):
    # creds fixture writes the credentials file under the temp config dir
    yield


def run(*args):
    return runner.invoke(app, list(args))


def test_items_list_json_when_not_tty(mock):
    mock.get(f"{API}/items").respond(json=page([item(1), item(2)], False))
    r = run("items", "list")
    assert r.exit_code == 0, r.output
    rows = json.loads(r.output)
    assert [x["sku"] for x in rows] == ["SKU-1", "SKU-2"]


def test_items_list_table(mock):
    mock.get(f"{API}/items").respond(json=page([item(1)], False))
    r = run("--format", "table", "items", "list")
    assert r.exit_code == 0
    assert "SKU-1" in r.output and "item_id" in r.output


def test_items_update_by_sku_exact(mock):
    def lister(request):
        assert request.url.params["sku"] == "RNODE-T3S3"
        return httpx.Response(200, json=page([item(7, "RNODE-T3S3")], False))

    mock.get(f"{API}/items").mock(side_effect=lister)
    put = mock.put(f"{API}/items/900000000000000007").respond(json={"code": 0, "item": {"item_id": "900000000000000007", "purchase_rate": 21.27}})
    r = run("items", "update", "RNODE-T3S3", "--purchase-rate", "21.27")
    assert r.exit_code == 0, r.output
    assert json.loads(put.calls.last.request.content) == {"purchase_rate": 21.27}


def test_items_update_rejects_ambiguous_sku(mock):
    mock.get(f"{API}/items").respond(json=page([item(1, "RNODE-A"), item(2, "RNODE-B")], False))
    r = run("items", "update", "RNODE", "--fuzzy", "--purchase-rate", "1")
    assert r.exit_code != 0
    assert "2 items match" in str(r.exception)


def test_items_update_by_id_skips_lookup(mock):
    lst = mock.get(f"{API}/items")
    put = mock.put(f"{API}/items/900000000000000001").respond(json={"code": 0, "item": {}})
    r = run("items", "update", "900000000000000001", "--rate", "150")
    assert r.exit_code == 0
    assert not lst.called and put.called


def test_items_delete_requires_yes(mock):
    r = run("items", "delete", "900000000000000001")
    assert r.exit_code == 2


def test_items_create_merges_json_and_flags(mock, tmp_path):
    f = tmp_path / "i.json"
    f.write_text(json.dumps({"name": "Battery", "unit": "pcs", "purchase_rate": 5.00}))
    post = mock.post(f"{API}/items").respond(json={"code": 0, "item": {"item_id": "1"}})
    r = run("items", "create", "--json", str(f), "--sku", "BAT-2000", "--purchase-rate", "5.75")
    assert r.exit_code == 0, r.output
    body = json.loads(post.calls.last.request.content)
    assert body["name"] == "Battery" and body["sku"] == "BAT-2000" and body["purchase_rate"] == 5.75
    assert body["item_type"] == "inventory"


def test_api_get_all_pages(mock):
    seq = iter([page([item(1)], True), page([item(2)], False)])
    mock.get(f"{API}/items").mock(side_effect=lambda r: httpx.Response(200, json=next(seq)))
    r = run("api", "GET", "/items", "--all")
    assert r.exit_code == 0, r.output
    assert len(json.loads(r.output)) == 2


def test_api_post_with_data_and_dry_run(mock):
    post = mock.post(f"{API}/compositeitems")
    r = run("--dry-run", "api", "POST", "/compositeitems", "--data", '{"name": "RNode"}')
    assert r.exit_code == 0, r.output
    assert not post.called


def test_api_delete_requires_yes(mock):
    r = run("api", "DELETE", "/items/1")
    assert r.exit_code == 2


def test_auth_status(mock):
    r = run("auth", "status")
    assert r.exit_code == 0, r.output
    d = json.loads(r.output)
    assert d["organization_id"] == "999" and d["access_token_cached"] is True
