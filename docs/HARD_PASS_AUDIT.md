# SettleSum — Hard-Pass Audit

**HARD PASS: all requested checks passed after fixes.** Audited 15 October 2026. Base revision: `2a6ed47`. Evidence: [hard-pass-evidence.json](hard-pass-evidence.json).

## 1. Red-flag scan results

- **21 application source files: PASS.** No concrete sample IDs or sample-customer literals in runtime source. Generic invoice-token recognition is not a fixture lookup. Tests, synthetic fixtures, dependencies, and generated builds are excluded.
- **Zero fake latency: PASS.** No artificial sleep/timer calls. `perf_counter_ns()` measures each actual search; `nodes += 1` executes inside recursive search. Browser tests compared rendered nodes/time to the actual API response.
- **Integer cents: PASS.** Solver and journal/export arithmetic use integers; no monetary float conversions, true division, or floating equality. Dollar ingress follows the specified conversion convention. Signed-64-bit input/aggregate limits are enforced; Python integer intermediates avoid overflow. The maximum boundary exports exactly as `92233720368547758.07`.
- **End-to-end terminal: PASS.** Raw bordered ledger UI retained, no gradients or decorative stock media. Real CSV/text/PDF ingestion, amount/date controls, fee/discount switches, custom fee bands, journal CSV, debit memos, and fresh audit JSON are wired to computation. No mocked HTTP responses or match results were used.

The browser explicitly rejects currency beyond JavaScript's safe-integer range; it never silently applies rounded source data. The Python API retains the signed-64-bit cents domain. Recovery is identified AR, not collected cash.

## 2. Pytest output summary

| Five-point torture case | Result |
| --- | --- |
| Alien CSV: Orbital Robotics, two FULL invoices minus 1,500-cent fee | PASS |
| +1-cent mutation: exception, zero false allocations/journal lines | PASS |
| Date shift: EARNED/4910 → UNEARNED/1215, 20,000-cent debit memo | PASS |
| GAAP invariant: every default/alien matched deposit balances exactly | PASS |
| Exact raw remittance, API keys unset: 25,000-cent claim → GL 1220 | PASS |

```text
Five-point suite: 5 passed, 0 failed, 0 errors, 0 skipped in 0.63s
Full backend suite: 54 passed, 0 failed, 0 errors, 0 skipped in 0.95s
Frontend currency tests: 4 passed, 0 failed
Production build: PASS (4.76s)
Real-browser torture checks: 12 passed; 0 JavaScript runtime errors
Original browser smoke check: PASS
```

Pytest emitted one upstream Starlette/httpx TestClient deprecation warning; no warnings were suppressed. Live Gemini-provider extraction was not exercised; deterministic offline extraction was tested.

## 3. Bugs/shortcuts found and fixed

- Removed the simulator's customer-name-specific preset and sample remittance placeholder. Replaced it with a generic selected-deposit date shift.
- Fixed generic truncated counterparty matching (`ROB`/`Robotics`) without adding customer-specific mappings; ambiguous names still fail closed.
- Reproduced three 500 errors for null/list/numeric discount terms; fixed them to structured 422 responses. Added non-object record guards and bounded terms parsing.
- Rejected coerced/fractional fee and journal cents; rejected duplicate CSV column headers instead of silently overwriting values.
- Removed browser currency precision loss: exact decimal/BigInt entry and display, safe-integer guards on incoming/outgoing money, and explicit rejection before dataset replacement.
- Removed premature VERIFIED/BALANCED text before results exist; wired the search shortcut and removed misleading static dropdown cues.
- Added a fresh audit JSON export with source inputs/configuration, source SHA-256, UTC timestamp, recomputed journal/proof, and actual solver telemetry.
- Extended generic remittance customer extraction and added the five-point suite, boundary/malformed-input regressions, browser payload/GL/export assertions, and CI coverage. Corrected the date-field test locator to its accessible label; the final browser run passes.

No hardcoded solver match outputs or artificial processing delays were found. The core solver below is the actual repository implementation.

## 4. Core solver — `backend/solver.py`

```python
"""Inspectable Multi-State Choice Branch-and-Bound.

A node is one entered DFS call (including root and calls pruned by bounds).
Each branch chooses one state of one subsequent invoice; skipped indices are implicit. Integer upper
bounds by remaining cardinality prune unreachable branches. All feasible
assignments are ranked; only the top six are retained. A budget interruption
never claims optimality or emits a posted match. Python's arbitrary precision
integers are constrained to the signed 64-bit money domain at the API boundary.
"""

from time import perf_counter_ns
from .models import Invoice, Deposit, SolverConfig, Remittance

COMPLEXITY = {
    "FULL": 0,
    "EARNED_DISCOUNT": 1,
    "REMITTANCE_SHORTPAY": 2,
    "UNEARNED_DISCOUNT": 3,
}


def invoice_states(invoice: Invoice, deposit: Deposit, config: SolverConfig, claims):
    base = {
        "invoice_id": invoice.invoice_id,
        "face_value_cents": invoice.amount_cents,
        "invoice_date": invoice.invoice_date.isoformat(),
        "due_date": invoice.due_date.isoformat(),
        "discount_pct": str(invoice.discount_pct),
        "discount_days": invoice.discount_days,
        "remittance_hit": invoice.invoice_id in claims,
    }
    states = [
        {
            **base,
            "state": "FULL",
            "value_cents": invoice.amount_cents,
            "adjustment_cents": 0,
            "document_id": None,
        }
    ]
    if config.allow_discounts and invoice.discount_pct > 0:
        numerator, denominator = invoice.discount_pct.as_integer_ratio()
        whole, remainder = divmod(
            invoice.amount_cents * (denominator - numerator), denominator
        )
        # Exact round-half-to-even, using integer rational arithmetic.
        value = whole + int(
            remainder * 2 > denominator
            or (remainder * 2 == denominator and whole % 2 == 1)
        )
        if value != invoice.amount_cents:
            earned = (
                deposit.deposit_date - invoice.invoice_date
            ).days <= invoice.discount_days
            states.append(
                {
                    **base,
                    "state": "EARNED_DISCOUNT" if earned else "UNEARNED_DISCOUNT",
                    "value_cents": value,
                    "adjustment_cents": invoice.amount_cents - value,
                    "document_id": None,
                }
            )
    for reference, doc_id in claims.get(invoice.invoice_id, []):
        deduction = reference.deduction_cents
        if not deduction and reference.paid_amount_cents is not None:
            deduction = invoice.amount_cents - reference.paid_amount_cents
        if 0 < deduction <= invoice.amount_cents:
            states.append(
                {
                    **base,
                    "state": "REMITTANCE_SHORTPAY",
                    "value_cents": invoice.amount_cents - deduction,
                    "adjustment_cents": deduction,
                    "document_id": doc_id,
                    "claim_note": reference.note,
                }
            )
    unique = {}
    for state in states:
        unique[(state["state"], state["value_cents"], state["document_id"])] = state
    return list(unique.values())


def solve(
    deposit: Deposit,
    invoices: list[Invoice],
    config: SolverConfig,
    remittances: list[Remittance],
):
    started = perf_counter_ns()
    claims = {}
    for remit in remittances:
        for reference in remit.referenced_invoices:
            claims.setdefault(reference.invoice_id, []).append(
                (reference, remit.document_id)
            )
    ordered = sorted(
        [x for x in invoices if x.invoice_date <= deposit.deposit_date],
        key=lambda x: (x.due_date, x.invoice_id),
    )
    vectors = [invoice_states(x, deposit, config, claims) for x in ordered]
    fees = set(config.wire_fee_options_cents if config.allow_wire_fees else [0]) | {0}
    band = config.allow_wire_fees and config.wire_fee_band_min_cents is not None
    min_fee = 0
    max_fee = max(fees | ({config.wire_fee_band_max_cents} if band else set()))
    target_min, target_max = (
        deposit.amount_cents + min_fee,
        deposit.amount_cents + max_fee,
    )
    n, cap = len(ordered), min(config.max_subset_size, len(ordered))
    # bound[index][slots] = greatest possible face sum with up to slots invoices.
    bound = [[0] * (cap + 1) for _ in range(n + 1)]
    for index in range(n - 1, -1, -1):
        for slots in range(1, cap + 1):
            bound[index][slots] = max(
                bound[index + 1][slots],
                ordered[index].amount_cents + bound[index + 1][slots - 1],
            )
    best, count, nodes, limited = [], 0, 0, False

    def rank(chosen, fee):
        return (
            -sum(x["remittance_hit"] for x in chosen),
            sum(COMPLEXITY[x["state"]] for x in chosen),
            int(fee != 0),
            tuple(x["due_date"] for x in chosen),
            fee,
            tuple(
                (x["invoice_id"], x["state"], x["document_id"] or "") for x in chosen
            ),
        )

    def visit(index, total, chosen):
        nonlocal nodes, count, limited
        if nodes >= config.max_nodes:
            limited = True
            return
        nodes += 1
        if total > target_max or total + bound[index][cap - len(chosen)] < target_min:
            return
        # Evaluate each nonempty subset once; implicit skips are the loop's
        # starting indices. Recursion depth is at most max_subset_size, even
        # for a 2,000-invoice upload.
        fee = total - deposit.amount_cents
        fee_valid = fee in fees or (
            band
            and config.wire_fee_band_min_cents <= fee <= config.wire_fee_band_max_cents
        )
        if chosen and fee_valid:
            count += 1
            score = rank(chosen, fee)
            best.append(
                (
                    score,
                    {
                        "invoices": list(chosen),
                        "wire_fee_cents": fee,
                        "valuation_cents": total,
                        "variance_cents": total - fee - deposit.amount_cents,
                        "rank_score": {
                            "remittance_hits": -score[0],
                            "state_complexity": score[1],
                            "nonzero_wire_fee": score[2],
                            "fifo_due_dates": list(score[3]),
                        },
                    },
                )
            )
            best.sort(key=lambda x: x[0])
            del best[6:]
        if index == n or len(chosen) == cap:
            return
        for candidate in range(index, n):
            for state in vectors[candidate]:
                visit(candidate + 1, total + state["value_cents"], chosen + [state])
                if limited:
                    return

    visit(0, 0, [])
    elapsed = (perf_counter_ns() - started) / 1_000_000
    return {
        "solution": best[0][1] if best and not limited else None,
        "alternatives": [x[1] for x in best[1:]] if not limited else [],
        "candidate_count": count,
        "nodes_explored": nodes,
        "solve_time_ms": elapsed,
        "search_complete": not limited,
        "eligible_invoices": n,
        "status": (
            "SEARCH_LIMIT"
            if limited
            else ("MATCHED" if best else "UNMATCHED_EXCEPTION")
        ),
    }

```

## 5. Current README.md — full contents

````markdown
# SettleSum

**B2B cash application, multi-state lump-sum reconciliation, and margin recovery.**

SettleSum reconciles bank deposits to computed combinations of open invoices, including valid early-payment discounts, expired discounts, documented short-pays, and permitted wire fees. Every match includes an exact-cent equation and a verified double-entry journal. The financial terminal supports live source edits, CSV imports, PDF/text remittances, and accounting exports.

All included business records are **SYNTHETIC BENCHMARK DATA — modeled on B2B wholesale AR ledgers**. No included record represents a real customer transaction.

![SettleSum financial terminal with computed synthetic benchmark results](docs/terminal.png)

Screenshot of an actual synthetic-data run; solver timing varies. See [verification record](docs/VERIFICATION.md).

## Run locally

Requires Python 3.11+ and Node.js 20.19+ (Node 22 recommended).

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000**. FastAPI serves both the built React terminal and API. Interactive API docs are at **http://localhost:8000/docs**.

For development with hot reload:

```bash
bash scripts/dev.sh
```

Open **http://localhost:5173**. Vite proxies `/api` to Python on port 8000. Stop with Ctrl+C. Restart the Python server after creating the first production build so its static mount is registered.

## Verify

```bash
python scripts/audit_static.py
python -m pytest -q backend/test_hard_pass.py
python -m pytest -q backend
npm --prefix frontend test
npm --prefix frontend run build
```

**54 Python tests and 4 frontend currency tests** verify the current implementation. The dedicated five-point torture suite verifies the exact alien CSV, a one-cent mutation, earned-to-unearned date changes, double-entry invariants, and offline remittance extraction. See the [hard-pass audit report](docs/HARD_PASS_AUDIT.md). The suite covers the seven real computed benchmark matches and exception; a removed $15 fee; a one-cent amount edit; a changed clearing date; invoice-date edits; disabled fees; duplicate prevention; empty/negative/malformed input; PDF/text parsing; journal exports; custom fee bands; exact rounding; FIFO/remittance ranking; search budgets; and a 1,200-invoice input. An independent exhaustive oracle checks branch-and-bound results on generated small ledgers. GitHub Actions runs the static source guard, full Python suite, frontend currency tests, and production frontend build on pushes and pull requests.

An optional full-stack browser smoke check is included in `scripts/verify_browser.py`. With Playwright installed and a Chromium executable available, run it against the live server:

```bash
python -m pip install playwright
python scripts/verify_browser.py --url http://localhost:8000 --browser /usr/bin/chromium
python scripts/verify_hard_pass_browser.py --url http://localhost:8000 --browser /usr/bin/chromium
```

These checks drive real uploads and API calls. The hard-pass browser script compares telemetry, invoice states, GL cells, and CSV/audit exports after amount/date mutations, wire-fee and discount toggles, custom fee bands, and offline claims. It also checks dataset replacement, keyboard controls, safe-integer rejection, and desktop/mobile overflow. No HTTP responses or computation results are mocked.

## Benchmark

36 open invoices across six synthetic customers, with eight deposits:

| Deposit  | Customer                          |       Cash | Computed valuation                              |
| -------- | --------------------------------- | ---------: | ----------------------------------------------- |
| DEP-9001 | Apex Industrial Supply            | $14,835.00 | $14,850 face − $15 wire fee                     |
| DEP-9002 | Vanguard Medical Systems          | $21,560.00 | $22,000 face − $440 valid discount              |
| DEP-9003 | Kestrel Freight & Logistics       | $18,412.00 | $18,700 face − $164 unearned − $124 earned      |
| DEP-9004 | Northstar Precision Manufacturing |  $9,410.00 | $9,750 face − $340 documented short-pay         |
| DEP-9005 | Meridian Cold Storage             | $11,225.00 | $11,250 face − $25 wire fee                     |
| DEP-9006 | Solstice Building Materials       |  $7,650.00 | Two invoices, exact full value                  |
| DEP-9007 | Apex Industrial Supply            |  $4,890.00 | $5,000 face − $100 earned discount − $10 fee    |
| DEP-9008 | Unknown / Omega Holdings          |  $6,123.45 | Unapplied exception; no forced match or journal |

Baseline: **7/8 deposits**, **$87,982.00** reconciled cash, **$164.00** identified unearned discounts, **$664.00** valid discounts, **$340.00** short-pay disputes, **$50.00** fees, **$0.00** debit/credit variance. Node counts and milliseconds come from each actual run and are never sample constants in the application.

### Live changed-input demo

1. Open **Live input simulator**.
2. Select Vanguard deposit **DEP-9002**.
3. Change clearing date from **2026-10-09** to **2026-10-19**.
4. Click **RE-SOLVE LEDGER**.

Its two discounts retain the same mathematical payment values but move from **GL 4910** to **GL 1215**. Identified recovery rises from **$164.00 to $604.00**. Reset benchmark restores the original source records and runs the solver again.

Changing Apex DEP-9001 from $14,835.00 to $14,850.00 removes the inferred $15 fee. Adding only $0.01 results in an exception under the default fee rules. These outcomes are computed from the submitted records; no deposit ID is a solver instruction.

## How the solver works

`backend/solver.py` implements the multi-state choice branch-and-bound algorithm directly in Python. It has no external subset-sum or optimization dependency.

For each resolved customer and deposit:

1. Exclude already-applied invoices and invoices issued after the clearing date.
2. Generate discrete states per eligible invoice: `FULL`; `EARNED_DISCOUNT` inside its term window; `UNEARNED_DISCOUNT` after that window; and `REMITTANCE_SHORTPAY` when a referenced document supplies a claim.
3. Search subsets of one through `max_subset_size` invoices, choosing at most one state per invoice. Remaining-cardinality face-value upper bounds and the target-plus-fee upper bound prune unreachable branches. Skips are implicit in increasing invoice indices. Recursion depth is bounded by subset size.
4. Accept only exact equality: **sum(selected state values) − permitted wire fee = deposit cents**. A custom band allows every integer-cent fee between its inclusive endpoints; it does not relax the equation.
5. Rank all feasible assignments by explicit remittance hits (descending), sum of state-complexity weights (FULL=0, earned=1, short-pay=2, unearned=3), zero-fee preference, and lexicographic ascending due dates. Fee amount and stable invoice/state/document identifiers break remaining ties. When a documented claim has the same amount as a permitted wire fee, a simpler full-value/fee assignment can outrank the short-pay state under this specified priority; inspect the returned alternatives. Return the best candidate and up to five alternatives, plus the exact candidate count.

Deposits apply in **clearing-date order, then deposit ID**. Matched invoices are reserved once for the run. This is a deterministic per-deposit policy; it is not a global optimization across every possible ordering of an entire bank batch.

Dollar inputs use `int(round(float(value) * 100))` at ingress as specified. Cents inputs accept exact integers. Monetary inputs and ledger totals are constrained to signed 64-bit range. Search uses Python integer arithmetic without overflow or floating-point monetary operations. Discount rates are validated decimals; rational integer arithmetic rounds the selected net amount to cents using round-half-to-even. Use `amount_cents` for large values or direct API integrations that require exact integer ingress. The browser validates all incoming/outgoing monetary numbers against its safe-integer limit (9,007,199,254,740,991 cents) and rejects larger values before applying source data; the Python API retains the full signed-64-bit currency domain. Browser dollar entry and formatting use integer/BigInt scaling, preserving the last cent without floating-point formatting drift.

`perf_counter_ns()` measures actual solver execution, including state-vector construction and bound preparation. A node is one entered search call, including a root or call pruned by bounds. No artificial waiting or simulated telemetry is used. The summary adds each deposit's solver measurements; `request_time_ms` measures the broader reconciliation operation.

### Search limits and exceptions

Defaults: subset size **6**, node budget **2,000,000 per deposit**, entity confidence threshold **0.65**. Accepts up to 2,000 invoices and 500 deposits per request. Subset-size limit is configurable up to 20. Increasing it can make search expensive; branch-and-bound is still combinatorial.

A budget interruption returns **SEARCH_LIMIT**, discards provisional matches, and emits no journal. Unresolved or ambiguous counterparties and impossible exact equations return **UNMATCHED_EXCEPTION**. The engine does not guess a customer from amount alone. Counterparty matching accepts generic token-prefix abbreviations of at least three letters, with ambiguous candidates still routed to review; no customer-specific name branches are used. Search duration depends on source data, configuration, and hardware; sub-5-ms operation is not guaranteed for arbitrary uploads.

## Data import

**Invoice CSV:**

```csv
invoice_id,customer_id,customer_name,invoice_date,due_date,amount_cents,discount_terms,discount_pct,discount_days
CUSTOM-001,CUSTOMER-1,Example Manufacturing,2026-10-01,2026-10-31,100000,2/10 Net 30,0.02,10
```

**Deposit CSV:**

```csv
deposit_id,deposit_date,raw_payer_memo,amount,bank_reference
PAYMENT-001,2026-10-09,ACH EXAMPLE MANUFACTURING,980.00,REFERENCE-01
```

Use ISO dates, unique invoice/deposit IDs, positive amounts, and consistent customer names per customer ID. Either schema accepts dollar `amount` or integer `amount_cents`; explicit cents take precedence when both are supplied. If discount fields are omitted, `2/10 Net 30` terms can supply the rate/window. Explicit rate/window fields take precedence.

Importing a CSV replaces that session's selected source dataset. Frontend input changes are held in memory; a browser reload loads the synthetic benchmark. There is no database or external posting integration.

### Remittance extraction

Upload a text-based PDF or UTF-8 TXT, or paste a note such as:

```text
Customer: Example Manufacturing
Applying $25 debit memo DM-101 against INV-EXAMPLE-001 for damaged goods
```

The deterministic offline parser reads explicit invoice IDs and claim amounts. Put one invoice claim per line for unambiguous attribution. It does not infer an amount when multiple amounts appear in one segment. Review extracted references before applying. Image-only PDFs require pasted text or a text-based document; OCR is not included.

Set `GEMINI_API_KEY` in the Python process environment to enable optional **Gemini 2.5 Flash** extraction. It falls back to the offline parser on provider errors or invalid output. With a key configured, remittance text is sent to Gemini; without one, extraction is local. `.env.example` documents variables, but `.env` is not loaded automatically. Never commit keys.

## API

| Endpoint                                         | Input                                               | Output                                                                                  |
| ------------------------------------------------ | --------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `GET /api/health`                                | —                                                   | Engine health                                                                           |
| `GET /api/sample-data`                           | —                                                   | Labeled synthetic source records                                                        |
| `POST /api/reconcile`                            | Invoices, deposits, remittances, config             | Computed matches, alternatives, proofs, summary, telemetry                              |
| `POST /api/parse-remittance`                     | JSON text, raw text/PDF, or multipart `file`        | Validated references, parser name, warnings                                             |
| `POST /api/import-csv?kind=invoices`             | Raw UTF-8 CSV body                                  | Validated invoice rows                                                                  |
| `POST /api/import-csv?kind=deposits`             | Raw UTF-8 CSV body                                  | Validated deposit rows                                                                  |
| `POST /api/export-journal-csv?vendor=quickbooks` | Reconciliation request                              | QuickBooks journal CSV                                                                  |
| `POST /api/export-journal-csv?vendor=xero`       | Reconciliation request                              | Xero manual journal CSV                                                                 |
| `POST /api/export-audit-json`                    | Reconciliation request                              | Fresh result, source inputs/configuration, source SHA-256, UTC timestamp, and telemetry |
| `POST /api/export-chargebacks-csv`               | Reconciliation request; optional `deposit_id` query | Draft recovery/dispute debit memo summary                                               |

Example request shape:

```json
{
  "invoices": [],
  "deposits": [],
  "remittances": [],
  "config": {
    "allow_wire_fees": true,
    "wire_fee_options_cents": [0, 1000, 1500, 2000, 2500, 3000],
    "wire_fee_band_min_cents": null,
    "wire_fee_band_max_cents": null,
    "allow_discounts": true,
    "max_subset_size": 6,
    "max_nodes": 2000000,
    "entity_match_threshold": 0.65
  }
}
```

Populate the arrays with records; empty ledgers intentionally return structured `422 VALIDATION_ERROR`. Non-solver endpoints report zero solver metrics. All API responses also expose `X-Solver-Time-Ms`, `X-Nodes-Explored`, and measured `X-Request-Time-Ms` headers; CSV responses carry telemetry in these headers. Exports recompute the current request and never trust client-supplied journal lines. The audit JSON’s source hash identifies its canonical inputs; it is not a digital signature.

## Accounting treatment

| GL   | Treatment                                               |
| ---- | ------------------------------------------------------- |
| 1010 | Debit bank cash received                                |
| 6120 | Debit permitted wire fees                               |
| 4910 | Debit valid earned sales discounts                      |
| 1215 | Debit recoverable unearned-discount chargeback AR       |
| 1220 | Debit documented, unapproved short-pay dispute clearing |
| 1200 | Credit face-value AR per matched invoice                |

Each journal must satisfy **∑ debit cents = ∑ credit cents** before it can be returned. Unearned discounts and short-pays generate **draft debit memos for controller review**. “Margin recovery” means identified recoverable AR; it does not mean collected cash. No email, chargeback, journal, or debit memo is sent or posted externally.

QuickBooks exports use journal-import fields; Xero exports use signed manual-journal amounts. Map the sample account names/codes and tax treatment to the target company's chart before importing. Import availability and field requirements depend on the accounting product edition and locale. Draft debit memos are exported separately from balanced journal lines. The inspector’s **Generate debit memo** action exports only the selected deposit’s drafts, after reconciling the entire source batch to preserve invoice allocation. The header export menu exports drafts for the entire ledger.

## Repository

```text
backend/
  main.py                 FastAPI, validation, imports, exports, static serving
  models.py               Typed, validated schemas and currency ingress
  solver.py               Multi-state branch-and-bound; exact integer arithmetic
  reconciliation.py       Counterparty isolation and batch allocation
  entity_resolver.py      Deterministic tokens and edit similarity
  remittance_parser.py    PDF/text and optional Gemini extraction
  ledger_exporter.py      Double-entry verification and vendor CSV formats
  test_solver.py          Benchmark, changes, failure cases, oracle checks
  test_hard_pass.py       Five required API torture scenarios
  test_audit_regressions.py  Validation, boundaries, ambiguity, and audit export
frontend/
  src/App.jsx             Financial operations terminal
  src/components/         Register, proofs, telemetry, simulator, import drawers
sample_data/              Synthetic CSV, JSON, text, and PDF fixtures
scripts/dev.sh            FastAPI + Vite development startup
scripts/audit_static.py   Source red-flag guard
scripts/verify_hard_pass_browser.py  Real end-to-end mutation/export checks
frontend/test/            Exact browser currency tests
```

## License

Copyright (c) 2026 Syedsaadhhh. **Proprietary — all rights reserved.** See [LICENSE](LICENSE). Public source visibility does not grant an open-source license. Third-party packages retain their respective licenses.

````
