import { Check, ChevronDown, ShieldCheck } from "lucide-react";
import { money, number } from "../utils";
export default function LedgerHeader({ result, busy, dirty }) {
  const s = result?.summary;
  const hasJournal = Boolean(s?.matched_count);
  const rate = s ? (100 * s.matched_count) / s.deposit_count : 0;
  return (
    <div className="ledger-summary">
      <section className="telemetry" aria-label="Reconciliation summary">
        <div className="metric">
          <span className="metric-label">Payments matched</span>
          <strong>{s ? `${rate.toFixed(1)}%` : "0.0%"}</strong>
          <span>
            {s
              ? `${s.matched_count} of ${s.deposit_count} payments resolved`
              : "Add both invoices and payments to reconcile"}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Cash reconciled</span>
          <strong>{money(s?.matched_deposits_cents || 0)}</strong>
          <span>
            {s
              ? `${money(s.total_deposits_cents)} received`
              : "No calculation yet"}
          </span>
        </div>
        <div className="metric recovery-metric">
          <span className="metric-label">Recoverable margin</span>
          <strong className="amber">
            {money(s?.unearned_discounts_recovered_cents || 0)}
          </strong>
          <span>Expired discounts to reclaim, before collection</span>
        </div>
      </section>
      <div className="summary-footer">
        <div className="ledger-proof-strip">
          <span>
            {hasJournal && <ShieldCheck size={17} />}
            <b className={hasJournal ? "green" : "muted"}>
              {hasJournal
                ? "Journal balanced"
                : s
                  ? "No journal generated"
                  : "Awaiting calculation"}
            </b>
            {hasJournal && (
              <span className="proof-equivalence">∑ DEBITS = ∑ CREDITS</span>
            )}
          </span>
          <span className={hasJournal ? "green" : "muted"}>
            {hasJournal && <Check size={15} />}
            {hasJournal
              ? `${money(s.ledger_variance_cents)} variance`
              : s
                ? "Payments remain unapplied"
                : "Add both source files to begin"}
          </span>
        </div>
        <details className="engine-details">
          <summary>
            Solver details
            <ChevronDown size={14} />
          </summary>
          <div className="engine-popover">
            <div className="metric">
              <span className="metric-label">Search nodes</span>
              <strong>{number(s?.total_nodes_explored || 0)}</strong>
              <span>Actual combinatorial search calls</span>
            </div>
            <div className="metric">
              <span className="metric-label">Solver execution</span>
              <strong>
                {s ? s.solve_time_ms.toFixed(3) : "—"}
                <small> ms</small>
              </strong>
              <span>
                {busy
                  ? "Calculating…"
                  : dirty
                    ? "Previous inputs; recalculate to update"
                    : "Measured Python wall-clock time"}
              </span>
            </div>
          </div>
        </details>
      </div>
    </div>
  );
}
