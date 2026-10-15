export const money = (cents = 0) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    cents / 100,
  );
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
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
export const stateLabels = {
  FULL: "FULL VALUE",
  EARNED_DISCOUNT: "VALID DISCOUNT",
  UNEARNED_DISCOUNT: "UNEARNED DISCOUNT",
  REMITTANCE_SHORTPAY: "SHORT-PAY CLAIM",
};
