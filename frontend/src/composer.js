import { dollarsToCents } from "./utils.js";

export const makeRecordId = (prefix) =>
  `${prefix}-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;
export const todayISO = () => new Date().toISOString().slice(0, 10);
export function addDays(date, days) {
  const value = new Date(`${date}T00:00:00Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return Number.isNaN(value.getTime()) ? "" : value.toISOString().slice(0, 10);
}
export function previewSum(rows, discountPercent = 0) {
  let total = 0n;
  for (const row of rows.filter((r) => r.selected)) {
    const cents = dollarsToCents(row.amount);
    if (!Number.isSafeInteger(cents) || cents <= 0)
      throw new Error(
        "Enter positive amounts with at most two decimal places.",
      );
    const numerator = BigInt(cents) * BigInt(100 - discountPercent);
    let net = numerator / 100n;
    const remainder = numerator % 100n;
    // Round each invoice's net amount half-to-even, matching the Python convention.
    if (remainder > 50n || (remainder === 50n && net % 2n)) net += 1n;
    total += net;
  }
  if (total > BigInt(Number.MAX_SAFE_INTEGER))
    throw new Error("Selected total exceeds safe browser integer cents.");
  return Number(total);
}
export function buildRecords({ customerName, customerId, invoices, deposits }) {
  if (!customerName.trim() || !customerId.trim())
    throw new Error("Enter a customer name and ID.");
  const amountOf = (row) => {
    const cents = dollarsToCents(row.amount);
    if (!Number.isSafeInteger(cents) || cents <= 0)
      throw new Error(
        "Every record needs a positive amount with at most two decimal places.",
      );
    return cents;
  };
  const uniqueIds = (rows, key) => {
    const ids = rows.map((r) => r[key].trim());
    if (ids.some((id) => !id) || new Set(ids).size !== ids.length)
      throw new Error(
        "Invoice and deposit IDs must be nonempty and unique within each dataset.",
      );
  };
  uniqueIds(invoices, "invoice_id");
  uniqueIds(deposits, "deposit_id");
  return {
    invoices: invoices.map((r) => {
      if (!r.invoice_date || !r.due_date || r.due_date < r.invoice_date)
        throw new Error(
          "Each invoice needs valid issue and due dates, in order.",
        );
      return {
        invoice_id: r.invoice_id.trim(),
        customer_id: customerId.trim(),
        customer_name: customerName.trim(),
        invoice_date: r.invoice_date,
        due_date: r.due_date,
        amount_cents: amountOf(r),
        discount_terms: r.discount_terms,
      };
    }),
    deposits: deposits.map((r) => {
      if (!r.deposit_date || !r.raw_payer_memo.trim())
        throw new Error("Each deposit needs a clearing date and bank memo.");
      return {
        deposit_id: r.deposit_id.trim(),
        deposit_date: r.deposit_date,
        raw_payer_memo: r.raw_payer_memo.trim(),
        amount_cents: amountOf(r),
        bank_reference: "",
      };
    }),
    remittances: [],
  };
}
