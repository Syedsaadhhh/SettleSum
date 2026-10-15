import {
  ArrowRight,
  ArrowUpRight,
  FilePlus2,
  Upload,
  Landmark,
  ListChecks,
  CheckCheck,
} from "lucide-react";

export default function WelcomeWorkspace({
  onBuild,
  onImport,
  onSample,
  busy,
}) {
  return (
    <section
      className="welcome-workspace"
      aria-labelledby="welcome-title"
      aria-busy={busy}
    >
      <div className="welcome-copy">
        <h1 id="welcome-title">
          Match payments.
          <br />
          <span>Find missing margin.</span>
        </h1>
        <p>
          Add your invoices and a bank payment. SettleSum matches them, explains
          every deduction, and prepares a balanced accounting entry.
        </p>
        <div className="welcome-actions">
          <button className="primary-button" onClick={onBuild} disabled={busy}>
            <FilePlus2 size={18} />
            Build a live case
            <ArrowRight size={17} />
          </button>
          <button onClick={onImport} disabled={busy}>
            <Upload size={17} />
            Import CSV files
          </button>
        </div>
        <p className="welcome-reassurance">
          Start with your own numbers. No CSV formatting needed.
        </p>
        <div className="sample-entry">
          <div>
            <strong>Want to see it in action first?</strong>
            <span>36 synthetic invoices. 8 payments. Real reconciliation.</span>
          </div>
          <button className="text-button" onClick={onSample} disabled={busy}>
            {busy ? "Loading sample…" : "Load sample ledger"}
            <ArrowUpRight size={16} />
          </button>
        </div>
      </div>
      <aside className="welcome-guide" aria-label="How SettleSum works">
        <h2>From payment to proof.</h2>
        <p>A clear answer to “what did this payment cover?”</p>
        <ol>
          <li>
            <Landmark size={21} />
            <div>
              <h3>Add the payment</h3>
              <p>
                Enter a customer, their open invoices, and the amount received.
              </p>
            </div>
          </li>
          <li>
            <ListChecks size={21} />
            <div>
              <h3>See what matches</h3>
              <p>
                Find the invoice combination, including discounts, fees, and
                documented claims.
              </p>
            </div>
          </li>
          <li>
            <CheckCheck size={21} />
            <div>
              <h3>Review every cent</h3>
              <p>
                Inspect the calculation, flag lost margin, and export a balanced
                journal.
              </p>
            </div>
          </li>
        </ol>
        <div className="welcome-note">
          An empty ledger, ready for your data.
          <span>Nothing is posted to your accounting system.</span>
        </div>
      </aside>
    </section>
  );
}
