"""Additional auditor regressions for boundaries and shortcuts outside the five scenarios."""

import csv
import hashlib
import io
import json
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from .main import app
from .models import MAX_CENTS, Invoice, JournalEntryLine
from .entity_resolver import resolve_counterparty
from .test_hard_pass import alien_payload
from scripts.audit_static import audit

client = TestClient(app)


def test_static_source_guards():
    assert audit()["failures"] == []


@pytest.mark.parametrize("bad_record", [None, "not an object", []])
def test_non_object_invoice_is_structured_validation_error(bad_record):
    payload = alien_payload()
    payload["invoices"] = [bad_record]
    response = client.post("/api/reconcile", json=payload)
    assert response.status_code == 422
    assert response.json()["status"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("bad_fee", [True, 1000.0, "1000", 10.1])
def test_wire_fee_options_require_actual_integer_cents(bad_fee):
    payload = alien_payload()
    payload["config"] = {"wire_fee_options_cents": [0, bad_fee]}
    assert client.post("/api/reconcile", json=payload).status_code == 422


@pytest.mark.parametrize(
    "field", ["wire_fee_band_min_cents", "wire_fee_band_max_cents"]
)
def test_fee_band_requires_integer_cents(field):
    payload = alien_payload()
    payload["config"] = {
        "wire_fee_band_min_cents": 0,
        "wire_fee_band_max_cents": 1000,
        field: 0.5,
    }
    assert client.post("/api/reconcile", json=payload).status_code == 422


@pytest.mark.parametrize("amount", [1.0, True, "100"])
def test_journal_rejects_coercible_non_integer_currency(amount):
    with pytest.raises(ValidationError):
        JournalEntryLine(gl_account="1010", account_name="Cash", debit_cents=amount)


def test_generic_abbreviations_still_reject_ambiguous_counterparties():
    invoices = [
        Invoice(
            invoice_id=f"OTHER-{i}",
            customer_id=f"C-{i}",
            customer_name=name,
            invoice_date="2026-10-01",
            due_date="2026-10-31",
            amount_cents=100,
        )
        for i, name in enumerate(("Orbital Robotics Labs", "Orbital Robotic Labs"))
    ]
    resolved = resolve_counterparty("FEDWIRE ORBITAL ROB LABS", invoices)
    assert resolved["customer_id"] is None
    assert "Ambiguous" in resolved["reason"]


def test_duplicate_csv_headers_rejected_instead_of_overwritten():
    content = "deposit_id,deposit_date,raw_payer_memo,amount_cents,amount_cents\nOTHER,2026-10-10,ROBOTICS,100,200\n"
    response = client.post("/api/import-csv?kind=deposits", content=content)
    assert response.status_code == 422
    assert "duplicate column" in response.json()["detail"]


def test_signed_64_bit_boundary_remains_exact_in_solver_and_exporter():
    payload = alien_payload()
    payload["invoices"] = [payload["invoices"][0]]
    payload["invoices"][0]["amount_cents"] = MAX_CENTS
    payload["deposits"][0]["amount_cents"] = MAX_CENTS
    payload["config"] = {"allow_wire_fees": False}
    response = client.post("/api/reconcile", json=payload)
    assert response.status_code == 200
    match = response.json()["matches"][0]
    assert match["status"] == "MATCHED"
    assert match["debits_cents"] == match["credits_cents"] == MAX_CENTS
    assert match["variance_cents"] == 0
    exported = client.post("/api/export-journal-csv", json=payload)
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert rows[0]["Debits"] == "92233720368547758.07"
    payload["invoices"][0]["amount_cents"] = MAX_CENTS + 1
    assert client.post("/api/reconcile", json=payload).status_code == 422


def test_fresh_audit_export_includes_source_hash_and_actual_recomputed_result():
    payload = alien_payload()
    response = client.post("/api/export-audit-json", json=payload)
    assert response.status_code == 200
    document = response.json()
    digest = hashlib.sha256(
        json.dumps(document["source"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert document["source_sha256"] == digest
    assert document["result"]["matches"][0]["status"] == "MATCHED"
    assert document["result"]["nodes_explored"] > 1
    assert (
        float(response.headers["X-Solver-Time-Ms"])
        == document["result"]["solve_time_ms"]
    )
    payload["deposits"][0]["amount_cents"] += 1
    changed = client.post("/api/export-audit-json", json=payload).json()
    assert changed["result"]["matches"][0]["status"] == "UNMATCHED_EXCEPTION"
    assert changed["source_sha256"] != digest
    assert changed["result"]["matches"][0]["journal_lines"] == []


@pytest.mark.parametrize("invalid_terms", [None, [], 7])
def test_malformed_discount_terms_return_422_instead_of_server_error(invalid_terms):
    payload = alien_payload()
    payload["invoices"][0]["discount_terms"] = invalid_terms
    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/reconcile", json=payload
    )
    assert response.status_code == 422
    assert response.json()["status"] == "VALIDATION_ERROR"
