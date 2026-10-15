"""Blank → composer → Python → proof/journal → source CSV → blank re-import.

Uses actual browser requests and downloaded files. Run against a built, running API.
"""

import argparse
import csv
import io
import json
from pathlib import Path
from zipfile import ZipFile
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8000")
parser.add_argument("--browser", default="/usr/bin/chromium")
options = parser.parse_args()
checks = []
shots = Path(__file__).resolve().parents[1] / ".impeccable/review"
shots.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=options.browser, headless=True, args=["--no-sandbox"]
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors, requests = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: requests.append(request.url))
    page.goto(options.url)
    expect(page.locator(".workspace-mode b")).to_have_text("BLANK LEDGER")
    expect(page.locator(".metric strong").nth(1)).to_have_text("$0.00")
    expect(page.locator(".metric strong").nth(3)).to_have_text("0")
    assert not any(
        "/api/sample-data" in url or "/api/reconcile" in url for url in requests
    )
    assert page.locator(".deposit-row").count() == 0
    page.screenshot(path=str(shots / "blank-ledger.png"))
    checks.append("Initial ledger is empty; no sample fetch or solver request is made")

    def open_case(
        name,
        invoice_ids,
        amounts,
        deposit_id,
        terms="Net 30",
        date="2026-10-10",
        mode="fresh",
    ):
        page.get_by_role("button", name="BUILD LIVE TEST CASE", exact=True).click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Workspace action").select_option(mode)
        dialog.get_by_label("Customer name", exact=True).fill(name)
        dialog.get_by_label("Customer ID", exact=True).fill(
            name.upper().replace(" ", "-")
        )
        for index, (invoice_id, amount) in enumerate(zip(invoice_ids, amounts)):
            if index:
                dialog.get_by_role("button", name="Add invoice", exact=True).click()
            dialog.get_by_label("Invoice ID", exact=True).nth(index).fill(invoice_id)
            dialog.get_by_label("Invoice date", exact=True).nth(index).fill(
                "2026-10-01"
            )
            dialog.get_by_label("Due date", exact=True).nth(index).fill("2026-10-31")
            dialog.get_by_label("Invoice amount ($)", exact=True).nth(index).fill(
                amount
            )
            dialog.get_by_label("Discount terms", exact=True).nth(index).select_option(
                terms
            )
        dialog.get_by_label("Deposit ID", exact=True).fill(deposit_id)
        dialog.get_by_label("Clearing date", exact=True).fill(date)
        expect(dialog.get_by_label("Raw bank memo")).to_have_value(f"WIRE IN: {name}")
        return dialog

    def run_case():
        with page.expect_response(
            lambda response: "/api/reconcile" in response.url
            and response.request.method == "POST"
        ) as received:
            page.get_by_role(
                "button", name="RUN SOLVER ON THIS LEDGER", exact=True
            ).click()
        response = received.value
        assert response.status == 200, response.text()
        document = response.json()
        payload = response.request.post_data_json
        expect(page.get_by_role("dialog")).to_have_count(0)
        return document, payload

    def balanced(document):
        for match in document["matches"]:
            assert match["status"] == "MATCHED", match
            assert match["variance_cents"] == 0
            assert sum(line["debit_cents"] for line in match["journal_lines"]) == sum(
                line["credit_cents"] for line in match["journal_lines"]
            )
        assert document["nodes_explored"] > 0
        expect(page.locator(".metric strong").nth(3)).to_have_text(
            f'{document["nodes_explored"]:,}'
        )
        expect(page.locator(".ledger-proof-strip")).to_contain_text(
            "DOUBLE-ENTRY VERIFIED"
        )

    dialog = open_case(
        "Horizon Hardware Co", ["BILL-H701", "BILL-H702"], ["4200", "3800"], "PAY-H701"
    )
    expect(dialog.locator(".composer-sum strong")).to_have_text("$8,000.00")
    dialog.get_by_role("button", name="Exact Sum", exact=True).click()
    expect(dialog.get_by_label("Deposit amount ($)", exact=True)).to_have_value(
        "8000.00"
    )
    dialog.get_by_role("button", name="Sum minus 2% Discount", exact=True).click()
    expect(dialog.get_by_label("Deposit amount ($)", exact=True)).to_have_value(
        "7840.00"
    )
    dialog.get_by_label("Include in preview").nth(1).uncheck()
    expect(dialog.locator(".composer-sum strong")).to_have_text("$4,200.00")
    dialog.get_by_label("Include in preview").nth(1).check()
    dialog.get_by_role("button", name="Sum minus $15 Wire Fee", exact=True).click()
    dialog.get_by_role("button", name="Add invoice", exact=True).click()
    dialog.get_by_role("button", name="Remove invoice 3", exact=True).click()
    dialog.get_by_role("button", name="Add deposit", exact=True).click()
    dialog.get_by_role("button", name="Remove deposit 2", exact=True).click()
    page.screenshot(path=str(shots / "live-case-composer.png"), full_page=True)
    document, payload = run_case()
    balanced(document)
    assert document["matches"][0]["wire_fee_cents"] == 1500
    assert len(payload["invoices"]) == 2 and len(payload["deposits"]) == 1
    assert {r["state"] for r in document["matches"][0]["invoices"]} == {"FULL"}
    expect(page.locator(".proof-inspector")).to_contain_text("BILL-H701")
    expect(page.locator(".proof-inspector")).to_contain_text("$7,985.00")
    page.screenshot(path=str(shots / "live-case-result.png"))
    checks.append(
        "Fresh composer records, selection/add/remove controls, all three helpers, real solver and balanced proof"
    )

    page.get_by_role("button", name="Export journal", exact=False).click()
    with page.expect_download() as received:
        page.get_by_role("button", name="QuickBooks journal CSV", exact=True).click()
    assert "BILL-H701" in Path(received.value.path()).read_text()
    checks.append(
        "Computed custom-ledger journal downloads with actual invoice references"
    )

    page.get_by_role("button", name="Import data", exact=True).click()
    for kind in ("Invoice", "Deposit"):
        with page.expect_download() as received:
            page.get_by_role(
                "button", name=f"Download Blank {kind} CSV Template", exact=True
            ).click()
        rows = list(csv.reader(io.StringIO(Path(received.value.path()).read_text())))
        assert len(rows) == 1 and len(rows[0]) >= 5
    with page.expect_download() as received:
        page.get_by_role(
            "button", name="Download Current Ledger as CSV", exact=True
        ).click()
    with ZipFile(received.value.path()) as archive:
        invoice_csv = archive.read("open_invoices.csv")
        deposit_csv = archive.read("bank_deposits.csv")
        assert json.loads(archive.read("remittance_notes.json")) == []
    with page.expect_download() as received:
        page.get_by_role("button", name="Download invoice CSV only", exact=True).click()
    assert Path(received.value.path()).read_bytes() == invoice_csv
    page.get_by_role("button", name="Close drawer", exact=True).click()
    page.get_by_role("button", name="NEW BLANK LEDGER", exact=True).click()
    expect(page.locator(".metric strong").nth(1)).to_have_text("$0.00")
    expect(page.locator(".ledger-proof-strip")).to_contain_text("AWAITING LEDGER PROOF")
    assert page.locator(".deposit-row").count() == 0
    checks.append(
        "Blank templates, lossless source CSV archive, individual CSV download, complete workspace reset"
    )

    # Deposit-first imports stage real source rows; no invalid empty reconcile request.
    before = sum("/api/reconcile" in url for url in requests)
    for kind, content in [("deposits", deposit_csv), ("invoices", invoice_csv)]:
        page.get_by_role("button", name="Import data", exact=True).click()
        page.get_by_label("Dataset to replace").select_option(kind)
        page.get_by_label("Upload file").set_input_files(
            {"name": f"{kind}.csv", "mimeType": "text/csv", "buffer": content}
        )
        expect(page.locator(".validation-success")).to_be_visible()
        if kind == "deposits":
            page.get_by_role("button", name="APPLY & RECONCILE", exact=True).click()
            expect(page.get_by_role("dialog")).to_have_count(0)
            expect(page.locator(".staged-deposit")).to_have_count(1)
            assert before == sum("/api/reconcile" in url for url in requests)
        else:
            with page.expect_response(
                lambda response: "/api/reconcile" in response.url
                and response.request.method == "POST"
            ) as received:
                page.get_by_role("button", name="APPLY & RECONCILE", exact=True).click()
            assert received.value.status == 200
            balanced(received.value.json())
            expect(page.get_by_role("dialog")).to_have_count(0)
    checks.append(
        "Export → clear → deposit-first CSV staging → invoice import → fresh exact reconciliation"
    )

    dialog = open_case(
        "Orbit Forge Co",
        ["BILL-OF-9", "BILL-OF-10"],
        ["10000", "5000"],
        "PAY-OF-9",
        terms="2/10 Net 30",
        date="2026-10-08",
        mode="append",
    )
    dialog.get_by_label("Include in preview").nth(1).uncheck()
    dialog.get_by_role("button", name="Sum minus 2% Discount", exact=True).click()
    dialog.get_by_role("button", name="Add deposit", exact=True).click()
    dialog.get_by_label("Deposit ID", exact=True).nth(1).fill("PAY-OF-10")
    dialog.get_by_label("Clearing date", exact=True).nth(1).fill("2026-10-08")
    dialog.get_by_label("Deposit amount ($)", exact=True).nth(1).fill("5000")
    document, payload = run_case()
    balanced(document)
    assert len(payload["invoices"]) == 4 and len(payload["deposits"]) == 3
    match = next(m for m in document["matches"] if m["deposit_id"] == "PAY-OF-9")
    assert match["invoices"][0]["state"] == "EARNED_DISCOUNT"
    page.get_by_role("button", name="Live input simulator WHAT-IF").click()
    page.get_by_role("combobox").select_option("PAY-OF-9")
    page.get_by_label("Clearing date").fill("2026-10-22")
    with page.expect_response(
        lambda response: "/api/reconcile" in response.url
        and response.request.method == "POST"
    ) as received:
        page.get_by_role("button", name="RE-SOLVE LEDGER", exact=True).click()
    document = received.value.json()
    expect(page.get_by_role("dialog")).to_have_count(0)
    balanced(document)
    assert document["summary"]["unearned_discounts_recovered_cents"] == 20000
    expect(page.locator(".metric strong").nth(2)).to_have_text("$200.00")
    checks.append(
        "Append with multiple deposits preserves sources; composed discount case reclassifies to chargeback AR after live date edit"
    )

    dialog = open_case(
        "Horizon Hardware Co",
        ["bill.claim-7", "bill.claim-8"],
        ["4200", "3800"],
        "PAY-CLAIM-7",
    )
    dialog.get_by_label("Deposit amount ($)", exact=True).fill("7750.00")
    dialog.get_by_label("03 / OPTIONAL REMITTANCE NOTE", exact=True).fill(
        "Applying $250.00 deduction on bill.claim-7 for cracked actuator housing"
    )
    with page.expect_response(
        lambda response: "/api/parse-remittance" in response.url
    ) as parsed:
        document, payload = run_case()
    assert parsed.value.json()["parser"] == "deterministic-regex"
    balanced(document)
    assert len(payload["invoices"]) == 2 and len(payload["deposits"]) == 1
    assert (
        payload["remittances"][0]["referenced_invoices"][0]["deduction_cents"] == 25000
    )
    assert {r["state"] for r in document["matches"][0]["invoices"]} == {
        "FULL",
        "REMITTANCE_SHORTPAY",
    }
    assert any(
        line["gl_account"] == "1220" and line["debit_cents"] == 25000
        for line in document["matches"][0]["journal_lines"]
    )
    checks.append(
        "Fresh replaces sources; optional text note with arbitrary invoice ID parses offline and produces GL 1220"
    )

    page.get_by_role("button", name="NEW BLANK LEDGER", exact=True).click()
    page.get_by_role("button", name="Remittance documents", exact=True).click()
    assert page.locator(".remittance-card").count() == 0
    before = sum("/api/reconcile" in url for url in requests)
    for kind, content in [("invoices", invoice_csv), ("deposits", deposit_csv)]:
        page.get_by_role("button", name="Import data", exact=True).click()
        page.get_by_label("Dataset to replace").select_option(kind)
        page.get_by_label("Upload file").set_input_files(
            {"name": f"{kind}.csv", "mimeType": "text/csv", "buffer": content}
        )
        expect(page.locator(".validation-success")).to_be_visible()
        if kind == "invoices":
            page.get_by_role("button", name="APPLY & RECONCILE", exact=True).click()
            expect(page.get_by_role("dialog")).to_have_count(0)
            expect(page.locator(".source-table tbody tr")).to_have_count(2)
            assert before == sum("/api/reconcile" in url for url in requests)
        else:
            with page.expect_response(
                lambda response: "/api/reconcile" in response.url
                and response.request.method == "POST"
            ) as received:
                page.get_by_role("button", name="APPLY & RECONCILE", exact=True).click()
            assert received.value.status == 200
            balanced(received.value.json())
            expect(page.get_by_role("dialog")).to_have_count(0)
    checks.append(
        "Invoice-first staging displays real source rows and reconciles after deposit import"
    )
    page.get_by_role("button", name="LOAD 36-ROW SAMPLE CSV", exact=True).click()
    expect(page.locator(".metric strong").first).to_have_text("87.5%")
    expect(page.locator(".workbench-toolbar")).to_contain_text("36 INVOICES")
    checks.append(
        "Reset clears remittances; benchmark is available only by explicit load"
    )
    page.reload()
    expect(page.locator(".workspace-mode b")).to_have_text("BLANK LEDGER")
    for width in (1280, 1024, 800, 390):
        page.set_viewport_size({"width": width, "height": 900})
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.get_by_role("button", name="BUILD LIVE TEST CASE", exact=True).click()
        assert not page.get_by_role("dialog").evaluate(
            "el => el.scrollWidth > el.clientWidth"
        )
        if width == 390:
            page.screenshot(path=str(shots / "composer-mobile.png"), full_page=True)
        page.get_by_role("button", name="Close drawer", exact=True).click()
    assert not errors, errors
    checks.append(
        "Reload starts blank; zero JavaScript errors or horizontal overflow across desktop/tablet/mobile"
    )
    browser.close()
print(
    json.dumps(
        {"status": "PASS", "checks_passed": len(checks), "checks": checks}, indent=2
    )
)
