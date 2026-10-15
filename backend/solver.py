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
