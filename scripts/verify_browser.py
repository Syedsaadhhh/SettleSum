"""Optional full-stack smoke check; requires playwright and a running server.

python -m pip install playwright
python scripts/verify_browser.py --url http://localhost:8000 --browser /usr/bin/chromium

Uses a real browser and actual API responses. No fake latency or request mocks.
"""

import argparse
import csv
import io
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:8000")
parser.add_argument("--browser", default="/usr/bin/chromium")
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
shots = root / ".impeccable/review"
shots.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=args.browser, headless=True, args=["--no-sandbox"]
    )
    page = browser.new_page(
        viewport={"width": 1440, "height": 1100}, device_scale_factor=1
    )
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(args.url)
    page.get_by_text("87.5%", exact=True).wait_for()
    page.evaluate("document.fonts.ready")
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    page.screenshot(path=str(shots / "desktop.png"), full_page=True)

    # Discount date changes must reach Python and genuinely change accounting.
    page.get_by_role("button", name="Live input simulator WHAT-IF").click()
    page.get_by_role("combobox").select_option("DEP-9002")
    page.get_by_label("Clearing date").fill("2026-10-19")
    with page.expect_response(
        lambda r: "/api/reconcile" in r.url and r.request.method == "POST"
    ) as response:
        page.get_by_role("button", name="RE-SOLVE LEDGER", exact=True).click()
    result = response.value.json()
    assert result["summary"]["unearned_discounts_recovered_cents"] == 60400
    page.get_by_role("dialog").wait_for(state="hidden")
    assert page.locator(".recovery-metric strong").inner_text() == "$604.00"

    # Selected-deposit memo action must exclude other deposits' memos.
    page.locator(".deposit-row").filter(has_text="Kestrel Freight").click()
    with page.expect_download() as downloaded:
        page.get_by_role("button", name="Generate debit memo", exact=True).click()
    memos = list(csv.DictReader(io.StringIO(Path(downloaded.value.path()).read_text())))
    assert len(memos) == 1 and memos[0]["Deposit"] == "DEP-9003"

    # About dialog moves focus, traps Tab, closes on Escape, restores focus.
    about = page.get_by_role("button", name="About the solver", exact=True)
    about.click()
    dialog = page.get_by_role("dialog")
    assert dialog.locator("button").first.evaluate("(el)=>el===document.activeElement")
    page.keyboard.press("Shift+Tab")
    assert dialog.locator("button").last.evaluate("(el)=>el===document.activeElement")
    page.keyboard.press("Escape")
    dialog.wait_for(state="hidden")
    assert about.evaluate("(el)=>el===document.activeElement")

    # Exception view is unapplied; no invented ledger entries.
    page.get_by_role("button", name="Exceptions 1", exact=True).click()
    page.locator(".deposit-row").click()
    assert page.get_by_text("No exact reconciliation found", exact=True).is_visible()
    page.get_by_role("button", name="Reset benchmark", exact=True).click()
    page.get_by_text("87.5%", exact=True).wait_for()

    # A real CSV download and an empty upload failure.
    page.get_by_role("button", name="Export journal", exact=False).click()
    with page.expect_download() as downloaded:
        page.get_by_role("button", name="QuickBooks journal CSV", exact=True).click()
    assert "Cash - Operating Bank Account" in Path(downloaded.value.path()).read_text()
    page.get_by_role("button", name="Import data", exact=True).click()
    page.get_by_label("Upload file").set_input_files(
        {"name": "empty.csv", "mimeType": "text/csv", "buffer": b""}
    )
    page.get_by_text(
        "CSV is empty; include a header and at least one data row", exact=True
    ).wait_for()
    page.get_by_role("button", name="Close drawer", exact=True).click()

    # Direct invoice editing must invalidate and replace old proofs.
    page.get_by_role("button", name="Open invoice ledger", exact=True).click()
    page.get_by_label("INV-2026-107 invoice date", exact=True).fill("2026-09-20")
    assert page.locator(".pending-banner").is_visible()
    with page.expect_response(
        lambda r: "/api/reconcile" in r.url and r.request.method == "POST"
    ) as response:
        page.locator(".data-panel").get_by_role(
            "button", name="RE-SOLVE LEDGER", exact=True
        ).click()
    assert (
        response.value.json()["summary"]["unearned_discounts_recovered_cents"] == 40400
    )
    page.get_by_role("button", name="Reset benchmark", exact=True).click()
    page.get_by_text("87.5%", exact=True).wait_for()

    # Entirely new customers, invoices, and deposits through the upload UI.
    invoice_csv = (
        "invoice_id,customer_id,customer_name,invoice_date,due_date,amount,discount_terms,discount_pct,discount_days\n"
        "INV-ORBIT-A,ORBIT,Orbit Packaging Ltd,2026-10-01,2026-10-31,1000.00,Net 30,0,0\n"
        "INV-ORBIT-B,ORBIT,Orbit Packaging Ltd,2026-10-01,2026-10-31,700.00,2/10 Net 30,0.02,10\n"
    )
    deposit_csv = (
        "deposit_id,deposit_date,raw_payer_memo,amount,bank_reference\n"
        "ORBIT-PAYMENT,2026-10-09,ACH CREDIT ORBIT PACKAGING,1686.00,NEW-REF\n"
    )

    def upload_csv(kind, content):
        page.get_by_role("button", name="Import data", exact=True).click()
        page.get_by_label("Dataset to replace").select_option(kind)
        page.get_by_label("Upload file").set_input_files(
            {"name": f"{kind}.csv", "mimeType": "text/csv", "buffer": content.encode()}
        )
        page.get_by_text(
            f'{2 if kind == "invoices" else 1} rows validated', exact=True
        ).wait_for()
        with page.expect_response(
            lambda r: "/api/reconcile" in r.url and r.request.method == "POST"
        ) as response:
            page.get_by_role("button", name="APPLY & RECONCILE", exact=True).click()
        page.get_by_role("dialog").wait_for(state="hidden")
        return response.value.json()

    upload_csv("invoices", invoice_csv)
    custom = upload_csv("deposits", deposit_csv)
    assert custom["summary"]["matched_count"] == 1
    assert custom["matches"][0]["amount_cents"] == 168600
    assert custom["summary"]["valid_discounts_cents"] == 1400
    assert {i["invoice_id"] for i in custom["matches"][0]["invoices"]} == {
        "INV-ORBIT-A",
        "INV-ORBIT-B",
    }

    # Add a genuine parsed claim, then change cash to its exact documented net.
    page.get_by_role("button", name="Import data", exact=True).click()
    page.get_by_role("button", name="PDF / text remittance", exact=True).click()
    page.get_by_label("Remittance text", exact=True).fill(
        "Customer: Orbit Packaging Ltd\nDeducting $27 from INV-ORBIT-A for damaged goods"
    )
    page.get_by_role("button", name="Extract remittance references", exact=True).click()
    page.get_by_text("1 invoice references extracted", exact=True).wait_for()
    page.get_by_role("button", name="APPLY & RECONCILE", exact=True).click()
    page.get_by_role("dialog").wait_for(state="hidden")
    page.get_by_role("button", name="Live input simulator WHAT-IF").click()
    page.get_by_label("Deposit amount · USD", exact=True).fill("1659.00")
    with page.expect_response(
        lambda r: "/api/reconcile" in r.url and r.request.method == "POST"
    ) as response:
        page.get_by_role("button", name="RE-SOLVE LEDGER", exact=True).click()
    assert response.value.json()["summary"]["short_pays_cents"] == 2700
    page.get_by_role("dialog").wait_for(state="hidden")

    # Return screenshots to the labeled benchmark in both device sizes.
    page.get_by_role("button", name="Reset benchmark", exact=True).click()
    page.get_by_text("87.5%", exact=True).wait_for()
    page.locator(".proof-inspector").evaluate("(el)=>el.scrollTop=el.scrollHeight")
    page.screenshot(path=str(shots / "desktop-journal.png"), full_page=True)
    page.locator(".proof-inspector").evaluate("(el)=>el.scrollTop=0")
    page.screenshot(path=str(shots / "desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.evaluate("window.scrollTo(0,0)")
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    page.screenshot(path=str(shots / "mobile.png"), full_page=True)
    assert errors == [], errors
    browser.close()
    print(
        "PASS: date changes, scoped memo, dialog keyboard handling, exceptions, exports, empty CSV, invoice edits, entirely custom CSVs and remittance, desktop/mobile overflow, zero runtime errors."
    )
