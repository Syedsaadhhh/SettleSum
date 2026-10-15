import { useState } from "react";
import { Play, RotateCcw, SlidersHorizontal } from "lucide-react";
import Drawer from "./Drawer";
import { money } from "../utils";
export default function LiveSimulatorDrawer({
  data,
  selectedId,
  config,
  onClose,
  onSolve,
  busy,
  backendError,
}) {
  const [id, setId] = useState(selectedId || data.deposits[0]?.deposit_id);
  const original = data.deposits.find((d) => d.deposit_id === id);
  const [amount, setAmount] = useState(
    (original.amount_cents / 100).toFixed(2),
  );
  const [date, setDate] = useState(original.deposit_date);
  const [rules, setRules] = useState({ ...config });
  const [band, setBand] = useState(
    config.wire_fee_band_min_cents !== null &&
      config.wire_fee_band_min_cents !== undefined,
  );
  const [minimum, setMinimum] = useState(
    (config.wire_fee_band_min_cents || 0) / 100,
  );
  const [maximum, setMaximum] = useState(
    (config.wire_fee_band_max_cents || 3000) / 100,
  );
  const [error, setError] = useState("");
  const select = (id) => {
    const row = data.deposits.find((d) => d.deposit_id === id);
    setId(id);
    setAmount((row.amount_cents / 100).toFixed(2));
    setDate(row.deposit_date);
  };
  const submit = async (e) => {
    e.preventDefault();
    setError("");
    const cents = Math.round(Number(amount) * 100);
    if (!Number.isSafeInteger(cents) || cents <= 0) {
      setError("Enter a positive dollar amount.");
      return;
    }
    const nextConfig = {
      ...rules,
      wire_fee_band_min_cents: band ? Math.round(Number(minimum) * 100) : null,
      wire_fee_band_max_cents: band ? Math.round(Number(maximum) * 100) : null,
    };
    const ok = await onSolve(
      {
        ...data,
        deposits: data.deposits.map((d) =>
          d.deposit_id === id
            ? { ...d, amount_cents: cents, deposit_date: date }
            : d,
        ),
      },
      nextConfig,
    );
    if (ok) onClose();
  };
  return (
    <Drawer
      title="Live input simulator"
      subtitle="Change the inputs. Recompute every match."
      onClose={onClose}
    >
      <form onSubmit={submit} className="drawer-form">
        <div className="form-section">
          <h3>
            <SlidersHorizontal size={15} /> Deposit inputs
          </h3>
          <label>
            Bank deposit
            <select value={id} onChange={(e) => select(e.target.value)}>
              {data.deposits.map((d) => (
                <option key={d.deposit_id} value={d.deposit_id}>
                  {d.deposit_id} · {money(d.amount_cents)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Deposit amount · USD
            <input
              className="mono"
              type="number"
              step="0.01"
              min="0.01"
              max="90071992547409"
              required
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </label>
          <label>
            Clearing date
            <input
              className="mono"
              type="date"
              required
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
            <small>
              Discount eligibility is recalculated against each invoice date.
            </small>
          </label>
        </div>
        <div className="form-section">
          <h3>Valuation & fee rules</h3>
          <label className="check-label">
            <span>
              <b>Apply payment-term states</b>
              <small>Evaluate both valid and expired discounts</small>
            </span>
            <input
              type="checkbox"
              checked={rules.allow_discounts}
              onChange={(e) =>
                setRules({ ...rules, allow_discounts: e.target.checked })
              }
            />
          </label>
          <label className="check-label">
            <span>
              <b>Allow bank wire fees</b>
              <small>Infer a fee only when the equation is exact</small>
            </span>
            <input
              type="checkbox"
              checked={rules.allow_wire_fees}
              onChange={(e) =>
                setRules({ ...rules, allow_wire_fees: e.target.checked })
              }
            />
          </label>
          <fieldset disabled={!rules.allow_wire_fees}>
            <legend>Permitted fees · USD</legend>
            <div className="fee-options">
              {[0, 1000, 1500, 2000, 2500, 3000].map((fee) => (
                <label key={fee}>
                  <input
                    type="checkbox"
                    checked={
                      fee === 0 || rules.wire_fee_options_cents.includes(fee)
                    }
                    disabled={fee === 0}
                    onChange={(e) =>
                      setRules({
                        ...rules,
                        wire_fee_options_cents: e.target.checked
                          ? [...rules.wire_fee_options_cents, fee]
                          : rules.wire_fee_options_cents.filter(
                              (x) => x !== fee,
                            ),
                      })
                    }
                  />
                  {money(fee)}
                </label>
              ))}
            </div>
            <label className="check-label">
              <span>
                Custom fee band{" "}
                <small>Every integer cent in this range is allowed</small>
              </span>
              <input
                type="checkbox"
                checked={band}
                onChange={(e) => setBand(e.target.checked)}
              />
            </label>
            {band && (
              <div className="form-columns">
                <label>
                  Minimum · USD
                  <input
                    type="number"
                    min="0"
                    step=".01"
                    max="100000"
                    value={minimum}
                    onChange={(e) => setMinimum(e.target.value)}
                    required
                  />
                </label>
                <label>
                  Maximum · USD
                  <input
                    type="number"
                    min={minimum}
                    step=".01"
                    max="100000"
                    value={maximum}
                    onChange={(e) => setMaximum(e.target.value)}
                    required
                  />
                </label>
              </div>
            )}
          </fieldset>
          <label>
            Maximum invoices per deposit
            <input
              type="number"
              min="1"
              max="20"
              value={rules.max_subset_size}
              onChange={(e) =>
                setRules({ ...rules, max_subset_size: Number(e.target.value) })
              }
              required
            />
          </label>
          <label>
            Search node budget per deposit
            <input
              type="number"
              min="1"
              max="10000000"
              value={rules.max_nodes}
              onChange={(e) =>
                setRules({ ...rules, max_nodes: Number(e.target.value) })
              }
              required
            />
          </label>
        </div>
        <div className="simulator-tip">
          <b>Try the discount window test</b>
          <p>
            Select Vanguard’s deposit and move its clearing date to 19 Oct 2026.
            The same cash amount should shift from valid discount to chargeback
            AR.
          </p>
          <button
            type="button"
            className="text-button"
            onClick={() => {
              const target = data.deposits.find((d) =>
                /vanguard/i.test(d.raw_payer_memo),
              );
              if (target) {
                select(target.deposit_id);
                setDate("2026-10-19");
              }
            }}
          >
            Load benchmark scenario <RotateCcw size={12} />
          </button>
        </div>
        {(error || backendError) && (
          <p role="alert" className="inline-error">
            {error || backendError}
          </p>
        )}
        <div className="drawer-actions">
          <span>Fresh branch-and-bound search. No cached matches.</span>
          <button className="primary-button" type="submit" disabled={busy}>
            <Play size={14} />
            {busy ? "SOLVING LEDGER…" : "RE-SOLVE LEDGER"}
          </button>
        </div>
      </form>
    </Drawer>
  );
}
