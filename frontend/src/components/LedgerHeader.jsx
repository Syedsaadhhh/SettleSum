import { Activity, ArrowUpRight, Check, ShieldCheck } from "lucide-react";
import { money, number } from "../utils";
export default function LedgerHeader({ result, busy, dirty }) {
  const s = result?.summary;
  const rate = s ? (100 * s.matched_count) / s.deposit_count : 0;
  return (
    <>
      <section
        className="telemetry"
        aria-label="Measured reconciliation telemetry"
      >
        <div className="metric">
          <span className="metric-label">
            RECONCILIATION RATE <Activity size={13} />
          </span>
          <strong className="green">{s ? `${rate.toFixed(1)}%` : "—"}</strong>
          <span>
            {s
              ? `${s.matched_count} of ${s.deposit_count} deposits resolved`
              : "Awaiting solver"}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">
            CASH RECONCILED <ArrowUpRight size={13} />
          </span>
          <strong>{s ? money(s.matched_deposits_cents) : "—"}</strong>
          <span>
            {s
              ? `${money(s.total_deposits_cents)} total bank deposits`
              : "Exact cent arithmetic"}
          </span>
        </div>
        <div className="metric recovery-metric">
          <span className="metric-label">
            MARGIN RECOVERY <ArrowUpRight size={13} />
          </span>
          <strong className="amber">
            {s ? money(s.unearned_discounts_recovered_cents) : "—"}
          </strong>
          <span>Unearned discounts identified</span>
        </div>
        <div className="metric">
          <span className="metric-label">SEARCH NODES</span>
          <strong>{s ? number(s.total_nodes_explored) : "—"}</strong>
          <span>Combinatorial states evaluated</span>
        </div>
        <div className="metric">
          <span className="metric-label">
            SOLVER EXECUTION{" "}
            <span className={`status-dot ${busy ? "working" : ""}`} />
          </span>
          <strong>
            {s ? s.solve_time_ms.toFixed(3) : "—"}
            <small> ms</small>
          </strong>
          <span>
            {busy
              ? "Running branch-and-bound"
              : dirty
                ? "Results from previous inputs"
                : "Measured Python wall-clock time"}
          </span>
        </div>
      </section>
      <div className="ledger-proof-strip">
        <span>
          <ShieldCheck size={14} />
          <b>DOUBLE-ENTRY VERIFIED</b>
          <i className="strip-divider" /> ∑ DEBITS = ∑ CREDITS
        </span>
        <span className={s?.ledger_variance_cents ? "red" : "green"}>
          <Check size={13} />
          {s ? money(s.ledger_variance_cents) : "—"} DR / CR VARIANCE
        </span>
      </div>
    </>
  );
}
