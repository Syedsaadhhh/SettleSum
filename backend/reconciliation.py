"""Deterministic chronological cash application with exclusive invoice reservation."""

from time import perf_counter_ns
from .entity_resolver import resolve_counterparty
from .ledger_exporter import make_journal, proof
from .models import ReconcileRequest
from .solver import solve


def reconcile(request: ReconcileRequest):
    started = perf_counter_ns()
    used, matches = set(), []
    nodes = 0
    for deposit in sorted(
        request.deposits, key=lambda x: (x.deposit_date, x.deposit_id)
    ):
        counterparty = resolve_counterparty(
            deposit.raw_payer_memo,
            request.invoices,
            request.config.entity_match_threshold,
        )
        eligible = [
            x
            for x in request.invoices
            if x.customer_id == counterparty["customer_id"] and x.invoice_id not in used
        ]
        invoice_ids = {x.invoice_id for x in eligible}
        remittances = [
            r
            for r in request.remittances
            if (
                r.deposit_id == deposit.deposit_id
                or (
                    r.deposit_id is None
                    and any(x.invoice_id in invoice_ids for x in r.referenced_invoices)
                )
            )
        ]
        result = solve(deposit, eligible, request.config, remittances)
        nodes += result["nodes_explored"]
        match = {
            **deposit.model_dump(mode="json"),
            **{k: v for k, v in result.items() if k != "solution"},
            "counterparty": counterparty,
            "invoices": [],
            "wire_fee_cents": 0,
            "journal_lines": [],
            "chargeback_memos": [],
            "variance_cents": None,
            "reason": (
                ""
                if result["solution"]
                else (
                    "Search budget reached. Increase the node limit or narrow the ledger."
                    if result["status"] == "SEARCH_LIMIT"
                    else (
                        counterparty["reason"]
                        if not counterparty["customer_id"]
                        else "No exact permitted invoice-state combination; controller review required"
                    )
                )
            ),
        }
        if result["solution"]:
            solution = result["solution"]
            match.update(solution)
            match.update(make_journal(deposit, solution))
            match["math_proof"] = proof(solution)
            used.update(x["invoice_id"] for x in solution["invoices"])
        matches.append(match)
    # Preserve the input bank-feed order in the display; allocation is chronological.
    order = {d.deposit_id: i for i, d in enumerate(request.deposits)}
    matches.sort(key=lambda x: order[x["deposit_id"]])
    resolved = [x for x in matches if x["status"] == "MATCHED"]
    state_totals = {
        state: sum(
            i["adjustment_cents"]
            for m in resolved
            for i in m["invoices"]
            if i["state"] == state
        )
        for state in ("EARNED_DISCOUNT", "UNEARNED_DISCOUNT", "REMITTANCE_SHORTPAY")
    }
    total = sum(x.amount_cents for x in request.deposits)
    matched = sum(x["amount_cents"] for x in resolved)
    return {
        "summary": {
            "total_deposits_cents": total,
            "matched_deposits_cents": matched,
            "unmatched_deposits_cents": total - matched,
            "matched_count": len(resolved),
            "deposit_count": len(matches),
            "unearned_discounts_recovered_cents": state_totals["UNEARNED_DISCOUNT"],
            "valid_discounts_cents": state_totals["EARNED_DISCOUNT"],
            "short_pays_cents": state_totals["REMITTANCE_SHORTPAY"],
            "wire_fees_cents": sum(x["wire_fee_cents"] for x in resolved),
            "total_nodes_explored": nodes,
            "solve_time_ms": sum(x["solve_time_ms"] for x in matches),
            "ledger_variance_cents": sum(
                x.get("ledger_variance_cents", 0) for x in matches
            ),
            "invoice_count": len(request.invoices),
            "applied_invoice_count": len(used),
            "allocation_policy": "Deposit clearing date, then deposit ID; each invoice applied at most once.",
            "recovery_status": "Identified and drafted; no collection or external posting performed.",
        },
        "matches": matches,
        "nodes_explored": nodes,
        "solve_time_ms": sum(x["solve_time_ms"] for x in matches),
        "request_time_ms": (perf_counter_ns() - started) / 1_000_000,
    }
