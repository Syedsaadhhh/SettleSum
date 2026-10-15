import {
  ArrowDownToLine,
  Check,
  ChevronDown,
  FileText,
  Link2,
  ShieldCheck,
  SlidersHorizontal,
  TriangleAlert,
  ArrowUpRight,
} from "lucide-react";
import { useState } from "react";
import { money, number, stateLabels } from "../utils";
export default function MathProofInspector({
  match,
  onSimulate,
  onMemo,
  busy,
  remittances,
}) {
  const [tab, setTab] = useState("proof");
  if (!match)
    return (
      <section className="proof-inspector">
        <div className="empty-state">
          <FileText size={26} />
          <h2>Select a bank deposit</h2>
          <p>
            Invoice valuations and accounting proof appear here after
            reconciliation.
          </p>
        </div>
      </section>
    );
  const resolved = match.status === "MATCHED";
  const recovery = match.invoices
    .filter((x) => x.state === "UNEARNED_DISCOUNT")
    .reduce((s, x) => s + x.adjustment_cents, 0);
  const face = match.invoices.reduce((s, x) => s + x.face_value_cents, 0);
  const earned = match.invoices
    .filter((x) => x.state === "EARNED_DISCOUNT")
    .reduce((s, x) => s + x.adjustment_cents, 0);
  const shortpay = match.invoices
    .filter((x) => x.state === "REMITTANCE_SHORTPAY")
    .reduce((s, x) => s + x.adjustment_cents, 0);
  const relevantDocs = remittances.filter(
    (r) =>
      r.deposit_id === match.deposit_id ||
      r.referenced_invoices.some((ref) =>
        match.invoices.some((i) => i.invoice_id === ref.invoice_id),
      ),
  );
  return (
    <section className="proof-inspector">
      <div className="panel-heading">
        <h2>Reconciliation inspector</h2>
        <span className="small-label mono">{match.deposit_id}</span>
      </div>
      <div className="inspector-identity">
        <div>
          <span className={`badge ${resolved ? "green" : "amber"}`}>
            {resolved ? <Check size={11} /> : <TriangleAlert size={11} />}{" "}
            {resolved ? "VERIFIED MATCH" : "CONTROLLER REVIEW"}
          </span>
          <h2>
            {match.counterparty.customer_name || "Unidentified counterparty"}
          </h2>
          <p className="mono">
            {match.deposit_id} <span>/</span> {match.deposit_date}{" "}
            <span>/</span> {match.bank_reference || "NO BANK REFERENCE"}
          </p>
        </div>
        <div className="inspector-amount">
          <strong>{money(match.amount_cents)}</strong>
          <span>NET BANK DEPOSIT</span>
        </div>
      </div>
      <div className="inspector-meta">
        <span>
          <Link2 size={12} /> ENTITY CONFIDENCE{" "}
          <b className="mono">{(match.counterparty.score * 100).toFixed(0)}%</b>
        </span>
        <button className="text-button" onClick={onSimulate}>
          <SlidersHorizontal size={12} /> Test different inputs{" "}
          <ArrowUpRight size={12} />
        </button>
      </div>
      <div className="inspector-tabs">
        <button
          className={tab === "proof" ? "active" : ""}
          onClick={() => setTab("proof")}
        >
          Matching proof
        </button>
        <button
          className={tab === "sources" ? "active" : ""}
          onClick={() => setTab("sources")}
        >
          Remittance & source <span>{relevantDocs.length}</span>
        </button>
      </div>
      {tab === "sources" ? (
        <div className="source-content">
          <h3>Bank feed source</h3>
          <pre>{match.raw_payer_memo}</pre>
          <h3>Counterparty resolution</h3>
          <p>{match.counterparty.reason}</p>
          <div className="candidate-list">
            {match.counterparty.candidates.map((c) => (
              <div key={c.customer_id}>
                <span>{c.customer_name}</span>
                <span className="mono">{(c.score * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
          <h3>Referenced remittance documents</h3>
          {relevantDocs.length ? (
            relevantDocs.map((r, i) => (
              <div key={i}>
                <span className="mono blue">{r.document_id}</span>
                <pre>{r.raw_text}</pre>
              </div>
            ))
          ) : (
            <p className="muted">
              No explicit remittance attached. This match uses invoice amounts,
              terms, dates, and permitted fees.
            </p>
          )}
        </div>
      ) : (
        <>
          {!resolved ? (
            <div className="exception-state">
              <TriangleAlert size={26} />
              <h3>
                {match.status === "SEARCH_LIMIT"
                  ? "Search budget reached"
                  : "No exact reconciliation found"}
              </h3>
              <p>{match.reason}</p>
              <div>
                <span>BANK DEPOSIT</span>
                <strong className="mono">{money(match.amount_cents)}</strong>
              </div>
              <div>
                <span>ELIGIBLE OPEN INVOICES</span>
                <strong className="mono">{match.eligible_invoices}</strong>
              </div>
              <p>
                Payment remains unapplied. No journal entry or debit memo has
                been generated.
              </p>
              <button onClick={onSimulate}>
                <SlidersHorizontal size={14} /> Review inputs & rules
              </button>
            </div>
          ) : (
            <>
              {recovery > 0 && (
                <div className="recovery-notice">
                  <TriangleAlert size={16} />
                  <div>
                    <strong>
                      Unearned discount detected{" "}
                      <span className="mono">{money(recovery)}</span>
                    </strong>
                    <p>
                      Discount taken after the payment window. Chargeback AR is
                      ready for review.
                    </p>
                  </div>
                  <span className="badge amber">RECOVERABLE</span>
                </div>
              )}
              {shortpay > 0 && (
                <div className="recovery-notice">
                  <FileText size={16} />
                  <div>
                    <strong>
                      Documented short-pay claim{" "}
                      <span className="mono">{money(shortpay)}</span>
                    </strong>
                    <p>
                      Unapproved claim routed to GL 1220 for controller review.
                    </p>
                  </div>
                </div>
              )}
              <div className="section-heading">
                <h3>Multi-state invoice equation</h3>
                <span className="small-label">
                  {match.invoices.length} INVOICES · {match.candidate_count}{" "}
                  VALID SOLUTION{match.candidate_count !== 1 ? "S" : ""}
                </span>
              </div>
              <div className="table-scroll">
                <table className="invoice-proof-table">
                  <thead>
                    <tr>
                      <th>INVOICE / DUE DATE</th>
                      <th className="numeric">FACE VALUE</th>
                      <th>SELECTED STATE</th>
                      <th className="numeric">APPLIED VALUE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {match.invoices.map((item) => (
                      <tr key={item.invoice_id}>
                        <td>
                          <strong className="mono">{item.invoice_id}</strong>
                          <span className="secondary mono">
                            Due {item.due_date}
                          </span>
                        </td>
                        <td className="numeric mono">
                          {money(item.face_value_cents)}
                        </td>
                        <td>
                          <span
                            className={`state-badge ${item.state === "UNEARNED_DISCOUNT" ? "amber" : item.state === "EARNED_DISCOUNT" ? "blue" : item.state === "REMITTANCE_SHORTPAY" ? "amber" : "muted"}`}
                          >
                            {stateLabels[item.state]}
                          </span>
                          <span className="secondary mono">
                            {item.state === "FULL"
                              ? "No adjustment"
                              : `${money(item.adjustment_cents)} deduction`}
                          </span>
                        </td>
                        <td className="numeric mono">
                          {money(item.value_cents)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="equation-totals">
                <div>
                  <span>Invoice face value</span>
                  <b className="mono">{money(face)}</b>
                </div>
                {earned > 0 && (
                  <div>
                    <span>
                      Valid early-payment discount{" "}
                      <span className="mono">GL 4910</span>
                    </span>
                    <b className="mono">− {money(earned)}</b>
                  </div>
                )}
                {recovery > 0 && (
                  <div className="amber">
                    <span>
                      Unearned discount · chargeback AR{" "}
                      <span className="mono">GL 1215</span>
                    </span>
                    <b className="mono">− {money(recovery)}</b>
                  </div>
                )}
                {shortpay > 0 && (
                  <div className="amber">
                    <span>
                      Short-pay dispute <span className="mono">GL 1220</span>
                    </span>
                    <b className="mono">− {money(shortpay)}</b>
                  </div>
                )}
                {match.wire_fee_cents > 0 && (
                  <div>
                    <span>
                      Permitted bank wire fee{" "}
                      <span className="mono">GL 6120</span>
                    </span>
                    <b className="mono">− {money(match.wire_fee_cents)}</b>
                  </div>
                )}
                <div className="equation-result">
                  <span>
                    <Check size={14} /> EXACT DEPOSIT MATCH
                  </span>
                  <b className="mono">
                    {money(match.amount_cents)} <small>USD</small>
                  </b>
                </div>
              </div>
              <div className="section-heading journal-heading">
                <h3>Double-entry journal</h3>
                <span className="small-label green">
                  <ShieldCheck size={12} /> BALANCED
                </span>
              </div>
              <div className="table-scroll">
                <table className="journal-table">
                  <thead>
                    <tr>
                      <th>GL</th>
                      <th>ACCOUNT / REFERENCE</th>
                      <th className="numeric">DEBIT</th>
                      <th className="numeric">CREDIT</th>
                    </tr>
                  </thead>
                  <tbody>
                    {match.journal_lines.map((line, i) => (
                      <tr key={i}>
                        <td
                          className={`mono ${line.gl_account === "1215" ? "amber" : "muted"}`}
                        >
                          {line.gl_account}
                        </td>
                        <td>
                          {line.account_name}
                          <span className="journal-ref mono">
                            {line.invoice_id || ""}
                            {line.document_id ? ` / ${line.document_id}` : ""}
                          </span>
                        </td>
                        <td className="numeric mono">
                          {line.debit_cents ? (
                            money(line.debit_cents)
                          ) : (
                            <span className="faint">—</span>
                          )}
                        </td>
                        <td className="numeric mono">
                          {line.credit_cents ? (
                            money(line.credit_cents)
                          ) : (
                            <span className="faint">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td colSpan="2">
                        ∑ TOTAL <span className="green">ZERO VARIANCE</span>
                      </td>
                      <td className="numeric mono">
                        {money(match.debits_cents)}
                      </td>
                      <td className="numeric mono">
                        {money(match.credits_cents)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
              {match.chargeback_memos.length > 0 && (
                <div className="memo-action">
                  <span>
                    <FileText size={15} />
                    <span>
                      {match.chargeback_memos.length} draft debit memo
                      {match.chargeback_memos.length !== 1
                        ? "s"
                        : ""} ready{" "}
                      <small>Controller approval required before posting</small>
                    </span>
                  </span>
                  <button onClick={onMemo} disabled={busy}>
                    <ArrowDownToLine size={13} /> Generate debit memo
                  </button>
                </div>
              )}
              <details className="algorithm-details">
                <summary>
                  Search & ranking details <ChevronDown size={13} />
                </summary>
                <p className="mono">
                  {number(match.nodes_explored)} nodes ·{" "}
                  {match.solve_time_ms.toFixed(3)} ms · exhaustive search
                  complete
                </p>
                <p>
                  Rank: remittance hits → state complexity → zero wire fee →
                  oldest due dates.
                </p>
                <pre>{match.math_proof}</pre>
                {match.alternatives.map((a, i) => (
                  <div key={i}>
                    <h4>
                      Alternative {i + 1} · complexity{" "}
                      {a.rank_score.state_complexity}
                    </h4>
                    <p className="mono">
                      {a.invoices
                        .map((x) => `${x.invoice_id} [${x.state}]`)
                        .join(" + ")}{" "}
                      − {money(a.wire_fee_cents)} fee
                    </p>
                  </div>
                ))}
              </details>
            </>
          )}
        </>
      )}
      <div className="inspector-footer">
        <span>
          <span className="status-dot" />{" "}
          {match.search_complete
            ? "DETERMINISTIC SEARCH COMPLETE"
            : "SEARCH INCOMPLETE"}
        </span>
        <span className="mono">
          {number(match.nodes_explored)} NODES /{" "}
          {match.solve_time_ms.toFixed(3)} ms
        </span>
      </div>
    </section>
  );
}
