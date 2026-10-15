# Verification record

Verified in the development environment on 15 October 2026.

- `python -m pytest -q`: **54 passed in 0.95s**.
- `python -m pytest -q backend/test_hard_pass.py`: **5 passed in 0.63s**, zero failures/errors/skips.
- `npm --prefix frontend test`: **4 passed**, zero failures.
- `python scripts/audit_static.py`: **21 application source files passed**.

One upstream Starlette/httpx TestClient deprecation warning; no test failures.

- `npm --prefix frontend run build`: production build passed.
- `python scripts/verify_hard_pass_browser.py --url http://127.0.0.1:8000`: **12 checks passed**, including exact alien records, amount/date mutations, fee/discount switches, custom fee bands, rendered telemetry/proof/GL agreement, CSV/audit export payloads, and unsafe-currency rejection.
- `python scripts/verify_browser.py --url http://127.0.0.1:8000`: passed against real Chromium and the running FastAPI server. No intercepted requests, mocked API responses, or artificial delays.

Browser checks included:

1. Baseline 7/8 reconciliation with the unearned-discount showcase selected.
2. Vanguard date change produces $604.00 identified recovery and real GL state changes.
3. The selected Kestrel debit-memo download contains only that deposit's one memo, even when other deposits have draft memos.
4. About dialog receives focus, traps Shift+Tab, closes with Escape, and restores focus.
5. Unknown payer remains in the exception queue without a forced journal.
6. Actual QuickBooks CSV download and empty CSV validation message.
7. Editing an invoice date marks old proofs pending and recomputes accounting.
8. Uploading entirely new invoices, deposits, and a new counterparty returns a genuine computed match.
9. A newly parsed $27 claim and changed custom payment produce the corresponding short-pay journal amount.
10. Desktop (1440 px) and mobile (390 px) have no document-level horizontal overflow and no browser runtime errors. Accounting tables retain their own horizontal scroll where needed.

The new audit also corrected a fixture-specific simulator shortcut, generic abbreviation resolution, malformed terms/non-object input handling, monetary coercion, duplicate CSV headers, browser precision loss, pre-computation verification labels, and unwired control cues. See [the complete hard-pass report](HARD_PASS_AUDIT.md).

A separate initial finish review found two issues (memo scope and About focus handling); both were corrected and verified through regression tests/browser actions.

The screenshot in `terminal.png` shows a measured synthetic-data run. Wall-clock times vary by machine and run. Recovery figures represent identified chargeback AR and draft memos, not collected cash. Optional live Gemini extraction was not exercised because no API key was configured; deterministic text and PDF extraction were verified.
