"""The five non-negotiable hard-pass scenarios, exercised through the real API."""

import copy
import csv
import io
from fastapi.testclient import TestClient
from .main import app

client = TestClient(app)


def alien_payload():
    invoices = (
        "invoice_id,customer_id,customer_name,invoice_date,due_date,amount,discount_terms\n"
        "INV-X901,CUST-ORB,Orbital Robotics Corp,2026-10-01,2026-10-31,4200.00,Net 30\n"
        "INV-X902,CUST-ORB,Orbital Robotics Corp,2026-10-02,2026-11-01,3800.00,Net 30\n"
    )
    deposits = (
        "deposit_id,deposit_date,raw_payer_memo,amount,bank_reference\n"
        "DEP-X100,2026-10-10,FEDWIRE CRED ORBITAL ROB CORP,7985.00,ALIEN-WIRE\n"
    )
    inv = client.post("/api/import-csv?kind=invoices", content=invoices)
    dep = client.post("/api/import-csv?kind=deposits", content=deposits)
    assert inv.status_code == dep.status_code == 200
    return {
        "invoices": inv.json()["rows"],
        "deposits": dep.json()["rows"],
        "remittances": [],
    }


def reconcile(payload):
    response = client.post("/api/reconcile", json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["nodes_explored"] == int(response.headers["X-Nodes-Explored"])
    assert result["solve_time_ms"] >= 0
    return result


def debit(match, gl):
    return sum(
        line["debit_cents"]
        for line in match["journal_lines"]
        if line["gl_account"] == gl
    )


def test_1_alien_csv_injection():
    result = reconcile(alien_payload())
    match = result["matches"][0]
    assert match["counterparty"]["customer_name"] == "Orbital Robotics Corp"
    assert match["counterparty"]["customer_id"] == "CUST-ORB"
    assert match["status"] == "MATCHED"
    assert {i["invoice_id"] for i in match["invoices"]} == {"INV-X901", "INV-X902"}
    assert {i["state"] for i in match["invoices"]} == {"FULL"}
    assert match["wire_fee_cents"] == 1500
    assert match["variance_cents"] == 0
    assert match["nodes_explored"] > 1
    assert match["search_complete"] is True


def test_2_plus_one_cent_mutation():
    payload = alien_payload()
    before = reconcile(payload)
    assert before["matches"][0]["status"] == "MATCHED"
    payload["deposits"][0]["amount_cents"] = 798501
    after = reconcile(payload)
    match = after["matches"][0]
    assert match["deposit_id"] == "DEP-X100"
    assert match["status"] == "UNMATCHED_EXCEPTION"
    assert (
        match["invoices"] == match["journal_lines"] == match["chargeback_memos"] == []
    )
    assert after["summary"]["matched_deposits_cents"] == 0
    assert after["summary"]["unmatched_deposits_cents"] == 798501


def test_3_date_shift_margin_recovery():
    payload = alien_payload()
    payload["invoices"] = [
        {
            "invoice_id": "INV-M500",
            "customer_id": "CUST-ORB",
            "customer_name": "Orbital Robotics Corp",
            "invoice_date": "2026-10-01",
            "due_date": "2026-10-31",
            "amount_cents": 1000000,
            "discount_terms": "2/10 Net 30",
        }
    ]
    payload["deposits"][0].update(amount_cents=980000, deposit_date="2026-10-08")
    early = reconcile(payload)["matches"][0]
    assert early["status"] == "MATCHED"
    assert early["invoices"][0]["state"] == "EARNED_DISCOUNT"
    assert debit(early, "4910") == 20000
    assert debit(early, "1215") == 0
    changed = copy.deepcopy(payload)
    changed["deposits"][0]["deposit_date"] = "2026-10-22"
    late_result = reconcile(changed)
    late = late_result["matches"][0]
    assert late["status"] == "MATCHED"
    assert late["invoices"][0]["state"] == "UNEARNED_DISCOUNT"
    assert debit(late, "4910") == 0
    assert debit(late, "1215") == 20000
    assert late_result["summary"]["unearned_discounts_recovered_cents"] == 20000
    assert late["chargeback_memos"][0]["amount_cents"] == 20000
    response = client.post("/api/export-chargebacks-csv", json=changed)
    assert response.status_code == 200
    memos = list(csv.DictReader(io.StringIO(response.text)))
    assert len(memos) == 1 and memos[0]["Invoice"] == "INV-M500"
    assert memos[0]["Amount"] == "200.00" and memos[0]["GL Account"] == "1215"


def test_4_double_entry_gaap_invariant():
    sample = client.get("/api/sample-data").json()
    benchmark = {key: sample[key] for key in ("invoices", "deposits", "remittances")}
    normal = reconcile(benchmark)
    assert normal["summary"]["matched_count"] == 7
    for result in (normal, reconcile(alien_payload())):
        for match in result["matches"]:
            if match["status"] != "MATCHED":
                assert match["journal_lines"] == []
                continue
            lines = match["journal_lines"]
            assert all(
                type(line[field]) is int
                for line in lines
                for field in ("debit_cents", "credit_cents")
            )
            assert sum(line["debit_cents"] for line in lines) == sum(
                line["credit_cents"] for line in lines
            )
            credited_faces = sum(
                line["credit_cents"] for line in lines if line["gl_account"] == "1200"
            )
            assert credited_faces == sum(
                i["face_value_cents"] for i in match["invoices"]
            )
            assert credited_faces == match["amount_cents"] + match[
                "wire_fee_cents"
            ] + debit(match, "4910") + debit(match, "1215") + debit(match, "1220")
            assert debit(match, "1010") == match["amount_cents"]
            assert debit(match, "6120") == match["wire_fee_cents"]
            assert match["debits_cents"] == match["credits_cents"]
            assert match["variance_cents"] == match["ledger_variance_cents"] == 0


def test_5_unstructured_remittance_offline_fallback(monkeypatch):
    for key in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    text = "Remittance Advice: Orbital Robotics Corp applying $250.00 deduction on INV-X901 for cracked actuator housing per DM-771."
    response = client.post(
        "/api/parse-remittance", json={"text": text, "document_id": "ALIEN-REMITTANCE"}
    )
    assert response.status_code == 200
    parsed = response.json()
    assert parsed["parser"] == "deterministic-regex"
    reference = parsed["referenced_invoices"][0]
    assert reference["invoice_id"] == "INV-X901"
    assert reference["deduction_cents"] == 25000
    payload = alien_payload()
    payload["deposits"][0]["amount_cents"] = 775000
    payload["remittances"] = [
        {
            key: parsed[key]
            for key in (
                "document_id",
                "deposit_id",
                "customer_name",
                "raw_text",
                "referenced_invoices",
            )
        }
    ]
    match = reconcile(payload)["matches"][0]
    assert match["status"] == "MATCHED"
    assert {i["invoice_id"]: i["state"] for i in match["invoices"]} == {
        "INV-X901": "REMITTANCE_SHORTPAY",
        "INV-X902": "FULL",
    }
    assert match["wire_fee_cents"] == 0
    assert match["variance_cents"] == 0
    assert debit(match, "1220") == 25000
    claim_line = next(
        line for line in match["journal_lines"] if line["gl_account"] == "1220"
    )
    assert claim_line["document_id"] == "ALIEN-REMITTANCE"
    assert "DM-771" in claim_line["description"]
