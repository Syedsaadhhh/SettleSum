"""CSV ingress conveniences and lossless source-ledger exports; no matching logic."""

import csv
import hashlib
import io
import re
from datetime import date, timedelta
from zipfile import ZipFile, ZIP_DEFLATED
from pydantic import Field
from .models import Schema, Invoice, Deposit, Remittance

INVOICE_COLUMNS = [
    "invoice_id",
    "customer_id",
    "customer_name",
    "invoice_date",
    "due_date",
    "amount_cents",
    "discount_terms",
    "discount_pct",
    "discount_days",
]
DEPOSIT_COLUMNS = [
    "deposit_id",
    "deposit_date",
    "raw_payer_memo",
    "amount_cents",
    "bank_reference",
]
ALIASES = {
    "invoice_number": "invoice_id",
    "customer": "customer_name",
    "customer_number": "customer_id",
    "invoice_amount": "amount",
    "deposit_amount": "amount",
    "clearing_date": "deposit_date",
    "bank_memo": "raw_payer_memo",
    "memo": "raw_payer_memo",
    "terms": "discount_terms",
}


class SourceLedger(Schema):
    # Source exports also work while only one side of a blank ledger is imported.
    invoices: list[Invoice] = Field(default_factory=list, max_length=2000)
    deposits: list[Deposit] = Field(default_factory=list, max_length=500)
    remittances: list[Remittance] = Field(default_factory=list, max_length=1000)


def normalize_headers(headers):
    normalized = []
    for header in headers:
        key = re.sub(r"[^a-z0-9]+", "_", header.strip().lower()).strip("_")
        normalized.append(ALIASES.get(key, key))
    if len(set(normalized)) != len(normalized):
        raise ValueError("CSV contains duplicate column names (including aliases)")
    return normalized


def normalize_row(row, kind):
    if None in row or any(value is None for value in row.values()):
        raise ValueError("CSV row has a different number of fields than its header")
    row = {key: value.strip() for key, value in row.items()}
    if kind == "invoices":
        for field in ("discount_terms", "discount_pct", "discount_days"):
            if not row.get(field):
                row.pop(field, None)
        if not row.get("customer_id") and row.get("customer_name"):
            name = " ".join(row["customer_name"].casefold().split())
            row["customer_id"] = (
                "CUSTOMER-" + hashlib.sha256(name.encode()).hexdigest()[:16]
            )
        if not row.get("due_date") and row.get("invoice_date"):
            terms = re.search(r"net\s*(\d+)", row.get("discount_terms", "Net 30"), re.I)
            days = int(terms[1]) if terms else 30
            if days > 36500:
                raise ValueError("Net terms exceed 100 years")
            row["due_date"] = (
                date.fromisoformat(row["invoice_date"]) + timedelta(days=days)
            ).isoformat()
    return row


def source_csv(records, columns):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow(record.model_dump(mode="json"))
    return stream.getvalue()


def source_archive(payload):
    import json

    stream = io.BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "open_invoices.csv", source_csv(payload.invoices, INVOICE_COLUMNS)
        )
        archive.writestr(
            "bank_deposits.csv", source_csv(payload.deposits, DEPOSIT_COLUMNS)
        )
        archive.writestr(
            "remittance_notes.json",
            json.dumps(
                [r.model_dump(mode="json") for r in payload.remittances], indent=2
            ),
        )
    return stream.getvalue()
