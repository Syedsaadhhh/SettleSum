"""Real-browser torture tests. No request routing, mocked responses, or timed sleeps."""

import argparse
import csv
import io
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

args = argparse.ArgumentParser()
args.add_argument("--url", default="http://127.0.0.1:8000")
args.add_argument("--browser", default="/usr/bin/chromium")
options = args.parse_args()
root = Path(__file__).resolve().parent.parent
checks = []


def money(cents):
    return f'{"-" if cents < 0 else ""}${abs(cents) // 100:,}.{abs(cents) % 100:02d}'


with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=options.browser, headless=True, args=["--no-sandbox"]
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(options.url)
    page.get_by_role("button", name="LOAD 36-ROW SAMPLE CSV").click()
    expect(page.locator(".metric strong").first).to_have_text("87.5%")
    page.evaluate("document.fonts.ready")
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    checks.append("benchmark loads from API and computes 7/8")

    def post_result(action, path="/api/reconcile"):
        with page.expect_response(
            lambda r: path in r.url and r.request.method == "POST"
        ) as received:
            action()
        response = received.value
        assert response.status == 200, response.text()
        payload = response.request.post_data_json
        document = response.json()
        return document, payload

    def upload_csv(kind, source):
        page.get_by_role("button", name="Import data", exact=True).click()
        page.get_by_label("Dataset to replace").select_option(kind)
        page.get_by_label("Upload file").set_input_files(
            {"name": f"{kind}.csv", "mimeType": "text/csv", "buffer": source.encode()}
        )
        expect(page.locator(".validation-success")).to_be_visible()
        document, payload = post_result(
            lambda: page.get_by_role(
                "button", name="APPLY & RECONCILE", exact=True
            ).click()
        )
        page.get_by_role("dialog").wait_for(state="hidden")
        return document, payload

    def simulate(
        amount=None, date=None, fees=None, discounts=None, band=None, shift=False
    ):
        page.get_by_role("button", name="Live input simulator WHAT-IF").click()
        if amount is not None:
            page.get_by_label("Deposit amount · USD", exact=True).fill(amount)
        if date is not None:
            page.get_by_label("Clearing date").fill(date)
        if fees is not None:
            page.get_by_role("checkbox", name="Allow bank wire fees").set_checked(fees)
        if discounts is not None:
            page.get_by_role("checkbox", name="Apply payment-term states").set_checked(
                discounts
            )
        if band is not None:
            page.get_by_role("checkbox", name="Custom fee band").set_checked(True)
            page.get_by_label("Minimum · USD", exact=True).fill(band)
            page.get_by_label("Maximum · USD", exact=True).fill(band)
        if shift:
            page.get_by_role("button", name="Shift clearing date +14 days").click()
        document, payload = post_result(
            lambda: page.get_by_role(
                "button", name="RE-SOLVE LEDGER", exact=True
            ).click()
        )
        page.get_by_role("dialog").wait_for(state="hidden")
        return document, payload

    def check_ui(document):
        summary = document["summary"]
        match = document["matches"][0]
        expected_rate = f"{summary['matched_count']/summary['deposit_count']*100:.1f}%"
        expect(page.locator(".metric strong").nth(0)).to_have_text(expected_rate)
        expect(page.locator(".metric strong").nth(1)).to_have_text(
            money(summary["matched_deposits_cents"])
        )
        expect(page.locator(".metric strong").nth(2)).to_have_text(
            money(summary["unearned_discounts_recovered_cents"])
        )
        expect(page.locator(".metric strong").nth(3)).to_have_text(
            f"{summary['total_nodes_explored']:,}"
        )
        displayed = float(
            page.locator(".metric strong").nth(4).inner_text().replace("ms", "").strip()
        )
        assert abs(displayed - summary["solve_time_ms"]) <= 0.00051
        expect(page.locator(".inspector-amount strong")).to_have_text(
            money(match["amount_cents"])
        )
        if match["status"] != "MATCHED":
            expect(
                page.get_by_text("No exact reconciliation found", exact=True)
            ).to_be_visible()
            assert page.locator(".journal-table").count() == 0
            return
        rows = page.locator(".invoice-proof-table tbody tr")
        assert rows.count() == len(match["invoices"])
        labels = {
            "FULL": "FULL VALUE",
            "EARNED_DISCOUNT": "VALID DISCOUNT",
            "UNEARNED_DISCOUNT": "UNEARNED DISCOUNT",
            "REMITTANCE_SHORTPAY": "SHORT-PAY CLAIM",
        }
        for index, item in enumerate(match["invoices"]):
            expect(rows.nth(index).locator("td").nth(0).locator("strong")).to_have_text(
                item["invoice_id"]
            )
            expect(rows.nth(index).locator("td").nth(1)).to_have_text(
                money(item["face_value_cents"])
            )
            expect(rows.nth(index).locator(".state-badge")).to_have_text(
                labels[item["state"]]
            )
            expect(rows.nth(index).locator("td").nth(3)).to_have_text(
                money(item["value_cents"])
            )
        assert (
            page.locator(".equation-result b")
            .inner_text()
            .startswith(money(match["amount_cents"]))
        )
        rows = page.locator(".journal-table tbody tr")
        assert rows.count() == len(match["journal_lines"])
        for index, line in enumerate(match["journal_lines"]):
            expect(rows.nth(index).locator("td").nth(0)).to_have_text(
                line["gl_account"]
            )
            expect(rows.nth(index).locator("td").nth(2)).to_have_text(
                money(line["debit_cents"]) if line["debit_cents"] else "—"
            )
            expect(rows.nth(index).locator("td").nth(3)).to_have_text(
                money(line["credit_cents"]) if line["credit_cents"] else "—"
            )
        totals = page.locator(".journal-table tfoot td")
        expect(totals.nth(1)).to_have_text(money(match["debits_cents"]))
        expect(totals.nth(2)).to_have_text(money(match["credits_cents"]))

    def export(kind="quickbooks"):
        page.get_by_role("button", name="Export journal", exact=False).click()
        label = (
            "Reconciliation audit JSON" if kind == "audit" else "QuickBooks journal CSV"
        )
        endpoint = (
            "/api/export-audit-json" if kind == "audit" else "/api/export-journal-csv"
        )
        with page.expect_download() as received:
            with page.expect_response(
                lambda r: endpoint in r.url and r.request.method == "POST"
            ) as response:
                page.get_by_role("button", name=label, exact=True).click()
        assert response.value.status == 200
        text = Path(received.value.path()).read_text()
        return (
            json.loads(text)
            if kind == "audit"
            else list(csv.DictReader(io.StringIO(text)))
        ), response.value.request.post_data_json

    invoices = (
        "invoice_id,customer_id,customer_name,invoice_date,due_date,amount,discount_terms\n"
        "INV-X901,CUST-ORB,Orbital Robotics Corp,2026-10-01,2026-10-31,4200.00,Net 30\n"
        "INV-X902,CUST-ORB,Orbital Robotics Corp,2026-10-02,2026-11-01,3800.00,Net 30\n"
    )
    deposits = (
        "deposit_id,deposit_date,raw_payer_memo,amount,bank_reference\n"
        "DEP-X100,2026-10-10,FEDWIRE CRED ORBITAL ROB CORP,7985.00,ALIEN-WIRE\n"
    )
    upload_csv("invoices", invoices)
    document, payload = upload_csv("deposits", deposits)
    assert {i["invoice_id"] for i in payload["invoices"]} == {"INV-X901", "INV-X902"}
    assert payload["deposits"][0]["amount_cents"] == 798500
    assert document["matches"][0]["wire_fee_cents"] == 1500
    check_ui(document)
    exported, source = export()
    assert source["deposits"][0]["amount_cents"] == 798500
    assert any(
        "6120" in row["Description"] and row["Debits"] == "15.00" for row in exported
    )
    audit, source = export("audit")
    assert audit["result"]["matches"][0]["wire_fee_cents"] == 1500
    assert audit["source"]["deposits"][0]["amount_cents"] == 798500
    assert audit["result"]["nodes_explored"] > 1
    checks.append(
        "alien CSVs replace active data; solver, telemetry, proof, GL cells, CSV and audit exports agree"
    )

    document, payload = simulate(amount="7985.01")
    assert payload["deposits"][0]["amount_cents"] == 798501
    assert document["matches"][0]["status"] == "UNMATCHED_EXCEPTION"
    check_ui(document)
    exported, source = export()
    assert exported == [] and source["deposits"][0]["amount_cents"] == 798501
    checks.append(
        "+1 cent updates actual request, telemetry and exception UI; no journal exported"
    )

    document, payload = simulate(band="14.99")
    assert (
        payload["config"]["wire_fee_band_min_cents"]
        == payload["config"]["wire_fee_band_max_cents"]
        == 1499
    )
    assert document["matches"][0]["wire_fee_cents"] == 1499
    check_ui(document)
    exported, source = export()
    assert source["config"]["wire_fee_band_min_cents"] == 1499
    assert any(
        "6120" in row["Description"] and row["Debits"] == "14.99" for row in exported
    )
    checks.append(
        "custom fee band genuinely creates exact 1499-cent fee and matching journal/export"
    )

    document, payload = simulate(fees=False)
    assert payload["config"]["allow_wire_fees"] is False
    assert document["matches"][0]["status"] == "UNMATCHED_EXCEPTION"
    check_ui(document)
    document, payload = simulate(amount="8000.00")
    assert document["matches"][0]["wire_fee_cents"] == 0
    check_ui(document)
    checks.append(
        "wire-fee toggle removes inferred fee state; full cash amount resolves without fee"
    )

    term_invoice = (
        "invoice_id,customer_id,customer_name,invoice_date,due_date,amount,discount_terms\n"
        "INV-M500,CUST-ORB,Orbital Robotics Corp,2026-10-01,2026-10-31,10000.00,2/10 Net 30\n"
    )
    term_deposit = (
        "deposit_id,deposit_date,raw_payer_memo,amount,bank_reference\n"
        "DEP-M500,2026-10-08,FEDWIRE ORBITAL ROB CORP,9800.00,TERM-WIRE\n"
    )
    upload_csv("invoices", term_invoice)
    document, payload = upload_csv("deposits", term_deposit)
    assert document["matches"][0]["invoices"][0]["state"] == "EARNED_DISCOUNT"
    check_ui(document)
    document, payload = simulate(date="2026-10-22")
    assert payload["deposits"][0]["deposit_date"] == "2026-10-22"
    assert document["matches"][0]["invoices"][0]["state"] == "UNEARNED_DISCOUNT"
    check_ui(document)
    exported, source = export()
    assert source["deposits"][0]["deposit_date"] == "2026-10-22"
    assert any(
        "1215" in row["Description"] and row["Debits"] == "200.00" for row in exported
    )
    assert all("4910" not in row["Description"] for row in exported)
    checks.append(
        "date change updates API source, recovery ribbon, invoice state, GL1215 and exported CSV"
    )

    document, payload = simulate(discounts=False)
    assert payload["config"]["allow_discounts"] is False
    assert document["matches"][0]["status"] == "UNMATCHED_EXCEPTION"
    check_ui(document)
    document, payload = simulate(discounts=True)
    check_ui(document)
    assert document["matches"][0]["invoices"][0]["state"] == "UNEARNED_DISCOUNT"
    checks.append(
        "discount toggle removes/restores genuine valuation states across all views"
    )

    document, payload = simulate(shift=True)
    assert payload["deposits"][0]["deposit_date"] == "2026-11-05"
    check_ui(document)
    audit, source = export("audit")
    assert audit["source"]["deposits"][0]["deposit_date"] == "2026-11-05"
    assert audit["result"]["summary"]["unearned_discounts_recovered_cents"] == 20000
    checks.append(
        "generic date-shift control works on unseen customer and exported audit uses latest source"
    )

    upload_csv("invoices", invoices)
    upload_csv("deposits", deposits.replace("7985.00", "7750.00"))
    page.get_by_role("button", name="Import data", exact=True).click()
    page.get_by_role("button", name="PDF / text remittance", exact=True).click()
    page.get_by_label("Remittance text", exact=True).fill(
        "Remittance Advice: Orbital Robotics Corp applying $250.00 deduction on INV-X901 for cracked actuator housing per DM-771."
    )
    page.get_by_role("button", name="Extract remittance references", exact=True).click()
    expect(
        page.get_by_text("1 invoice references extracted", exact=True)
    ).to_be_visible()
    document, payload = post_result(
        lambda: page.get_by_role("button", name="APPLY & RECONCILE", exact=True).click()
    )
    page.get_by_role("dialog").wait_for(state="hidden")
    assert document["summary"]["short_pays_cents"] == 25000
    assert payload["remittances"][-1]["customer_name"] == "Orbital Robotics Corp"
    check_ui(document)
    exported, source = export()
    assert any(
        "1220" in row["Description"] and row["Debits"] == "250.00" for row in exported
    )
    checks.append(
        "exact unstructured remittance parses offline, applies claim, and updates GL1220/CSV"
    )

    # Precision failures stay visible and cannot replace the active dataset.
    page.get_by_role("button", name="Import data", exact=True).click()
    page.get_by_label("Dataset to replace").select_option("invoices")
    huge = term_invoice.replace(
        "amount,discount_terms", "amount_cents,discount_terms"
    ).replace("10000.00", "9007199254740992")
    page.get_by_label("Upload file").set_input_files(
        {"name": "unsafe.csv", "mimeType": "text/csv", "buffer": huge.encode()}
    )
    expect(
        page.get_by_role("alert").filter(has_text="safe browser integer cents")
    ).to_be_visible()
    assert page.get_by_role(
        "button", name="APPLY & RECONCILE", exact=True
    ).is_disabled()
    page.get_by_role("button", name="Close drawer", exact=True).click()
    check_ui(document)
    checks.append(
        "unsafe browser currency is rejected explicitly; current computed ledger remains intact"
    )

    page.get_by_role("button", name="LOAD 36-ROW SAMPLE CSV", exact=True).click()
    expect(page.locator(".metric strong").first).to_have_text("87.5%")
    page.get_by_role("button", name="About the solver", exact=True).click()
    page.keyboard.press("Escape")
    page.get_by_role("dialog").wait_for(state="hidden")
    page.keyboard.press("/")
    expect(page.get_by_label("Search deposits", exact=True)).to_be_focused()
    page.get_by_label("Search deposits", exact=True).fill("zz-no-such-customer")
    expect(page.get_by_text("No deposits found", exact=True)).to_be_visible()
    page.get_by_role("button", name="Clear filters", exact=True).click()
    checks.append(
        "about dialog, real search shortcut, filters, and reset controls work"
    )
    shots = root / ".impeccable/review"
    shots.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(shots / "hard-pass-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    page.screenshot(path=str(shots / "hard-pass-mobile.png"), full_page=True)
    assert errors == [], errors
    checks.append(
        "desktop/mobile have no document overflow and no JavaScript runtime errors"
    )
    browser.close()
    result = {
        "status": "PASS",
        "checks_passed": len(checks),
        "checks": checks,
        "runtime_errors": errors,
    }
    Path("/tmp/settlesum-hard-pass-browser.json").write_text(
        json.dumps(result, indent=2)
    )
    print(json.dumps(result, indent=2))
