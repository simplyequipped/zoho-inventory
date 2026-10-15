"""Descriptors for API modules that get generic commands.

Each entry drives a command group with list/get/create/update/delete plus a
`do` command for the POST /{path}/{id}/{action} status endpoints Zoho uses
(confirm, void, cancel, ...). Adding a module is one more entry here. Field
lists are for `zoho docs <module>`; the API accepts anything in Zoho's docs
through --json.

The two keys to get right are list_key (the array in a list response) and
single_key (the object in a get/create response). Zoho is mostly regular but
not entirely, so each one is set explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Module:
    name: str            # command group name
    path: str            # API path, no leading slash
    list_key: str
    single_key: str
    id_field: str
    columns: list[str]
    doc: str             # reference URL
    summary: str
    fields: list[str] = field(default_factory=list)     # notable request fields for docs
    actions: list[str] = field(default_factory=list)    # POST /{path}/{id}/{action}
    search_params: list[str] = field(default_factory=lambda: ["search_text", "status"])


MODULES: dict[str, Module] = {}


def _add(m: Module) -> None:
    MODULES[m.name] = m


_add(Module(
    name="salesorders", path="salesorders", list_key="salesorders", single_key="salesorder",
    id_field="salesorder_id",
    columns=["salesorder_id", "salesorder_number", "date", "customer_name", "status", "total", "reference_number"],
    doc="https://www.zoho.com/inventory/api/v1/salesorders/",
    summary="Sales orders. Shopify-synced orders show up here.",
    fields=["customer_id*", "date", "reference_number", "line_items[]{item_id, quantity, rate}", "notes", "shipment_date", "is_inclusive_tax"],
    actions=["confirmed", "void", "markasopen"],
    search_params=["search_text", "status", "salesorder_number", "customer_id", "date", "reference_number"],
))

_add(Module(
    name="purchaseorders", path="purchaseorders", list_key="purchaseorders", single_key="purchaseorder",
    id_field="purchaseorder_id",
    columns=["purchaseorder_id", "purchaseorder_number", "date", "vendor_name", "status", "total", "reference_number"],
    doc="https://www.zoho.com/inventory/api/v1/purchaseorders/",
    summary="Purchase orders to vendors.",
    fields=["vendor_id*", "date", "reference_number", "line_items[]{item_id, quantity, rate}", "delivery_date", "notes"],
    actions=["issued", "cancelled"],
    search_params=["search_text", "status", "purchaseorder_number", "vendor_id", "date"],
))

_add(Module(
    name="purchasereceives", path="purchasereceives", list_key="purchasereceives", single_key="purchasereceive",
    id_field="receive_id",
    columns=["receive_id", "receive_number", "date", "vendor_name", "purchaseorder_number", "status"],
    doc="https://www.zoho.com/inventory/api/v1/purchasereceives/",
    summary="Receiving against a purchase order; this is what adds parts to stock.",
    fields=["purchaseorder_id* (query param on create)", "date", "line_items[]{line_item_id, quantity}", "notes"],
    search_params=["search_text"],
))

_add(Module(
    name="contacts", path="contacts", list_key="contacts", single_key="contact",
    id_field="contact_id",
    columns=["contact_id", "contact_name", "contact_type", "company_name", "email", "status"],
    doc="https://www.zoho.com/inventory/api/v1/contacts/",
    summary="Customers and vendors.",
    fields=["contact_name*", "contact_type (customer|vendor)", "company_name", "email", "phone", "billing_address{}", "shipping_address{}", "contact_persons[]"],
    actions=["active", "inactive"],
    search_params=["search_text", "status", "contact_type", "contact_name", "email"],
))

_add(Module(
    name="itemgroups", path="itemgroups", list_key="itemgroups", single_key="item_group",
    id_field="group_id",
    columns=["group_id", "group_name", "status", "unit", "product_type"],
    doc="https://www.zoho.com/inventory/api/v1/itemgroups/",
    summary="Item groups: one product with attribute variants (color, band).",
    fields=["group_name*", "unit", "attribute_name1..3", "items[]{name, sku, rate, purchase_rate, attribute_option_name1..3}"],
    actions=["active", "inactive"],
))

_add(Module(
    name="locations", path="locations", list_key="locations", single_key="location",
    id_field="location_id",
    columns=["location_id", "location_name", "type", "status", "is_primary"],
    doc="https://www.zoho.com/inventory/api/v1/locations/",
    summary="Warehouses / locations. Most line items accept a location_id.",
    fields=["location_name*", "type", "address{}"],
    actions=["active", "inactive", "markasprimary"],
    search_params=[],
))

_add(Module(
    name="packages", path="packages", list_key="packages", single_key="package",
    id_field="package_id",
    columns=["package_id", "package_number", "date", "customer_name", "salesorder_number", "status"],
    doc="https://www.zoho.com/inventory/api/v1/packages/",
    summary="Packages created from sales orders, before shipment.",
    fields=["salesorder_id* (query param on create)", "date", "line_items[]{so_line_item_id, quantity}"],
    search_params=["search_text", "status"],
))

_add(Module(
    name="shipmentorders", path="shipmentorders", list_key="shipmentorders", single_key="shipmentorder",
    id_field="shipment_id",
    columns=["shipment_id", "shipment_number", "date", "customer_name", "status", "tracking_number"],
    doc="https://www.zoho.com/inventory/api/v1/shipmentorders/",
    summary="Shipments for packages.",
    fields=["salesorder_id*, package_ids* (query params on create)", "date", "delivery_method", "tracking_number"],
    actions=["delivered"],
))

_add(Module(
    name="invoices", path="invoices", list_key="invoices", single_key="invoice",
    id_field="invoice_id",
    columns=["invoice_id", "invoice_number", "date", "customer_name", "status", "total", "balance"],
    doc="https://www.zoho.com/inventory/api/v1/invoices/",
    summary="Invoices.",
    fields=["customer_id*", "date", "due_date", "line_items[]{item_id, quantity, rate}", "reference_number"],
    actions=["sent", "void", "draft"],
    search_params=["search_text", "status", "invoice_number", "customer_id", "date"],
))

_add(Module(
    name="bills", path="bills", list_key="bills", single_key="bill",
    id_field="bill_id",
    columns=["bill_id", "bill_number", "date", "vendor_name", "status", "total", "balance"],
    doc="https://www.zoho.com/inventory/api/v1/bills/",
    summary="Vendor bills.",
    fields=["vendor_id*", "bill_number*", "date", "due_date", "line_items[]{item_id, quantity, rate}"],
    actions=["void", "open"],
    search_params=["search_text", "status", "bill_number", "vendor_id"],
))

_add(Module(
    name="pricelists", path="pricebooks", list_key="pricebooks", single_key="pricebook",
    id_field="pricebook_id",
    columns=["pricebook_id", "name", "pricebook_type", "status", "currency_code"],
    doc="https://www.zoho.com/inventory/api/v1/price-lists/",
    summary="Price lists (Zoho's API still calls them pricebooks).",
    fields=["name*", "pricebook_type (fixed_percentage|per_item)", "sales_or_purchase_type", "percentage", "pricebook_items[]"],
    actions=["active", "inactive"],
    search_params=["status"],
))

_add(Module(
    name="users", path="users", list_key="users", single_key="user",
    id_field="user_id",
    columns=["user_id", "name", "email", "user_role", "status"],
    doc="https://www.zoho.com/inventory/api/v1/users/",
    summary="Organization users.",
    fields=["name*", "email*", "user_role"],
    actions=["active", "inactive", "invite"],
    search_params=["filter_by"],
))
