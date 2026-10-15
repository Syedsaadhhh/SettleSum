import { useRef, useState } from "react";
import { Check, FileText, Upload, ArrowUpRight } from "lucide-react";
import Drawer from "./Drawer";
import { api, money, readJson, download, saveBlob } from "../utils";
export default function RemittanceDropzone({
  data,
  onClose,
  onApply,
  busy,
  backendError,
}) {
  const [tab, setTab] = useState("csv");
  const [kind, setKind] = useState("invoices");
  const [rows, setRows] = useState(null);
  const [text, setText] = useState("");
  const [depositId, setDepositId] = useState("");
  const [parsed, setParsed] = useState(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [filename, setFilename] = useState("");
  const fileRef = useRef(null);
  function template(kind) {
    const headers =
      kind === "invoices"
        ? "invoice_id,customer_name,invoice_date,amount,discount_terms,customer_id,due_date"
        : "deposit_id,deposit_date,raw_payer_memo,amount,bank_reference";
    saveBlob(
      new Blob([headers + "\r\n"], { type: "text/csv;charset=utf-8" }),
      `blank-${kind}-template.csv`,
    );
  }
  async function exportSource(kind = "ledger") {
    setPending(true);
    setError("");
    try {
      await download(
        `/api/export-source-csv?kind=${kind}`,
        data,
        kind === "ledger"
          ? "settlesum-ledger-csv.zip"
          : `settlesum-${kind}.csv`,
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(false);
    }
  }
  async function importFile(file) {
    if (!file) return;
    setError("");
    setPending(true);
    setRows(null);
    setParsed(null);
    setFilename(file.name);
    try {
      if (tab === "csv") {
        const response = await api(
          `/api/import-csv?kind=${kind}`,
          await file.text(),
          { "Content-Type": "text/csv" },
        );
        setRows((await readJson(response)).rows);
      } else {
        const form = new FormData();
        form.append("file", file);
        form.append(
          "known_invoice_ids",
          JSON.stringify(data.invoices.map((r) => r.invoice_id)),
        );
        if (depositId) form.append("deposit_id", depositId);
        const response = await api("/api/parse-remittance", form, {});
        setParsed(await readJson(response));
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(false);
    }
  }
  async function parseText() {
    setPending(true);
    setError("");
    setParsed(null);
    try {
      setParsed(
        await readJson(
          await api("/api/parse-remittance", {
            text,
            known_invoice_ids: data.invoices.map((r) => r.invoice_id),
            deposit_id: depositId || null,
            document_id: `REM-TEXT-${Date.now()}`,
          }),
        ),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(false);
    }
  }
  async function apply() {
    const next =
      tab === "csv"
        ? { ...data, [kind]: rows }
        : {
            ...data,
            remittances: [
              ...data.remittances,
              parsed && {
                document_id: parsed.document_id,
                deposit_id: parsed.deposit_id,
                customer_name: parsed.customer_name,
                raw_text: parsed.raw_text,
                referenced_invoices: parsed.referenced_invoices,
              },
            ],
          };
    if (await onApply(next)) onClose();
  }
  return (
    <Drawer
      title="Import ledger data"
      subtitle="Your files. The same exact-cent solver."
      onClose={onClose}
    >
      <div className="drawer-body">
        <div className="drawer-tabs">
          <button
            className={tab === "csv" ? "active" : ""}
            onClick={() => {
              setTab("csv");
              setRows(null);
              setParsed(null);
              setError("");
            }}
          >
            Invoice & deposit CSV
          </button>
          <button
            className={tab === "remittance" ? "active" : ""}
            onClick={() => {
              setTab("remittance");
              setRows(null);
              setParsed(null);
              setError("");
            }}
          >
            PDF / text remittance
          </button>
        </div>
        {tab === "csv" ? (
          <>
            <details
              className="csv-tools"
              aria-label="CSV templates and source exports"
            >
              <summary>CSV templates & downloads</summary>
              <button onClick={() => template("invoices")}>
                Download Blank Invoice CSV Template
              </button>
              <button onClick={() => template("deposits")}>
                Download Blank Deposit CSV Template
              </button>
              <button
                onClick={() => exportSource()}
                disabled={
                  pending ||
                  busy ||
                  (!data.invoices.length && !data.deposits.length)
                }
              >
                Download Current Ledger as CSV
              </button>
              <p className="help-text">
                The ledger download is a ZIP containing separate invoice and
                deposit CSV files, plus remittance JSON. Unzip, edit, and import
                each CSV in either order.
              </p>
              <button
                onClick={() => exportSource(kind)}
                disabled={pending || busy || !data[kind].length}
              >
                Download {kind === "invoices" ? "invoice" : "deposit"} CSV only
              </button>
            </details>
            <label className="field-label">
              Dataset to replace
              <select
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value);
                  setRows(null);
                }}
              >
                <option value="invoices">Open invoice ledger</option>
                <option value="deposits">Bank deposits</option>
              </select>
            </label>
            <p className="help-text">
              A validated CSV replaces the selected dataset for this session.
              Import either file first. The solver runs when invoices and
              deposits are both present.
            </p>
          </>
        ) : (
          <>
            <label className="field-label">
              Link to bank deposit
              <select
                value={depositId}
                onChange={(e) => {
                  setDepositId(e.target.value);
                  setParsed(null);
                }}
              >
                <option value="">Auto-link by exact invoice reference</option>
                {data.deposits.map((d) => (
                  <option key={d.deposit_id} value={d.deposit_id}>
                    {d.deposit_id} · {money(d.amount_cents)}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}
        <div
          className="dropzone"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            importFile(e.dataTransfer.files[0]);
          }}
        >
          <Upload size={26} />
          <strong>
            {pending
              ? "Reading and validating…"
              : `Drop your ${tab === "csv" ? "CSV" : "PDF or text"} file here`}
          </strong>
          <span>
            {tab === "csv"
              ? "UTF-8 CSV · keep files under 4 MB"
              : "Text-based PDF or TXT · keep files under 4 MB"}
          </span>
          <button onClick={() => fileRef.current.click()} disabled={pending}>
            Browse files <ArrowUpRight size={13} />
          </button>
          <input
            ref={fileRef}
            type="file"
            className="visually-hidden"
            aria-label="Upload file"
            accept={tab === "csv" ? ".csv" : ".pdf,.txt"}
            onChange={(e) => {
              importFile(e.target.files[0]);
              e.target.value = "";
            }}
          />
        </div>
        {tab === "csv" ? (
          <details className="schema-help">
            <summary>Flexible column schema</summary>
            <pre>
              {kind === "invoices"
                ? "invoice_id, customer_name, invoice_date, amount\nOptional: customer_id, due_date, discount_terms,\ndiscount_pct, discount_days"
                : "deposit_id, deposit_date, raw_payer_memo,\namount, bank_reference"}
            </pre>
            <p>
              Dates: YYYY-MM-DD. Use amount_cents as an integer, or amount in
              dollars. Negative values are rejected. Missing customer IDs are
              derived from customer names; missing due dates use Net terms (30
              days by default). Headers such as Invoice ID, Customer, Terms,
              Clearing Date, and Bank Memo are accepted. Blank optional discount
              fields use defaults.
            </p>
          </details>
        ) : (
          <>
            <div className="or-divider">OR PASTE REMITTANCE TEXT</div>
            <label className="visually-hidden" htmlFor="remittance-text">
              Remittance text
            </label>
            <textarea
              id="remittance-text"
              rows="6"
              placeholder={
                "Paste the customer, exact invoice reference, deduction amount, and reason from your remittance advice."
              }
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setParsed(null);
              }}
            />
            <button
              className="parse-button"
              disabled={!text.trim() || pending}
              onClick={parseText}
            >
              <FileText size={14} />
              {pending ? "Parsing source…" : "Extract remittance references"}
            </button>
          </>
        )}
        {rows && (
          <div className="validation-success">
            <Check size={15} />
            <span>
              <b>{rows.length} rows validated</b>
              <small>{filename} · Ready to reconcile</small>
            </span>
          </div>
        )}
        {parsed && (
          <div className="parsed-results">
            <h3>
              {parsed.referenced_invoices.length} invoice references extracted
            </h3>
            <span className="small-label">PARSER: {parsed.parser}</span>
            {parsed.referenced_invoices.map((r, i) => (
              <div key={i}>
                <span className="mono">{r.invoice_id}</span>
                <span className="mono amber">
                  {money(r.deduction_cents)} claim
                </span>
              </div>
            ))}
            {parsed.warning && <p className="amber">{parsed.warning}</p>}
            <p className="help-text">
              Review extracted references before applying. Ambiguous claims
              require a separate line for each invoice.
            </p>
          </div>
        )}
        {(error || backendError) && (
          <p role="alert" className="inline-error">
            {error || backendError}
          </p>
        )}
        <div className="drawer-actions">
          <span>
            Files are processed for this session. No external posting.
          </span>
          <button
            className="primary-button"
            disabled={
              busy ||
              pending ||
              !(tab === "csv" ? rows : parsed?.referenced_invoices.length)
            }
            onClick={apply}
          >
            <Check size={14} />
            {busy ? "RECONCILING…" : "APPLY & RECONCILE"}
          </button>
        </div>
      </div>
    </Drawer>
  );
}
