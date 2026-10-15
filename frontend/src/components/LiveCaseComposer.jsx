import { useState } from "react";
import { Plus, Trash2, Play } from "lucide-react";
import Drawer from "./Drawer";
import { api, readJson, centsToDollars, money } from "../utils";
import {
  addDays,
  buildRecords,
  makeRecordId,
  previewSum,
  todayISO,
} from "../composer";

const newInvoice = () => ({
  key: crypto.randomUUID(),
  invoice_id: makeRecordId("INV"),
  invoice_date: todayISO(),
  due_date: addDays(todayISO(), 30),
  amount: "",
  discount_terms: "Net 30",
  selected: true,
});
const newDeposit = (name) => ({
  key: crypto.randomUUID(),
  deposit_id: makeRecordId("DEP"),
  deposit_date: todayISO(),
  raw_payer_memo: name ? `WIRE IN: ${name}` : "",
  memoEdited: false,
  amount: "",
});

export default function LiveCaseComposer({
  data,
  onClose,
  onRun,
  busy,
  backendError,
}) {
  const [mode, setMode] = useState("fresh");
  const [customerName, setCustomerName] = useState("");
  const [customerId, setCustomerId] = useState(() => makeRecordId("CUSTOMER"));
  const [invoices, setInvoices] = useState(() => [newInvoice()]);
  const [deposits, setDeposits] = useState(() => [newDeposit("")]);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [parsing, setParsing] = useState(false);
  const locked = busy || parsing;
  let sum = null;
  try {
    sum = previewSum(invoices);
  } catch {
    /* Incomplete rows remain input fields. */
  }
  const updateInvoice = (key, field, value) =>
    setInvoices((rows) =>
      rows.map((row) => (row.key === key ? { ...row, [field]: value } : row)),
    );
  const updateDeposit = (key, field, value) =>
    setDeposits((rows) =>
      rows.map((row) =>
        row.key === key
          ? {
              ...row,
              [field]: value,
              ...(field === "raw_payer_memo" ? { memoEdited: true } : {}),
            }
          : row,
      ),
    );
  const setHelper = (key, type) => {
    try {
      const value =
        previewSum(invoices, type === "discount" ? 2 : 0) -
        (type === "wire" ? 1500 : 0);
      if (value <= 0)
        throw new Error(
          "Select invoices with a positive total greater than the adjustment.",
        );
      updateDeposit(key, "amount", centsToDollars(value));
      setError("");
    } catch (e) {
      setError(e.message);
    }
  };
  async function submit(event) {
    event.preventDefault();
    setError("");
    setParsing(true);
    try {
      const records = buildRecords({
        customerName,
        customerId,
        invoices,
        deposits,
      });
      if (note.trim()) {
        const parsed = await readJson(
          await api("/api/parse-remittance", {
            text: note,
            known_invoice_ids: [
              ...(mode === "append" ? data.invoices : []),
              ...records.invoices,
            ].map((r) => r.invoice_id),
            document_id: makeRecordId("REM"),
          }),
        );
        if (!parsed.referenced_invoices.length)
          throw new Error(
            "No invoice reference was extracted from the note. Use an explicit invoice ID and review the text.",
          );
        records.remittances.push({
          document_id: parsed.document_id,
          deposit_id: parsed.deposit_id,
          customer_name: parsed.customer_name,
          raw_text: parsed.raw_text,
          referenced_invoices: parsed.referenced_invoices,
        });
      }
      const next =
        mode === "append"
          ? {
              invoices: [...data.invoices, ...records.invoices],
              deposits: [...data.deposits, ...records.deposits],
              remittances: [...data.remittances, ...records.remittances],
            }
          : records;
      if (await onRun(next)) onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setParsing(false);
    }
  }
  return (
    <Drawer
      title="Build live test case"
      subtitle="Create source records. Run the exact same Python solver."
      onClose={onClose}
      wide
    >
      <form className="composer-form" onSubmit={submit}>
        <fieldset disabled={locked} className="composer-fields">
          <div className="composer-intro">
            <label className="field-label">
              Workspace action
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="fresh">Start a fresh ledger</option>
                <option value="append">
                  Add to current ledger ({data.invoices.length} invoices /{" "}
                  {data.deposits.length} deposits)
                </option>
              </select>
            </label>
            <p className="help-text">
              {mode === "fresh"
                ? "Replaces the active ledger after a successful solver response."
                : "Appends these records and reconciles the entire ledger again. Use unique IDs."}
            </p>
          </div>
          <div className="composer-customer">
            <label className="field-label">
              Customer name
              <input
                required
                maxLength={200}
                value={customerName}
                placeholder="Enter any business name"
                onChange={(e) => {
                  const name = e.target.value;
                  setCustomerName(name);
                  setDeposits((rows) =>
                    rows.map((r) =>
                      r.memoEdited
                        ? r
                        : {
                            ...r,
                            raw_payer_memo: name ? `WIRE IN: ${name}` : "",
                          },
                    ),
                  );
                }}
              />
            </label>
            <label className="field-label">
              Customer ID
              <input
                required
                maxLength={100}
                className="mono"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
              />
            </label>
          </div>
          <div className="composer-section-heading">
            <h3>01 / OPEN INVOICES</h3>
            <button
              type="button"
              onClick={() => setInvoices((rows) => [...rows, newInvoice()])}
            >
              <Plus size={13} /> Add invoice
            </button>
          </div>
          <p className="help-text">
            Select rows for the amount helpers. All invoice rows below are
            submitted to the solver.
          </p>
          {invoices.map((row, index) => (
            <fieldset className="composer-record" key={row.key}>
              <legend>Invoice {index + 1}</legend>
              <div className="composer-record-actions">
                <label className="checkbox-field">
                  <input
                    type="checkbox"
                    checked={row.selected}
                    onChange={(e) =>
                      updateInvoice(row.key, "selected", e.target.checked)
                    }
                  />
                  Include in preview
                </label>
                <button
                  type="button"
                  aria-label={`Remove invoice ${index + 1}`}
                  disabled={invoices.length === 1}
                  onClick={() =>
                    setInvoices((rows) => rows.filter((r) => r.key !== row.key))
                  }
                >
                  <Trash2 size={13} /> Remove
                </button>
              </div>
              <div className="composer-invoice-grid">
                <label className="field-label">
                  Invoice ID
                  <input
                    required
                    maxLength={100}
                    value={row.invoice_id}
                    onChange={(e) =>
                      updateInvoice(row.key, "invoice_id", e.target.value)
                    }
                  />
                </label>
                <label className="field-label">
                  Invoice date
                  <input
                    required
                    type="date"
                    value={row.invoice_date}
                    onChange={(e) =>
                      updateInvoice(row.key, "invoice_date", e.target.value)
                    }
                  />
                </label>
                <label className="field-label">
                  Due date
                  <input
                    required
                    type="date"
                    min={row.invoice_date}
                    value={row.due_date}
                    onChange={(e) =>
                      updateInvoice(row.key, "due_date", e.target.value)
                    }
                  />
                </label>
                <label className="field-label">
                  Invoice amount ($)
                  <input
                    required
                    inputMode="decimal"
                    placeholder="0.00"
                    value={row.amount}
                    onChange={(e) =>
                      updateInvoice(row.key, "amount", e.target.value)
                    }
                  />
                </label>
                <label className="field-label">
                  Discount terms
                  <select
                    aria-label="Discount terms"
                    value={row.discount_terms}
                    onChange={(e) =>
                      updateInvoice(row.key, "discount_terms", e.target.value)
                    }
                  >
                    <option value="Net 30">None (Net 30)</option>
                    <option>2/10 Net 30</option>
                    <option>1/10 Net 30</option>
                  </select>
                </label>
              </div>
            </fieldset>
          ))}
          <div className="composer-sum">
            <span>
              AUTO-SUM SELECTED INVOICES{" "}
              <small>
                {invoices.filter((r) => r.selected).length} selected
              </small>
            </span>
            <strong className="mono">
              {sum === null ? "Enter amounts" : money(sum)}
            </strong>
          </div>
          <div className="composer-section-heading">
            <h3>02 / BANK DEPOSITS</h3>
            <button
              type="button"
              onClick={() =>
                setDeposits((rows) => [...rows, newDeposit(customerName)])
              }
            >
              <Plus size={13} /> Add deposit
            </button>
          </div>
          {deposits.map((row, index) => (
            <fieldset className="composer-record" key={row.key}>
              <legend>Deposit {index + 1}</legend>
              <div className="composer-record-actions">
                <span className="muted">Bank source record</span>
                <button
                  type="button"
                  aria-label={`Remove deposit ${index + 1}`}
                  disabled={deposits.length === 1}
                  onClick={() =>
                    setDeposits((rows) => rows.filter((r) => r.key !== row.key))
                  }
                >
                  <Trash2 size={13} /> Remove
                </button>
              </div>
              <div className="composer-deposit-grid">
                <label className="field-label">
                  Deposit ID
                  <input
                    required
                    maxLength={100}
                    value={row.deposit_id}
                    onChange={(e) =>
                      updateDeposit(row.key, "deposit_id", e.target.value)
                    }
                  />
                </label>
                <label className="field-label">
                  Clearing date
                  <input
                    required
                    type="date"
                    value={row.deposit_date}
                    onChange={(e) =>
                      updateDeposit(row.key, "deposit_date", e.target.value)
                    }
                  />
                </label>
                <label className="field-label">
                  Deposit amount ($)
                  <input
                    required
                    inputMode="decimal"
                    placeholder="0.00"
                    value={row.amount}
                    onChange={(e) =>
                      updateDeposit(row.key, "amount", e.target.value)
                    }
                  />
                </label>
                <label className="field-label composer-memo">
                  Raw bank memo
                  <input
                    required
                    maxLength={2000}
                    value={row.raw_payer_memo}
                    onChange={(e) =>
                      updateDeposit(row.key, "raw_payer_memo", e.target.value)
                    }
                  />
                </label>
              </div>
              <div className="amount-helpers">
                <span>SET AMOUNT</span>
                <button
                  type="button"
                  onClick={() => setHelper(row.key, "exact")}
                >
                  Exact Sum
                </button>
                <button
                  type="button"
                  onClick={() => setHelper(row.key, "wire")}
                >
                  Sum minus $15 Wire Fee
                </button>
                <button
                  type="button"
                  onClick={() => setHelper(row.key, "discount")}
                >
                  Sum minus 2% Discount
                </button>
              </div>
            </fieldset>
          ))}
          <p className="help-text">
            Helpers fill source amounts only. Discount eligibility, fees,
            allocations, and all accounting proofs are computed by the backend.
            For multiple payments, select each payment’s invoices before using a
            helper.
          </p>
          <label className="field-label">
            03 / OPTIONAL REMITTANCE NOTE
            <textarea
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Paste a note with an invoice ID, deduction amount, and reason"
            />
          </label>
          <p className="help-text">
            Remittance text is parsed before reconciliation. Use one claim per
            line and an exact invoice ID. Review applied references in the
            documents view.
          </p>
        </fieldset>
        {(error || backendError) && (
          <div className="error-banner" role="alert">
            {error || backendError}
          </div>
        )}
        <div className="composer-submit">
          <span>
            Integer cents · actual search telemetry · balanced journal
          </span>
          <button type="submit" className="primary-button" disabled={locked}>
            <Play size={14} />
            {locked ? "RUNNING…" : "RUN SOLVER ON THIS LEDGER"}
          </button>
        </div>
      </form>
    </Drawer>
  );
}
