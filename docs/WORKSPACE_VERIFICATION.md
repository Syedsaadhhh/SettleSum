# Blank workspace and Vercel preparation verification

Verified locally on 2026-10-15 using Python 3.12, Node 22, a production Vite build, FastAPI's real ASGI entry point, and headless Chromium. No solver responses were mocked.

| Check | Result |
| --- | --- |
| `python scripts/audit_static.py` | PASS: 25 runtime source files, including `api/index.py`; no fixture-specific branches, artificial delays, or forbidden solver math |
| `pytest` | **66 passed in 2.77s**, including all original 54 tests and 12 new workspace/API/deployment tests |
| `npm --prefix frontend test` | **7 passed**, zero failures; exact cents, selected-invoice helpers, and source-record construction |
| `npm --prefix frontend run build` | PASS |
| Root `requirements.txt` | `pip install --dry-run -r requirements.txt` resolves the backend requirements |
| `vercel.json` | Zero instance validation errors against the current official Vercel configuration schema |
| `api/index.py` | Imports with `frontend/dist` unavailable; custom `/api/reconcile` request matches with a $15 fee and zero variance |
| `scripts/verify_workspace_browser.py` | **10 browser checks passed**, no JavaScript runtime errors |
| `scripts/verify_hard_pass_browser.py` | **12 browser checks passed**, no JavaScript runtime errors |
| `scripts/verify_browser.py` | Existing full-stack smoke suite passed |

Pytest reports one existing dependency deprecation warning from FastAPI's test client; no test failures. The solver, entity resolver, accounting exporter, reconciliation pipeline, and original 54 test cases were not modified.

## New browser verification

1. Opening or reloading the application produces an empty ledger. No benchmark or reconciliation request is sent automatically. Money totals and node counts are zero; execution time and ledger proof remain uncomputed.
2. An unseen customer with two invoices is created in the composer. Add/remove controls and preview selections work. Exact-sum, $15 fee, and per-invoice 2% helpers fill real source amounts; the solver determines matches and accounting.
3. Submitting the composer sends real source records to `/api/reconcile`. Returned nodes, invoice states, proof, and balanced GL journal agree with the workbench. Accounting CSV includes the custom references.
4. Both blank CSV templates download with headers only. Current source data downloads as individual CSVs or a ZIP of invoice/deposit CSVs plus remittance JSON. Exported cents and terms survive re-import.
5. Clearing removes source rows, selected results, claims, metrics, and settings. Deposit-first ingestion stages bank records without sending an invalid empty reconciliation request; importing invoices then triggers the full solver.
6. Append mode preserves prior source data and accepts multiple deposits. A newly composed early-payment discount reconciles to GL 4910. Editing its clearing date re-solves the complete ledger and moves $200 to GL 1215.
7. A fresh case replaces the prior ledger. A text claim with an arbitrary, case-sensitive invoice ID parses offline and produces the actual short-pay state and GL 1220 debit.
8. Invoice-first ingestion shows the imported source rows, stages them without a solver request, then reconciles when deposits arrive.
9. Clearing removes remittance documents. Explicitly loading the benchmark computes 7/8 matches and 36 source invoices.
10. Reload returns to blank. Desktop, tablet, and mobile viewport checks find no document or composer horizontal overflow.

Reproduce with a built frontend and running API:

```bash
python -m uvicorn api.index:app --host 0.0.0.0 --port 8000
# In another terminal, with Playwright and Chromium installed:
python scripts/verify_workspace_browser.py --browser /usr/bin/chromium
python scripts/verify_hard_pass_browser.py --browser /usr/bin/chromium
python scripts/verify_browser.py --browser /usr/bin/chromium
```

## Deployment boundary

This verifies repository configuration and local behavior. A hosted Vercel deployment, its cold-start time, platform routing, and provider execution limits require checking the resulting deployment URL. Import the GitHub repository using the repository root; `vercel.json` supplies the frontend build/output and Python API rewrites. The optional Gemini key is not required. Vercel's 4.5 MB function request/response limit takes precedence over larger local upload limits.

Source ledger exports serialize records without solving. Accounting CSV and audit exports always recompute. No journal, debit memo, or message is posted externally.
