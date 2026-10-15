import test from "node:test";
import assert from "node:assert/strict";
import { buildRecords, previewSum } from "../src/composer.js";
const invoice = (amount, selected = true) => ({ amount, selected });

test("composer helpers sum selected invoices in exact cents and round each discount half-even", () => {
  assert.equal(previewSum([invoice("4200"), invoice("3800")]), 800000);
  assert.equal(previewSum([invoice("4200"), invoice("3800")], 2), 784000);
  assert.equal(previewSum([invoice("1.25"), invoice("3.75")], 2), 490);
  assert.equal(previewSum([invoice("1.00"), invoice("999.99", false)]), 100);
  assert.equal(previewSum([]), 0);
});
test("composer rejects subcent, negative, invalid, and overflowing totals", () => {
  for (const amount of ["", "0", "-1", "100.001", "NaN"])
    assert.throws(() => previewSum([invoice(amount)]));
  assert.throws(() =>
    previewSum([invoice("90071992547409.91"), invoice("0.01")]),
  );
});
test("composer creates source records without inventing results or GL assignments", () => {
  const input = {
    customerName: "Horizon Hardware Co",
    customerId: "HORIZON",
    invoices: [
      {
        invoice_id: "bill-a",
        invoice_date: "2026-10-01",
        due_date: "2026-10-31",
        amount: "10000.00",
        discount_terms: "2/10 Net 30",
      },
    ],
    deposits: [
      {
        deposit_id: "payment-a",
        deposit_date: "2026-10-08",
        raw_payer_memo: "WIRE HORIZON HARDWARE CO",
        amount: "9800.00",
      },
    ],
  };
  const records = buildRecords(input);
  assert.equal(records.invoices[0].amount_cents, 1000000);
  assert.equal(records.deposits[0].amount_cents, 980000);
  assert.equal(records.invoices[0].discount_terms, "2/10 Net 30");
  assert.deepEqual(Object.keys(records).sort(), [
    "deposits",
    "invoices",
    "remittances",
  ]);
  assert(!("state" in records.invoices[0]));
  assert.throws(() => buildRecords({ ...input, customerName: "" }));
  assert.throws(() =>
    buildRecords({
      ...input,
      invoices: [input.invoices[0], input.invoices[0]],
    }),
  );
});
