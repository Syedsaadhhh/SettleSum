import test from "node:test";
import assert from "node:assert/strict";
import {
  assertSafeMoney,
  centsToDollars,
  dollarsToCents,
  money,
  readJson,
} from "../src/utils.js";

test("display preserves the last cent at JavaScript safe-integer boundary", () => {
  assert.equal(centsToDollars(Number.MAX_SAFE_INTEGER), "90071992547409.91");
  assert.equal(money(Number.MAX_SAFE_INTEGER), "$90,071,992,547,409.91");
  assert.equal(money(-101), "-$1.01");
  assert.equal(money(0), "$0.00");
});
test("dollar input uses exact decimal scaling and rejects unsafe or subcent input", () => {
  assert.equal(dollarsToCents("7985.01"), 798501);
  assert.equal(dollarsToCents("0.29"), 29);
  assert.equal(dollarsToCents("90071992547409.91"), Number.MAX_SAFE_INTEGER);
  for (const input of ["90071992547409.92", "1.001", "NaN", "Infinity", ""]) {
    assert(Number.isNaN(dollarsToCents(input)), input);
  }
});
test("nested monetary fields, arrays, fractional cents and unsafe integers are guarded", () => {
  assert.doesNotThrow(() =>
    assertSafeMoney({
      total_cents: 123,
      fees_cents: [0, 1500],
      paid_amount_cents: null,
    }),
  );
  for (const input of [
    { amount_cents: 9007199254740992 },
    { fees_cents: [1.5] },
    { matches: [{ credit_cents: Number.NaN }] },
  ]) {
    assert.throws(() => assertSafeMoney(input));
  }
});
test("JSON currency outside the browser exact domain is rejected, never silently applied", async () => {
  await assert.rejects(
    readJson(new Response('{"amount_cents":9223372036854775807}')),
    /safe browser integer cents/,
  );
  assert.deepEqual(await readJson(new Response('{"amount_cents":798501}')), {
    amount_cents: 798501,
  });
});
