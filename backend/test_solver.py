"""Mandatory benchmark, changed-input, and malformed-input verification.

Also compares the branch-and-bound search to a tiny independent exhaustive
oracle so pruning and deterministic ranking are verified beyond the benchmark.
"""

import copy
import csv
import io
import itertools
import random
from datetime import date
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from .main import app, sample_data
from .models import ReconcileRequest, Invoice, Deposit, SolverConfig, Remittance
from .solver import solve, COMPLEXITY
from .reconciliation import reconcile

client = TestClient(app)


@pytest.fixture
def payload():
    sample = sample_data()
    return {k: sample[k] for k in ("invoices", "deposits", "remittances")}


def match(result, id):
    return next(m for m in result["matches"] if m["deposit_id"] == id)


def test_normal_benchmark(payload):
    response = client.post("/api/reconcile", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert len(payload["invoices"]) == 36
    assert len({i["customer_id"] for i in payload["invoices"]}) == 6
    assert result["summary"]["matched_count"] == 7
    assert match(result, "DEP-9008")["status"] == "UNMATCHED_EXCEPTION"
    assert not match(result, "DEP-9008")["journal_lines"]
    for m in result["matches"]:
        assert m["nodes_explored"] > 0 and m["solve_time_ms"] >= 0
        if m["status"] == "MATCHED":
            assert m["variance_cents"] == 0
            assert (
                sum(i["value_cents"] for i in m["invoices"]) - m["wire_fee_cents"]
                == m["amount_cents"]
            )
            assert sum(l["debit_cents"] for l in m["journal_lines"]) == sum(
                l["credit_cents"] for l in m["journal_lines"]
            )
            assert m["debits_cents"] == m["credits_cents"]
    assert result["summary"]["unearned_discounts_recovered_cents"] == 16400
    assert result["summary"]["short_pays_cents"] == 34000
    assert result["summary"]["valid_discounts_cents"] == 66400
    assert result["summary"]["wire_fees_cents"] == 5000
    assert result["summary"]["matched_deposits_cents"] == 8798200
    assert result["summary"]["total_nodes_explored"] == sum(
        m["nodes_explored"] for m in result["matches"]
    )
    assert int(response.headers["X-Nodes-Explored"]) == result["nodes_explored"]


def test_changed_input_removed_fee(payload):
    payload["deposits"][0]["amount_cents"] += 1500
    result = reconcile(ReconcileRequest(**payload))
    m = match(result, "DEP-9001")
    assert m["status"] == "MATCHED"
    assert m["wire_fee_cents"] == 0
    assert all(l["gl_account"] != "6120" for l in m["journal_lines"])
    assert m["variance_cents"] == 0


def test_changed_input_discount_window(payload):
    original = reconcile(ReconcileRequest(**payload))
    payload["deposits"][1]["deposit_date"] = "2026-10-19"
    changed = reconcile(ReconcileRequest(**payload))
    before, after = match(original, "DEP-9002"), match(changed, "DEP-9002")
    assert before["status"] == after["status"] == "MATCHED"
    assert {x["state"] for x in before["invoices"]} == {"EARNED_DISCOUNT"}
    assert {x["state"] for x in after["invoices"]} == {"UNEARNED_DISCOUNT"}
    assert any(l["gl_account"] == "4910" for l in before["journal_lines"])
    assert not any(l["gl_account"] == "4910" for l in after["journal_lines"])
    assert (
        sum(
            l["debit_cents"]
            for l in after["journal_lines"]
            if l["gl_account"] == "1215"
        )
        == 44000
    )
    assert changed["summary"]["unearned_discounts_recovered_cents"] == 60400


def test_changed_invoice_date_and_fee_toggle(payload):
    for invoice in payload["invoices"]:
        if invoice["invoice_id"] in ("INV-2026-107", "INV-2026-108"):
            invoice["invoice_date"] = "2026-09-20"
    payload["config"] = {"allow_wire_fees": False}
    result = reconcile(ReconcileRequest(**payload))
    assert all(
        i["state"] == "UNEARNED_DISCOUNT" for i in match(result, "DEP-9002")["invoices"]
    )
    assert match(result, "DEP-9001")["status"] == "UNMATCHED_EXCEPTION"


def test_one_cent_edit_never_forces_match(payload):
    payload["deposits"][0]["amount_cents"] += 1
    result = reconcile(ReconcileRequest(**payload))
    assert match(result, "DEP-9001")["status"] == "UNMATCHED_EXCEPTION"
    assert not match(result, "DEP-9001")["journal_lines"]


def test_no_invoice_reused(payload):
    duplicate = copy.deepcopy(payload["deposits"][5])
    duplicate["deposit_id"] = "NEW-DEPOSIT"
    payload["deposits"].append(duplicate)
    result = reconcile(ReconcileRequest(**payload))
    ids = [i["invoice_id"] for m in result["matches"] for i in m["invoices"]]
    assert len(ids) == len(set(ids))
    assert match(result, "NEW-DEPOSIT")["status"] == "UNMATCHED_EXCEPTION"


@pytest.mark.parametrize("kind", ["invoices", "deposits"])
@pytest.mark.parametrize("content", ["", "\n", "invoice_id,amount\n"])
def test_empty_csv_structured_error(kind, content):
    r = client.post(
        f"/api/import-csv?kind={kind}",
        content=content,
        headers={"Content-Type": "text/csv"},
    )
    assert r.status_code == 422 and r.json()["status"] == "VALIDATION_ERROR"
    assert r.json()["nodes_explored"] == 0


@pytest.mark.parametrize("value", [-1, 0, 2**63, 1.1, True])
def test_invalid_invoice_amount(payload, value):
    payload["invoices"][0]["amount_cents"] = value
    r = client.post("/api/reconcile", json=payload)
    assert r.status_code == 422 and r.json()["status"] == "VALIDATION_ERROR"


def test_negative_csv_amount():
    content = "invoice_id,customer_id,customer_name,invoice_date,due_date,amount\nX,C,Customer,2026-10-01,2026-10-31,-3\n"
    assert (
        client.post("/api/import-csv?kind=invoices", content=content).status_code == 422
    )


def test_duplicate_ids_and_empty_ledger(payload):
    payload["invoices"].append(payload["invoices"][0])
    assert client.post("/api/reconcile", json=payload).status_code == 422
    assert (
        client.post("/api/reconcile", json={"invoices": [], "deposits": []}).status_code
        == 422
    )


def test_unmatchable_and_future_invoice():
    invoice = Invoice(
        invoice_id="arbitrary",
        customer_id="new",
        customer_name="New Customer",
        invoice_date="2026-10-20",
        due_date="2026-11-20",
        amount=1.01,
    )
    dep = Deposit(
        deposit_id="unseen",
        deposit_date="2026-10-15",
        raw_payer_memo="NEW CUSTOMER",
        amount=0.01,
    )
    result = solve(dep, [invoice], SolverConfig(), [])
    assert result["status"] == "UNMATCHED_EXCEPTION"
    assert result["eligible_invoices"] == 0


def test_search_limit_not_presented_as_proven_match(payload):
    payload["config"] = {"max_nodes": 1}
    r = client.post("/api/reconcile", json=payload).json()
    assert any(m["status"] == "SEARCH_LIMIT" for m in r["matches"])
    assert all(not m["journal_lines"] for m in r["matches"])


def test_offline_text_and_pdf_parser(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    text = "Customer: Test Customer\nApplying $340 debit memo DM-442 against Inv #INV-2026-114 for cracked CNC flange"
    r = client.post("/api/parse-remittance", json={"text": text}).json()
    assert r["parser"] == "deterministic-regex"
    assert r["referenced_invoices"][0]["invoice_id"] == "INV-2026-114"
    assert r["referenced_invoices"][0]["deduction_cents"] == 34000
    pdf = (
        Path(__file__).resolve().parent.parent / "sample_data/northstar_remittance.pdf"
    )
    r = client.post(
        "/api/parse-remittance",
        files={"file": ("sample.pdf", pdf.read_bytes(), "application/pdf")},
    )
    assert r.status_code == 200
    assert r.json()["referenced_invoices"][0]["deduction_cents"] == 34000
    assert client.post("/api/parse-remittance", json={"text": ""}).status_code == 422
    assert (
        client.post(
            "/api/parse-remittance",
            content=b"%PDFbroken",
            headers={"Content-Type": "application/pdf"},
        ).status_code
        == 422
    )


def test_journal_and_chargeback_exports(payload):
    for vendor in ["quickbooks", "xero"]:
        r = client.post(f"/api/export-journal-csv?vendor={vendor}", json=payload)
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        rows = list(csv.DictReader(io.StringIO(r.text)))
        assert rows
        if vendor == "quickbooks":
            from decimal import Decimal

            assert sum(Decimal(x["Debits"] or 0) for x in rows) == sum(
                Decimal(x["Credits"] or 0) for x in rows
            )
        else:
            from decimal import Decimal

            assert sum(Decimal(x["Amount"]) for x in rows) == 0
    r = client.post("/api/export-chargebacks-csv", json=payload)
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 2
    assert {x["Amount"] for x in rows} == {"164.00", "340.00"}


def make_invoice(id, cents, due="2026-10-31", pct=0):
    return Invoice(
        invoice_id=id,
        customer_id="C",
        customer_name="Independent Customer",
        invoice_date="2026-10-01",
        due_date=due,
        amount_cents=cents,
        discount_pct=pct,
        discount_days=10 if pct else 0,
    )


def test_exact_cents_custom_band_and_discount_boundary():
    invoice = make_invoice("cent-value", 101, pct=".02")
    d = Deposit(
        deposit_id="any",
        deposit_date="2026-10-11",
        raw_payer_memo="Independent Customer",
        amount_cents=99,
    )
    assert (
        solve(d, [invoice], SolverConfig(allow_wire_fees=False), [])["solution"][
            "invoices"
        ][0]["state"]
        == "EARNED_DISCOUNT"
    )
    d = d.model_copy(update={"deposit_date": date(2026, 10, 12)})
    assert (
        solve(d, [invoice], SolverConfig(allow_wire_fees=False), [])["solution"][
            "invoices"
        ][0]["state"]
        == "UNEARNED_DISCOUNT"
    )
    d = d.model_copy(update={"amount_cents": 97})
    r = solve(
        d,
        [invoice],
        SolverConfig(
            allow_discounts=False, wire_fee_band_min_cents=3, wire_fee_band_max_cents=5
        ),
        [],
    )
    assert r["solution"]["wire_fee_cents"] == 4


def test_lexicographic_ranking_and_remittance():
    invoices = [
        make_invoice("older", 10000, "2026-10-15"),
        make_invoice("newer", 10000),
    ]
    deposit = Deposit(
        deposit_id="not-benchmark",
        deposit_date="2026-10-09",
        amount_cents=10000,
        raw_payer_memo="Independent Customer",
    )
    assert (
        solve(deposit, invoices, SolverConfig(), [])["solution"]["invoices"][0][
            "invoice_id"
        ]
        == "older"
    )
    remit = Remittance(referenced_invoices=[{"invoice_id": "newer"}])
    result = solve(deposit, invoices, SolverConfig(), [remit])
    assert result["solution"]["invoices"][0]["invoice_id"] == "newer"
    assert result["candidate_count"] == 2
    assert len(result["alternatives"]) == 1


def test_many_invoices_no_recursion_crash():
    invoices = [make_invoice(f"new-{i}", 1000 + i) for i in range(1200)]
    dep = Deposit(
        deposit_id="large-upload",
        deposit_date="2026-10-09",
        amount_cents=1000,
        raw_payer_memo="Independent Customer",
    )
    result = solve(dep, invoices, SolverConfig(max_subset_size=1), [])
    assert result["solution"]["invoices"][0]["invoice_id"] == "new-0"


def test_branch_and_bound_matches_independent_exhaustive_oracle():
    random.seed(17)
    for case in range(30):
        invoices = [
            make_invoice(
                f"random-{i}", random.randint(1, 100) * 100, pct=".02" if i % 2 else 0
            )
            for i in range(5)
        ]
        options = [
            [None, ("FULL", x.amount_cents)]
            + (
                [("EARNED_DISCOUNT", x.amount_cents * 98 // 100)]
                if x.discount_pct
                else []
            )
            for x in invoices
        ]
        target = random.randint(1, 200) * 100
        expected = []
        for choices in itertools.product(*options):
            chosen = [(invoices[i], c) for i, c in enumerate(choices) if c]
            if not 1 <= len(chosen) <= 3:
                continue
            fee = sum(c[1] for inv, c in chosen) - target
            if fee not in (0, 1000, 1500):
                continue
            rank = (
                0,
                sum(COMPLEXITY[c[0]] for inv, c in chosen),
                int(fee != 0),
                tuple(str(inv.due_date) for inv, c in chosen),
                fee,
                tuple((inv.invoice_id, c[0], "") for inv, c in chosen),
            )
            expected.append((rank, [(inv.invoice_id, c[0]) for inv, c in chosen], fee))
        dep = Deposit(
            deposit_id=f"generated-{case}",
            deposit_date="2026-10-09",
            raw_payer_memo="Independent Customer",
            amount_cents=target,
        )
        r = solve(
            dep,
            invoices,
            SolverConfig(max_subset_size=3, wire_fee_options_cents=[0, 1000, 1500]),
            [],
        )
        assert r["candidate_count"] == len(expected)
        if expected:
            best = min(expected)
            assert [
                (x["invoice_id"], x["state"]) for x in r["solution"]["invoices"]
            ] == best[1]
            assert r["solution"]["wire_fee_cents"] == best[2]
        else:
            assert r["status"] == "UNMATCHED_EXCEPTION"


def test_selected_deposit_memo_export_preserves_whole_ledger_allocation(payload):
    r = client.post("/api/export-chargebacks-csv?deposit_id=DEP-9003", json=payload)
    assert r.status_code == 200
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 1
    assert rows[0]["Deposit"] == "DEP-9003"
    assert rows[0]["Amount"] == "164.00"
    assert (
        client.post(
            "/api/export-chargebacks-csv?deposit_id=unknown", json=payload
        ).status_code
        == 422
    )


def test_state_complexity_precedes_zero_wire_fee_in_ambiguous_claim():
    invoices = [
        make_invoice("claim-invoice", 100000),
        make_invoice("term-invoice", 70000, pct=".02"),
    ]
    deposit = Deposit(
        deposit_id="ambiguous-payment",
        deposit_date="2026-10-09",
        raw_payer_memo="Independent Customer",
        amount_cents=166100,
    )
    remit = Remittance(
        referenced_invoices=[{"invoice_id": "claim-invoice", "deduction_cents": 2500}]
    )
    result = solve(deposit, invoices, SolverConfig(), [remit])
    assert result["solution"]["wire_fee_cents"] == 2500
    assert result["solution"]["rank_score"]["state_complexity"] == 1
    assert any(
        candidate["wire_fee_cents"] == 0
        and any(i["state"] == "REMITTANCE_SHORTPAY" for i in candidate["invoices"])
        for candidate in result["alternatives"]
    )
