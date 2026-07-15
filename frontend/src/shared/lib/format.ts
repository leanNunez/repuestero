const money = new Intl.NumberFormat("es-AR", {
  style: "currency",
  currency: "ARS",
  maximumFractionDigits: 0,
});

const number = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 });

export function formatMoney(v: number | string): string {
  return money.format(typeof v === "string" ? Number(v) : v);
}

export function formatNumber(v: number | string): string {
  return number.format(typeof v === "string" ? Number(v) : v);
}
