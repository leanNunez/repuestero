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

/** Fecha ISO del backend (`YYYY-MM-DD`) a `dd/mm/aaaa`.
 *
 * Parte el string a mano y NO usa `new Date`: `new Date("2026-07-24")` se interpreta como
 * medianoche UTC, y en Argentina (UTC-3) eso se renderiza como 23/07. Un movimiento de cuenta
 * corriente fechado un día antes es un problema de verdad, no un detalle cosmético. */
export function fechaCorta(v: string | null | undefined): string {
  if (!v) return "—";

  const [a, m, d] = v.slice(0, 10).split("-");
  return a && m && d ? `${d}/${m}/${a}` : v;
}

/** Hoy como `YYYY-MM-DD` LOCAL, para precargar y topear un `<input type="date">`.
 *
 * `new Date().toISOString().slice(0, 10)` sería el bug del docstring de arriba al revés: da la
 * fecha UTC, así que a las 21:00 en Argentina devuelve MAÑANA. Con eso el input se precargaría en
 * el futuro y el backend rechazaría la cobranza con un 422 incomprensible.
 *
 * `getFullYear`/`getMonth`/`getDate` son locales, que es justo lo que se necesita. */
export function hoyISO(): string {
  const d = new Date();
  const dosDigitos = (n: number) => String(n).padStart(2, "0");

  return `${d.getFullYear()}-${dosDigitos(d.getMonth() + 1)}-${dosDigitos(d.getDate())}`;
}
