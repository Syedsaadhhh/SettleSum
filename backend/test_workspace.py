"""Workspace imports/exports and the Vercel entry point, without changing solver tests."""

import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile
import pytest
from fastapi.testclient import TestClient
from .main import app

client = TestClient(app)


def custom_ledger():
    return {
        "invoices": [
            {
                "invoice_id": "bill-horizon-7",
                "customer_id": "HORIZON",
                "customer_name": "Horizon Hardware Co",
                "invoice_date": "2026-10-01",
                "due_date": "2026-10-31",
                "amount_cents": 420000,
                "discount_terms": "Net 30",
            },
            {
                "invoice_id": "bill-horizon-8",
                "customer_id": "HORIZON",
                "customer_name": "Horizon Hardware Co",
                "invoice_date": "2026-10-02",
                "due_date": "2026-11-01",
                "amount_cents": 380000,
                "discount_terms": "Net 30",
            },
        ],
        "deposits": [
            {
                "deposit_id": "payment-horizon",
                "deposit_date": "2026-10-10",
                "raw_payer_memo": "FEDWIRE CRED HORIZON HARDWARE CO",
                "amount_cents": 798500,
            }
        ],
        "remittances": [],
    }


def test_source_archive_roundtrip_preserves_cents_and_discount_terms():
    ledger = custom_ledger()
    ledger["invoices"][0]["discount_terms"] = "2/10 Net 30"
    response = client.post("/api/export-source-csv", json=ledger)
    assert response.status_code == 200
    assert response.headers["X-Nodes-Explored"] == "0"
    restored = {}
    with ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {
            "open_invoices.csv",
            "bank_deposits.csv",
            "remittance_notes.json",
        }
        for kind, filename in [
            ("invoices", "open_invoices.csv"),
            ("deposits", "bank_deposits.csv"),
        ]:
            response = client.post(
                f"/api/import-csv?kind={kind}", content=archive.read(filename)
            )
            assert response.status_code == 200, response.text
            restored[kind] = response.json()["rows"]
            assert [r["amount_cents"] for r in restored[kind]] == [
                r["amount_cents"] for r in ledger[kind]
            ]
    assert restored["invoices"][0]["discount_pct"] == "0.02"
    assert restored["invoices"][0]["discount_days"] == 10


def test_csv_aliases_and_derived_fields_produce_real_match():
    invoices = "Invoice Number,Customer,Invoice Date,Invoice Amount,Terms\nnew-7,Horizon Hardware Co,2026-10-01,4200,Net 30\nnew-8,Horizon Hardware Co,2026-10-02,3800,Net 30\n"
    deposits = "Deposit ID,Clearing Date,Bank Memo,Deposit Amount\npayment-7,2026-10-10,WIRE HORIZON HARDWARE CO,7985\n"
    inv = client.post("/api/import-csv?kind=invoices", content=invoices)
    dep = client.post("/api/import-csv?kind=deposits", content=deposits)
    assert inv.status_code == dep.status_code == 200
    rows = inv.json()["rows"]
    assert rows[0]["customer_id"] == rows[1]["customer_id"]
    assert rows[0]["due_date"] == "2026-10-31"
    payload = {"invoices": rows, "deposits": dep.json()["rows"]}
    match = client.post("/api/reconcile", json=payload).json()["matches"][0]
    assert match["status"] == "MATCHED"
    assert match["wire_fee_cents"] == 1500
    assert match["variance_cents"] == 0


def test_blank_optional_fields_and_csv_quotes():
    content = 'invoice_id,customer_name,invoice_date,amount,discount_terms,customer_id,due_date,discount_pct,discount_days\ncustom,"Business, Inc",2026-10-01,100,Net 30,,,,\n'
    response = client.post("/api/import-csv?kind=invoices", content=content)
    assert response.status_code == 200, response.text
    assert response.json()["rows"][0]["customer_name"] == "Business, Inc"
    assert response.json()["rows"][0]["discount_pct"] == "0"


@pytest.mark.parametrize("kind", ["invoices", "deposits", "ledger"])
def test_empty_and_partial_workspace_exports(kind):
    response = client.post(f"/api/export-source-csv?kind={kind}", json={})
    assert response.status_code == 200
    ledger = custom_ledger()
    ledger["deposits"] = []
    response = client.post(f"/api/export-source-csv?kind={kind}", json=ledger)
    assert response.status_code == 200
    if kind == "invoices":
        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert rows[0]["amount_cents"] == "420000"


@pytest.mark.parametrize(
    "content",
    [
        "Invoice ID,invoice_id\none,two\n",
        "invoice_id,customer_name,invoice_date,amount\none,Name,2026-10-01,100,extra\n",
        "invoice_id,customer_name,invoice_date,amount,terms\none,Name,9999-12-31,100,Net 30\n",
    ],
)
def test_flexible_csv_still_rejects_ambiguous_or_malformed_rows(content):
    response = client.post("/api/import-csv?kind=invoices", content=content)
    assert response.status_code == 422
    assert response.json()["status"] == "VALIDATION_ERROR"


def test_custom_invoice_id_remittance_context_offline(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    ledger = custom_ledger()
    parsed = client.post(
        "/api/parse-remittance",
        json={
            "text": "Applying $250.00 deduction on BILL-HORIZON-7 for cracked housing",
            "known_invoice_ids": [r["invoice_id"] for r in ledger["invoices"]],
        },
    )
    assert parsed.status_code == 200
    doc = parsed.json()
    assert doc["referenced_invoices"][0]["invoice_id"] == "bill-horizon-7"
    assert doc["referenced_invoices"][0]["deduction_cents"] == 25000
    ledger["remittances"] = [
        {
            key: doc[key]
            for key in (
                "document_id",
                "deposit_id",
                "customer_name",
                "raw_text",
                "referenced_invoices",
            )
        }
    ]
    ledger["deposits"][0]["amount_cents"] = 775000
    match = client.post("/api/reconcile", json=ledger).json()["matches"][0]
    assert match["status"] == "MATCHED"
    assert {r["state"] for r in match["invoices"]} == {"FULL", "REMITTANCE_SHORTPAY"}
    assert (
        sum(
            r["debit_cents"]
            for r in match["journal_lines"]
            if r["gl_account"] == "1220"
        )
        == 25000
    )


def test_vercel_entry_imports_without_frontend_and_reconciles():
    root = Path(__file__).resolve().parents[1]
    code = """
from pathlib import Path
from unittest.mock import patch
exists = Path.exists
with patch.object(Path, "exists", lambda p: False if str(p).endswith("frontend/dist") else exists(p)):
    from api.index import app
from fastapi.testclient import TestClient
import json, sys
assert not any(getattr(route, "name", None) == "terminal" for route in app.routes)
r = TestClient(app).post("/api/reconcile", json=json.loads(sys.stdin.read()))
assert r.status_code == 200, r.text
match = r.json()["matches"][0]
assert match["status"] == "MATCHED" and match["wire_fee_cents"] == 1500
assert match["variance_cents"] == 0
print("Vercel ASGI import and custom reconciliation passed")
"""
    response = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        input=json.dumps(custom_ledger()),
        text=True,
        capture_output=True,
        env={**os.environ, "VERCEL": "1"},
        timeout=30,
    )
    assert response.returncode == 0, response.stdout + response.stderr


def test_vercel_configuration_has_static_and_python_routes():
    config = json.loads(
        (Path(__file__).resolve().parents[1] / "vercel.json").read_text()
    )
    assert (
        config["buildCommand"]
        == "npm --prefix frontend ci && npm --prefix frontend run build"
    )
    assert config["outputDirectory"] == "frontend/dist"
    assert config["rewrites"][0] == {
        "source": "/api/(.*)",
        "destination": "/api/index.py",
    }
