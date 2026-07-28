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

/** Conectores que no aportan como inicial. Sin esto "Juntas y Retenes del Norte SRL" da "JY", que
 *  no identifica a nadie. En nombres de personas casi no aparecen; en razones sociales, todo el
 *  tiempo — y es justo la tabla de proveedores la que está llena de ellas. */
const CONECTORES = new Set(["y", "e", "de", "del", "la", "las", "los", "el"]);

/** Iniciales para el avatar de una fila: "Taller Mecánico El Rulo" → "TM",
 *  "Juntas y Retenes del Norte SRL" → "JR".
 *
 * Compartida por las tablas de clientes y proveedores. Un nombre sin palabras devuelve "?" en vez
 * de un avatar vacío, que se lee como un dato que se perdió. */
export function iniciales(nombre: string): string {
  const palabras = nombre.trim().split(/\s+/).filter(Boolean);
  // Si sacar los conectores no deja nada (un nombre que es solo "La"), se usan las palabras tal
  // cual: es preferible una inicial pobre a un "?" sobre un nombre que existe.
  const utiles = palabras.filter((p) => !CONECTORES.has(p.toLowerCase()));
  const fuente = utiles.length > 0 ? utiles : palabras;

  const ini = (fuente[0]?.[0] ?? "") + (fuente[1]?.[0] ?? "");
  return ini.toUpperCase() || "?";
}
