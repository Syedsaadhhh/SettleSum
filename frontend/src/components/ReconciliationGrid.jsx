import {
  ArrowRight,
  Check,
  Search,
  TriangleAlert,
  ChevronDown,
} from "lucide-react";
import { useState } from "react";
import { dateLabel, money } from "../utils";
export default function ReconciliationGrid({
  result,
  selectedId,
  onSelect,
  filter,
  setFilter,
}) {
  const [query, setQuery] = useState("");
  const matches = result?.matches || [];
  const matched = matches.filter((x) => x.status === "MATCHED").length;
  const rows = matches.filter(
    (x) =>
      (filter === "all" ||
        (filter === "matched"
          ? x.status === "MATCHED"
          : x.status !== "MATCHED")) &&
      `${x.deposit_id} ${x.raw_payer_memo} ${x.counterparty.customer_name || ""}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  return (
    <section className="bank-register">
      <div className="panel-heading">
        <h2>
          Bank deposits{" "}
          <span className="count">
            {matches.length.toString().padStart(2, "0")}
          </span>
        </h2>
        <span className="small-label">
          USD <ChevronDown size={12} />
        </span>
      </div>
      <div className="register-filters" aria-label="Filter deposits">
        {[
          ["all", "All deposits", matches.length],
          ["matched", "Matched", matched],
          ["exceptions", "Exceptions", matches.length - matched],
        ].map(([value, label, count]) => (
          <button
            key={value}
            className={filter === value ? "active" : ""}
            onClick={() => setFilter(value)}
          >
            {label}
            <span
              className={
                value === "exceptions" && count ? "exception-count" : ""
              }
            >
              {count}
            </span>
          </button>
        ))}
      </div>
      <label className="search-box">
        <Search size={14} />
        <input
          aria-label="Search deposits"
          placeholder="Search payer or deposit ID…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="search-key">/</span>
      </label>
      <div className="register-column-labels">
        <span>COUNTERPARTY / BANK REFERENCE</span>
        <span>DEPOSIT AMOUNT</span>
      </div>
      <div className="deposit-rows">
        {rows.map((row) => {
          const resolved = row.status === "MATCHED";
          const recovery = row.invoices.some(
            (i) => i.state === "UNEARNED_DISCOUNT",
          );
          return (
            <button
              key={row.deposit_id}
              className={`deposit-row ${selectedId === row.deposit_id ? "selected" : ""}`}
              onClick={() => onSelect(row.deposit_id)}
              aria-pressed={selectedId === row.deposit_id}
            >
              <span className={`row-status ${resolved ? "green" : "amber"}`}>
                {resolved ? <Check size={14} /> : <TriangleAlert size={14} />}
              </span>
              <span className="deposit-description">
                <strong>
                  {row.counterparty.customer_name ||
                    "Unidentified counterparty"}
                </strong>
                <span className="mono muted">
                  {row.deposit_id}
                  <i /> {dateLabel(row.deposit_date)}
                </span>
                <span className="deposit-memo">{row.raw_payer_memo}</span>
              </span>
              <span className="deposit-value">
                <strong className="mono">{money(row.amount_cents)}</strong>
                <span
                  className={recovery ? "amber" : resolved ? "green" : "amber"}
                >
                  {recovery
                    ? "RECOVERY FOUND"
                    : resolved
                      ? `${row.invoices.length} INVOICE${row.invoices.length > 1 ? "S" : ""} MATCHED`
                      : row.status === "SEARCH_LIMIT"
                        ? "SEARCH LIMIT"
                        : "REVIEW REQUIRED"}
                </span>
              </span>
              <ArrowRight size={14} className="row-arrow" />
            </button>
          );
        })}
        {!rows.length && (
          <div className="empty-state">
            <Search size={22} />
            <h3>No deposits found</h3>
            <p>Try another payer name or choose All deposits.</p>
            <button
              onClick={() => {
                setQuery("");
                setFilter("all");
              }}
            >
              Clear filters
            </button>
          </div>
        )}
      </div>
      <div className="register-footer">
        <span>
          <span className="status-dot" /> {rows.length} DEPOSITS IN VIEW
        </span>
        <span className="mono">EXACT CENTS ONLY</span>
      </div>
      <div className="register-note">
        <span className="small-label">APPLICATION POLICY</span>
        <p>
          Clearing date, then deposit ID.
          <br />
          Each invoice is applied once per ledger run.
        </p>
      </div>
    </section>
  );
}
