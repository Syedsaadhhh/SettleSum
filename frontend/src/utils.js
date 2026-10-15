// The browser rejects unsafe JSON cents instead of silently rounding them.
// The Python API supports the full signed 64-bit cents domain.
export function assertSafeMoney(value, key = "") {
  if (Array.isArray(value)) {
    value.forEach((item) => assertSafeMoney(item, key));
  } else if (value && typeof value === "object") {
    Object.entries(value).forEach(([field, item]) =>
      assertSafeMoney(item, field),
    );
  } else if (
    key.endsWith("_cents") &&
    typeof value === "number" &&
    !Number.isSafeInteger(value)
  ) {
    throw new Error(
      "Currency exceeds safe browser integer cents or is invalid. Use exact integer cents through the Python API for larger values.",
    );
  }
}
export async function readJson(response) {
  const data = await response.json();
  assertSafeMoney(data);
  return data;
}
export function centsToDollars(cents) {
  if (!Number.isSafeInteger(cents))
    throw new Error("Invalid browser integer cents");
  const amount = BigInt(cents);
  const absolute = amount < 0n ? -amount : amount;
  return `${amount < 0n ? "-" : ""}${absolute / 100n}.${String(absolute % 100n).padStart(2, "0")}`;
}
export function dollarsToCents(input) {
  const parsed = /^(-?)(\d+)(?:\.(\d{0,2}))?$/.exec(String(input));
  if (!parsed) return Number.NaN;
  let cents =
    BigInt(parsed[2]) * 100n + BigInt((parsed[3] || "").padEnd(2, "0"));
  if (parsed[1]) cents = -cents;
  return cents > BigInt(Number.MAX_SAFE_INTEGER) ||
    cents < -BigInt(Number.MAX_SAFE_INTEGER)
    ? Number.NaN
    : Number(cents);
}
export function money(cents = 0) {
  const decimal = centsToDollars(cents);
  const [whole, fraction] = decimal.replace("-", "").split(".");
  return `${cents < 0 ? "-" : ""}$${new Intl.NumberFormat("en-US").format(BigInt(whole))}.${fraction}`;
}
export const number = (n = 0) => new Intl.NumberFormat("en-US").format(n);
export const dateLabel = (date) =>
  new Date(`${date}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
  });
export async function api(
  path,
  body,
  headers = { "Content-Type": "application/json" },
) {
  if (body && typeof body === "object" && !(body instanceof FormData))
    assertSafeMoney(body);
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers,
    body:
      body === undefined
        ? undefined
        : typeof body === "string" || body instanceof FormData
          ? body
          : JSON.stringify(body),
  });
  if (!response.ok) {
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(
        `Request failed (${response.status}). Check the API connection.`,
      );
    }
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : (data.detail || [])
            .map((x) => `${x.loc?.join(" → ") || "Input"}: ${x.msg}`)
            .join("; ");
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return response;
}
export async function download(path, body, filename) {
  const response = await api(path, body);
  saveBlob(await response.blob(), filename);
}
export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
export const stateLabels = {
  FULL: "Full value",
  EARNED_DISCOUNT: "Valid discount",
  UNEARNED_DISCOUNT: "Expired discount",
  REMITTANCE_SHORTPAY: "Short-pay claim",
};
