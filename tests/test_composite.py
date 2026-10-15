import json

import httpx
import pytest
from typer.testing import CliRunner

from zoho_inventory.cli import app
from conftest import API, item, page

runner = CliRunner()


@pytest.fixture(autouse=True)
def _env(creds, tmp_dirs):
    yield


def run(*args):
    return runner.invoke(app, list(args))


def comp(i, sku, parts):
    return {
        "composite_item_id": f"8000000000000{i:05d}",
        "name": f"Composite {i}",
        "sku": sku,
        "rate": 150.0,
        "mapped_items": [{"item_id": pid, "sku": psku, "name": psku, "quantity": q} for pid, psku, q in parts],
    }


def cpage(rows, more=False):
    return {"code": 0, "composite_items": rows, "page_context": {"has_more_page": more}}


def test_composite_list_columns(mock):
    mock.get(f"{API}/compositeitems").respond(json=cpage([comp(1, "RNODE-T3S3-BLK", [])]))
    r = run("composite", "list")
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)[0]["sku"] == "RNODE-T3S3-BLK"


def test_composite_create_resolves_part_skus(mock):
    def items(request):
        sku = request.url.params.get("sku")
        return httpx.Response(200, json=page([item(1, "BAT-2000")] if sku == "BAT-2000" else [item(2, "T3S3-915")], False))

    mock.get(f"{API}/items").mock(side_effect=items)
    post = mock.post(f"{API}/compositeitems").respond(json={"code": 0, "composite_item": {"composite_item_id": "1"}})
    r = run("composite", "create", "--name", "RNode T3S3 Black", "--sku", "RNODE-T3S3-BLK", "--rate", "150",
            "--part", "BAT-2000:1", "--part", "T3S3-915:1")
    assert r.exit_code == 0, r.output
    body = json.loads(post.calls.last.request.content)
    assert body["item_type"] == "inventory" and body["combo_type"] == "assembly"
    assert body["mapped_items"] == [
        {"item_id": "900000000000000001", "quantity": 1.0},
        {"item_id": "900000000000000002", "quantity": 1.0},
    ]


def test_composite_create_requires_parts(mock):
    r = run("composite", "create", "--name", "x", "--sku", "y", "--rate", "1")
    assert r.exit_code != 0
    assert "mapped_items is required" in r.output


def test_assemble_builds_line_items_from_mapped_items(mock):
    c = comp(5, "RNODE-T3S3-BLK", [("900000000000000001", "BAT-2000", 1), ("900000000000000003", "PACK-12IN", 2)])
    mock.get(f"{API}/compositeitems").respond(json=cpage([c]))
    mock.get(f"{API}/compositeitems/800000000000000005").respond(json={"code": 0, "composite_item": c})
    post = mock.post(f"{API}/bundles").respond(json={"code": 0, "bundle": {"bundle_id": "77"}})
    r = run("composite", "assemble", "RNODE-T3S3-BLK", "--qty", "4", "--date", "2026-10-15", "--ref", "batch-1")
    assert r.exit_code == 0, r.output
    body = json.loads(post.calls.last.request.content)
    assert body["composite_item_id"] == "800000000000000005"
    assert body["quantity_to_bundle"] == 4
    assert body["is_completed"] is True
    assert body["reference_number"] == "batch-1"
    assert body["line_items"] == [
        {"item_id": "900000000000000001", "quantity_consumed": 4.0},
        {"item_id": "900000000000000003", "quantity_consumed": 8.0},
    ]


def test_assemble_dry_run_sends_nothing(mock):
    c = comp(5, "X", [("900000000000000001", "BAT", 1)])
    mock.get(f"{API}/compositeitems").respond(json=cpage([c]))
    mock.get(f"{API}/compositeitems/800000000000000005").respond(json={"code": 0, "composite_item": c})
    post = mock.post(f"{API}/bundles")
    r = run("--dry-run", "composite", "assemble", "X", "--qty", "1")
    assert r.exit_code == 0, r.output
    assert not post.called


def test_unassemble_requires_yes(mock):
    assert run("composite", "unassemble", "77").exit_code == 2


def test_adjustments_create_lines(mock):
    mock.get(f"{API}/items").respond(json=page([item(1, "BAT-2000")], False))
    post = mock.post(f"{API}/inventoryadjustments").respond(json={"code": 0, "inventory_adjustment": {"inventory_adjustment_id": "5"}})
    r = run("adjustments", "create", "--reason", "cycle count", "--line", "BAT-2000:-2", "--date", "2026-10-15")
    assert r.exit_code == 0, r.output
    body = json.loads(post.calls.last.request.content)
    assert body["adjustment_type"] == "quantity" and body["reason"] == "cycle count"
    assert body["line_items"] == [{"item_id": "900000000000000001", "quantity_adjusted": -2.0}]


def test_generic_module_list_get_do(mock):
    mock.get(f"{API}/salesorders").respond(json={"code": 0, "salesorders": [{"salesorder_id": "1", "salesorder_number": "SO-1", "status": "draft"}], "page_context": {"has_more_page": False}})
    mock.get(f"{API}/salesorders/1").respond(json={"code": 0, "salesorder": {"salesorder_id": "1", "line_items": []}})
    do = mock.post(f"{API}/salesorders/1/confirmed").respond(json={"code": 0, "message": "ok"})
    assert json.loads(run("salesorders", "list", "--status", "draft").output)[0]["salesorder_number"] == "SO-1"
    assert json.loads(run("salesorders", "get", "1").output)["salesorder_id"] == "1"
    assert run("salesorders", "do", "1", "confirmed").exit_code == 0
    assert do.called


def test_generic_create_with_query_param(mock):
    post = mock.post(f"{API}/purchasereceives").respond(json={"code": 0, "purchasereceive": {"receive_id": "9"}})
    r = run("purchasereceives", "create", "--param", "purchaseorder_id=42", "--data", '{"date": "2026-10-15", "line_items": []}')
    assert r.exit_code == 0, r.output
    req = post.calls.last.request
    assert req.url.params["purchaseorder_id"] == "42"
    assert json.loads(req.content)["date"] == "2026-10-15"


def test_docs_markdown_mentions_every_module():
    from zoho_inventory.modules import MODULES
    r = run("docs", "--markdown")
    assert r.exit_code == 0
    for name in MODULES:
        assert f"### {name}" in r.output
    assert "### composite" in r.output
