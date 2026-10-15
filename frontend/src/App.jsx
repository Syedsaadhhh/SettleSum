import { useCallback, useState } from "react";
import {
  ArrowDownToLine,
  ArrowLeftRight,
  BookOpen,
  Check,
  ChevronDown,
  CircleHelp,
  Database,
  FileText,
  FlaskConical,
  Play,
  Plus,
  Settings2,
  SlidersHorizontal,
  Upload,
  X,
  TriangleAlert,
} from "lucide-react";
import LedgerHeader from "./components/LedgerHeader";
import Drawer from "./components/Drawer";
import ReconciliationGrid from "./components/ReconciliationGrid";
import MathProofInspector from "./components/MathProofInspector";
import LiveSimulatorDrawer from "./components/LiveSimulatorDrawer";
import RemittanceDropzone from "./components/RemittanceDropzone";
import LiveCaseComposer from "./components/LiveCaseComposer";
import WelcomeWorkspace from "./components/WelcomeWorkspace";
import {
  api,
  download,
  money,
  number,
  readJson,
  centsToDollars,
  dollarsToCents,
} from "./utils";

const initialConfig = {
  allow_wire_fees: true,
  wire_fee_options_cents: [0, 1000, 1500, 2000, 2500, 3000],
  allow_discounts: true,
  max_subset_size: 6,
  max_nodes: 2000000,
  entity_match_threshold: 0.65,
};
const emptyData = { invoices: [], deposits: [], remittances: [] };

export default function App() {
  const [data, setData] = useState(emptyData);
  const [result, setResult] = useState(null);
  const [config, setConfig] = useState(initialConfig);
  const [selectedId, setSelectedId] = useState(null);
  const [filter, setFilter] = useState("all");
  const [view, setView] = useState("workbench");
  const [drawer, setDrawer] = useState(null);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dirty, setDirty] = useState(false);
  const [workspaceMode, setWorkspaceMode] = useState("blank");
  const [workspaceRevision, setWorkspaceRevision] = useState(0);
  const custom = workspaceMode !== "sample";
  const isEmpty =
    !result &&
    !data.invoices.length &&
    !data.deposits.length &&
    !data.remittances.length;
  const showWelcome = isEmpty && view === "workbench";
  const [runAt, setRunAt] = useState(null);
  const [exportOpen, setExportOpen] = useState(false);

  const closeDrawer = useCallback(() => setDrawer(null), []);
  const solve = useCallback(async (nextData, nextConfig) => {
    setBusy(true);
    setError("");
    try {
      const response = await api("/api/reconcile", {
        ...nextData,
        config: nextConfig,
      });
      const next = await readJson(response);
      setData(nextData);
      setConfig(nextConfig);
      setResult(next);
      setDirty(false);
      setRunAt(new Date());
      setSelectedId((id) =>
        next.matches.some((m) => m.deposit_id === id)
          ? id
          : (
              next.matches.find((m) =>
                m.invoices.some((i) => i.state === "UNEARNED_DISCOUNT"),
              ) || next.matches[0]
            )?.deposit_id,
      );
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setBusy(false);
    }
  }, []);
  const loadSample = useCallback(async () => {
    setBusy(true);
    setError("");
    setNotice("");
    setSelectedId(null);
    try {
      const sample = await readJson(await api("/api/sample-data"));
      const next = {
        invoices: sample.invoices,
        deposits: sample.deposits,
        remittances: sample.remittances,
      };
      if (await solve(next, initialConfig)) {
        setWorkspaceMode("sample");
        setWorkspaceRevision((n) => n + 1);
        setFilter("all");
        setView("workbench");
      }
    } catch (e) {
      setError(`${e.message} Start the Python API and retry.`);
      setBusy(false);
    }
  }, [solve]);
  function clearLedger() {
    setData(emptyData);
    setResult(null);
    setConfig(initialConfig);
    setSelectedId(null);
    setFilter("all");
    setView("workbench");
    setDrawer(null);
    setError("");
    setNotice("");
    setDirty(false);
    setRunAt(null);
    setExportOpen(false);
    setWorkspaceMode("blank");
    setWorkspaceRevision((n) => n + 1);
  }
  async function applySources(next) {
    // A source-only workspace is staged until both sides are available.
    // The reconciliation API retains its nonempty-input validation contract.
    if (!next.invoices.length || !next.deposits.length) {
      setData(next);
      setResult(null);
      setSelectedId(null);
      setRunAt(null);
      setDirty(false);
      setError("");
      return true;
    }
    return solve(next, config);
  }
  const selected = result?.matches.find((x) => x.deposit_id === selectedId);
  async function exportFile(type, depositId) {
    setExportOpen(false);
    setExporting(true);
    setError("");
    try {
      const endpoint =
        type === "chargebacks"
          ? `/api/export-chargebacks-csv${depositId ? `?deposit_id=${encodeURIComponent(depositId)}` : ""}`
          : type === "audit"
            ? "/api/export-audit-json"
            : `/api/export-journal-csv?vendor=${type}`;
      await download(
        endpoint,
        { ...data, config },
        `settlesum-${type}${depositId ? `-${depositId}` : ""}.${type === "audit" ? "json" : "csv"}`,
      );
      setNotice(
        type === "audit"
          ? "Fresh reconciliation audit downloaded with source inputs, accounting proof, source hash, and measured telemetry."
          : `${type === "chargebacks" ? "Draft debit memo summary" : "Balanced journal"} downloaded. ${type === "chargebacks" ? "Review before posting." : "Map account names to your accounting system before importing."}`,
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setExporting(false);
    }
  }
  const updateInvoice = (id, key, value) => {
    setData((d) => ({
      ...d,
      invoices: d.invoices.map((i) =>
        i.invoice_id === id ? { ...i, [key]: value } : i,
      ),
    }));
    setDirty(data.deposits.length > 0);
  };
  const navigate = (next) => {
    setView(next);
    setDrawer(null);
  };
  return (
    <div className="terminal-shell">
      <aside className="nav-rail" aria-label="Main navigation">
        <a
          className="brand-mark"
          href="#"
          aria-label="SettleSum home"
          onClick={(e) => {
            e.preventDefault();
            navigate("workbench");
          }}
        >
          <span className="brand-symbol">
            <i />
            <i />
            <i />
          </span>
          <span className="brand-name">
            SettleSum<span>.</span>
          </span>
        </a>
        <div className="rail-items">
          {[
            [
              "workbench",
              ArrowLeftRight,
              "Reconciliation workbench",
              "Payments",
            ],
            ["invoices", Database, "Open invoice ledger", "Invoices"],
            ["remittances", FileText, "Remittance documents", "Remittances"],
            ["journal", BookOpen, "General ledger journal", "Journal"],
          ].map(([name, Icon, label, text]) => (
            <button
              key={name}
              title={label}
              aria-label={label}
              className={view === name ? "active" : ""}
              onClick={() => navigate(name)}
            >
              <Icon size={19} />
              <span>{text}</span>
            </button>
          ))}
        </div>
        <div className="rail-bottom">
          <button
            title="Solver settings"
            aria-label="Solver settings"
            onClick={() => setDrawer("simulator")}
            disabled={!data.deposits.length || !data.invoices.length}
          >
            <Settings2 size={19} />
            <span>Payment rules</span>
          </button>
          <button
            title="About the solver"
            aria-label="About the solver"
            onClick={() => setDrawer("help")}
          >
            <CircleHelp size={19} />
            <span>How it works</span>
          </button>
          <div className="session-note">
            Session workspace<span>Your changes stay until reload.</span>
          </div>
        </div>
      </aside>
      <div className="app-content">
        <header className="app-header">
          <div className="wordmark">
            Cash application
            <span className="workspace-name">Payments, explained.</span>
          </div>
          <div className="header-right">
            <span className="engine-state">
              <span className={`status-dot ${busy ? "working" : ""}`} />
              {busy
                ? "Reconciling…"
                : result
                  ? "Ledger calculated"
                  : "Ready for your data"}
            </span>
            <span className="header-divider" />
            <span className="workspace-id">USD</span>
          </div>
        </header>
        <main className={showWelcome ? "welcome-main" : "ledger-main"}>
          {!showWelcome && (
            <>
              <div className="workspace-bar" aria-label="Workspace actions">
                <div className="workspace-mode">
                  <span className="small-label">WORKSPACE</span>
                  <b>
                    {workspaceMode === "blank"
                      ? "Blank ledger"
                      : workspaceMode === "sample"
                        ? "Sample ledger"
                        : workspaceMode === "live"
                          ? "Live case"
                          : "Imported ledger"}
                  </b>
                </div>
                <div className="workspace-actions">
                  <button onClick={clearLedger} disabled={busy || exporting}>
                    New blank ledger
                  </button>
                  <button
                    onClick={() => {
                      setError("");
                      setDrawer("composer");
                    }}
                    disabled={busy || exporting}
                  >
                    <Plus size={14} />
                    Build a live case
                  </button>
                  <button onClick={loadSample} disabled={busy || exporting}>
                    <Database size={14} />
                    Load sample ledger
                  </button>
                </div>
              </div>
              <div className="page-heading">
                <div className="heading-copy">
                  <h1>
                    {view === "workbench"
                      ? "Payment reconciliation"
                      : view === "invoices"
                        ? "Open invoice ledger"
                        : view === "remittances"
                          ? "Remittance documents"
                          : "General ledger journal"}
                  </h1>
                  <p>
                    {view === "workbench"
                      ? "Choose a payment to see its invoices, deductions, and accounting proof."
                      : view === "invoices"
                        ? "Edit source values and dates, then re-solve the complete bank ledger."
                        : view === "remittances"
                          ? "Documented invoice references and claims, linked to source evidence."
                          : "Balanced journal entries generated from computed invoice-state matches."}
                  </p>
                </div>
                <div className="heading-actions">
                  <button onClick={() => setDrawer("upload")} disabled={busy}>
                    <Upload size={14} /> Import data
                  </button>
                  <div className="export-control">
                    <button
                      disabled={!result || busy || exporting || dirty}
                      className="primary-button"
                      onClick={() => setExportOpen(!exportOpen)}
                      aria-expanded={exportOpen}
                    >
                      <ArrowDownToLine size={14} />
                      {exporting ? "Exporting…" : "Export journal"}
                      <ChevronDown size={12} />
                    </button>
                    {exportOpen && (
                      <>
                        <div
                          className="menu-dismiss"
                          onClick={() => setExportOpen(false)}
                        />
                        <div className="export-menu">
                          <button onClick={() => exportFile("quickbooks")}>
                            QuickBooks journal CSV
                          </button>
                          <button onClick={() => exportFile("xero")}>
                            Xero journal CSV
                          </button>
                          <button onClick={() => exportFile("audit")}>
                            Reconciliation audit JSON
                          </button>
                          <button onClick={() => exportFile("chargebacks")}>
                            Chargeback debit memos
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
          {error && (
            <div className="error-banner" role="alert">
              <TriangleAlert size={16} />
              <span>{error}</span>
              <button onClick={() => setError("")} aria-label="Dismiss error">
                <X size={15} />
              </button>
            </div>
          )}
          {notice && (
            <div className="notice-banner" role="status">
              <Check size={14} />
              <span>{notice}</span>
              <button
                onClick={() => setNotice("")}
                aria-label="Dismiss notification"
              >
                <X size={14} />
              </button>
            </div>
          )}
          {showWelcome ? (
            <WelcomeWorkspace
              onBuild={() => {
                setError("");
                setDrawer("composer");
              }}
              onImport={() => setDrawer("upload")}
              onSample={loadSample}
              busy={busy}
            />
          ) : (
            <>
              <LedgerHeader result={result} busy={busy} dirty={dirty} />
              <div
                className={`dataset-banner ${custom ? "custom-dataset" : ""}`}
              >
                <span>
                  {workspaceMode === "sample" ? (
                    <FlaskConical size={16} />
                  ) : (
                    <Check size={16} />
                  )}
                  {workspaceMode === "sample"
                    ? "SYNTHETIC BENCHMARK DATASET — MODELED ON B2B WHOLESALE AR LEDGERS. UPLOAD ANY CUSTOM CSV TO RUN LIVE."
                    : workspaceMode === "blank"
                      ? "Add invoices and payments to get started."
                      : "Live ledger. Every result is calculated from your current inputs."}
                </span>
              </div>
              <div className="workbench-toolbar">
                <div>
                  <span className="status-dot" />
                  <b>
                    {busy
                      ? "Reconciliation running"
                      : dirty
                        ? "Input changes pending"
                        : "Current ledger"}
                  </b>
                  <span className="mono muted">
                    {`${number(data.invoices.length)} INVOICES / ${number(data.deposits.length)} DEPOSITS / ${new Set(data.invoices.map((x) => x.customer_id)).size} COUNTERPARTIES`}
                  </span>
                </div>
                <button
                  className="simulator-button"
                  onClick={() => setDrawer("simulator")}
                  disabled={
                    !data.deposits.length || !data.invoices.length || busy
                  }
                >
                  <SlidersHorizontal size={16} /> Try a change
                </button>
              </div>
              {dirty && (
                <div className="pending-banner">
                  <span>
                    Source inputs have changed. Displayed proofs and metrics
                    belong to the previous run.
                  </span>
                  <button
                    className="primary-button"
                    disabled={busy}
                    onClick={() => solve(data, config)}
                  >
                    <Play size={13} />
                    {busy ? "SOLVING…" : "RE-SOLVE LEDGER"}
                  </button>
                </div>
              )}
              {view === "workbench" ? (
                <div
                  className={`workbench ${busy ? "is-solving" : ""}`}
                  aria-busy={busy}
                >
                  <ReconciliationGrid
                    key={workspaceRevision}
                    sourceDeposits={data.deposits}
                    onBuild={() => setDrawer("composer")}
                    onImport={() => setDrawer("upload")}
                    result={result}
                    selectedId={selectedId}
                    onSelect={setSelectedId}
                    filter={filter}
                    setFilter={setFilter}
                  />
                  <MathProofInspector
                    match={selected}
                    onSimulate={() => setDrawer("simulator")}
                    onMemo={() =>
                      exportFile("chargebacks", selected?.deposit_id)
                    }
                    busy={exporting || busy || dirty}
                    remittances={data.remittances}
                  />
                </div>
              ) : view === "invoices" ? (
                <section className="data-panel">
                  <div className="panel-heading">
                    <h2>
                      Open invoices{" "}
                      <span className="count">{data.invoices.length}</span>
                    </h2>
                    <button
                      disabled={!dirty || busy || !data.deposits.length}
                      className="primary-button"
                      onClick={() => solve(data, config)}
                    >
                      <Play size={13} /> RE-SOLVE LEDGER
                    </button>
                  </div>
                  <div className="table-scroll">
                    <table className="source-table">
                      <thead>
                        <tr>
                          <th>INVOICE ID</th>
                          <th>CUSTOMER</th>
                          <th>ISSUED</th>
                          <th>DUE DATE</th>
                          <th>AMOUNT · USD</th>
                          <th>DISCOUNT RATE</th>
                          <th>WINDOW · DAYS</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.invoices.map((i) => (
                          <tr key={i.invoice_id}>
                            <td className="mono">{i.invoice_id}</td>
                            <td>{i.customer_name}</td>
                            <td>
                              <input
                                aria-label={`${i.invoice_id} invoice date`}
                                type="date"
                                value={i.invoice_date}
                                onChange={(e) =>
                                  updateInvoice(
                                    i.invoice_id,
                                    "invoice_date",
                                    e.target.value,
                                  )
                                }
                              />
                            </td>
                            <td>
                              <input
                                aria-label={`${i.invoice_id} due date`}
                                type="date"
                                value={i.due_date}
                                onChange={(e) =>
                                  updateInvoice(
                                    i.invoice_id,
                                    "due_date",
                                    e.target.value,
                                  )
                                }
                              />
                            </td>
                            <td>
                              <input
                                aria-label={`${i.invoice_id} amount`}
                                type="number"
                                step=".01"
                                min=".01"
                                value={
                                  Number.isFinite(i.amount_cents)
                                    ? centsToDollars(i.amount_cents)
                                    : ""
                                }
                                onChange={(e) =>
                                  updateInvoice(
                                    i.invoice_id,
                                    "amount_cents",
                                    dollarsToCents(e.target.value),
                                  )
                                }
                              />
                            </td>
                            <td>
                              <input
                                aria-label={`${i.invoice_id} discount rate`}
                                type="number"
                                step=".001"
                                min="0"
                                max=".99"
                                value={i.discount_pct}
                                onChange={(e) =>
                                  updateInvoice(
                                    i.invoice_id,
                                    "discount_pct",
                                    e.target.value,
                                  )
                                }
                              />
                            </td>
                            <td>
                              <input
                                aria-label={`${i.invoice_id} discount days`}
                                type="number"
                                min="0"
                                max="365"
                                value={i.discount_days}
                                onChange={(e) =>
                                  updateInvoice(
                                    i.invoice_id,
                                    "discount_days",
                                    Number(e.target.value),
                                  )
                                }
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ) : view === "remittances" ? (
                <section className="data-panel">
                  <div className="panel-heading">
                    <h2>
                      Source documents{" "}
                      <span className="count">{data.remittances.length}</span>
                    </h2>
                    <button onClick={() => setDrawer("upload")}>
                      <Upload size={13} /> Add remittance
                    </button>
                  </div>
                  {data.remittances.map((r, i) => (
                    <article
                      className="document-record"
                      key={`${r.document_id}-${i}`}
                    >
                      <h3>
                        <FileText size={16} />
                        <span className="mono">{r.document_id}</span>
                        <span className="badge blue">
                          {r.deposit_id || "INVOICE-LINKED"}
                        </span>
                      </h3>
                      <p>{r.customer_name}</p>
                      <pre>{r.raw_text}</pre>
                      <table>
                        <thead>
                          <tr>
                            <th>EXPLICIT INVOICE REFERENCE</th>
                            <th className="numeric">CLAIM</th>
                            <th>REASON</th>
                          </tr>
                        </thead>
                        <tbody>
                          {r.referenced_invoices.map((ref, j) => (
                            <tr key={j}>
                              <td className="mono">{ref.invoice_id}</td>
                              <td className="numeric mono amber">
                                {money(ref.deduction_cents)}
                              </td>
                              <td>{ref.reason_code}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </article>
                  ))}
                  {!data.remittances.length && (
                    <div className="empty-state">
                      <FileText size={26} />
                      <h3>No remittance documents</h3>
                      <p>
                        Import a text-based PDF or paste an advice note to add
                        documented claim states.
                      </p>
                      <button onClick={() => setDrawer("upload")}>
                        Import remittance
                      </button>
                    </div>
                  )}
                </section>
              ) : (
                <section className="data-panel">
                  <div className="panel-heading">
                    <h2>
                      Computed journal{" "}
                      <span className={`badge ${result ? "green" : "muted"}`}>
                        {result ? "BALANCED" : "AWAITING LEDGER"}
                      </span>
                    </h2>
                    <span className="small-label">DRAFT · NOT POSTED</span>
                  </div>
                  <div className="table-scroll">
                    <table className="source-table">
                      <thead>
                        <tr>
                          <th>DEPOSIT</th>
                          <th>DATE</th>
                          <th>GL</th>
                          <th>ACCOUNT</th>
                          <th>INVOICE REFERENCE</th>
                          <th className="numeric">DEBIT</th>
                          <th className="numeric">CREDIT</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result?.matches.flatMap((m) =>
                          m.journal_lines.map((line, i) => (
                            <tr key={`${m.deposit_id}-${i}`}>
                              <td>
                                <button
                                  className="text-button mono"
                                  onClick={() => {
                                    setSelectedId(m.deposit_id);
                                    setView("workbench");
                                  }}
                                >
                                  {m.deposit_id}
                                </button>
                              </td>
                              <td className="mono">{m.deposit_date}</td>
                              <td
                                className={`mono ${line.gl_account === "1215" ? "amber" : ""}`}
                              >
                                {line.gl_account}
                              </td>
                              <td>{line.account_name}</td>
                              <td className="mono muted">
                                {line.invoice_id || "—"}
                              </td>
                              <td className="numeric mono">
                                {line.debit_cents
                                  ? money(line.debit_cents)
                                  : "—"}
                              </td>
                              <td className="numeric mono">
                                {line.credit_cents
                                  ? money(line.credit_cents)
                                  : "—"}
                              </td>
                            </tr>
                          )),
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}
            </>
          )}
        </main>
        <footer className="app-footer">
          <span>
            Draft journals only. Nothing is posted to your accounting system.
          </span>
          <span>
            {runAt
              ? `Last calculated ${runAt.toLocaleTimeString("en-GB", { timeZone: "UTC" })} UTC`
              : "Your ledger starts empty."}
          </span>
        </footer>
      </div>
      {drawer === "simulator" && data.deposits.length > 0 && (
        <LiveSimulatorDrawer
          data={data}
          selectedId={selectedId}
          config={config}
          onClose={closeDrawer}
          onSolve={solve}
          busy={busy}
          backendError={error}
        />
      )}
      {drawer === "upload" && (
        <RemittanceDropzone
          backendError={error}
          data={data}
          onClose={closeDrawer}
          busy={busy}
          onApply={async (next) => {
            const ok = await applySources(next);
            if (ok) {
              setWorkspaceMode("custom");
              setWorkspaceRevision((n) => n + 1);
              setView(
                next.invoices.length && !next.deposits.length
                  ? "invoices"
                  : "workbench",
              );
              setFilter("all");
              setNotice(
                next.invoices.length && next.deposits.length
                  ? "Validated source data applied. Every bank deposit was reconciled again."
                  : "Source data staged. Import the other CSV to run reconciliation.",
              );
            }
            return ok;
          }}
        />
      )}
      {drawer === "composer" && (
        <LiveCaseComposer
          data={data}
          onClose={closeDrawer}
          busy={busy}
          backendError={error}
          onRun={async (next) => {
            const ok = await solve(next, config);
            if (ok) {
              setWorkspaceMode("live");
              setWorkspaceRevision((n) => n + 1);
              setView("workbench");
              setFilter("all");
              setNotice(
                "Your ledger is ready. Select a payment to review the calculation.",
              );
            }
            return ok;
          }}
        />
      )}
      {drawer === "help" && (
        <Drawer
          title="About SettleSum"
          subtitle="Inspectable accounting. Exact results."
          onClose={closeDrawer}
        >
          <div className="drawer-body about-content">
            <p>
              SettleSum searches invoice subsets and their conditional valuation
              states using a Python multi-state choice branch-and-bound solver.
              Every run uses integer cents and returns measured wall-clock time
              and visited-node counts.
            </p>
            <p>
              Matches prioritize explicit invoice references, simpler states,
              zero fees, and older due dates. Deposits apply chronologically.
              Each invoice can be used once per run.
            </p>
            <p>
              Margin recovery means identified unearned discounts and drafted
              chargeback AR. No journal or debit memo is posted externally.
            </p>
            <button
              onClick={() => setDrawer("simulator")}
              disabled={!data.deposits.length || !data.invoices.length}
            >
              <SlidersHorizontal size={14} /> Open live simulator
            </button>
          </div>
        </Drawer>
      )}
    </div>
  );
}
