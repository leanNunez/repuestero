/** Formatea plata SOLO para mostrar.
 *
 * El valor que se GUARDA nunca pasa por acá: los importes viajan como string de punta a
 * punta (ver la nota en `schema.ts`). Esto es la capa de presentación y nada más.
 */
export function pesos(v: string | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("es-AR", {
        style: "currency",
        currency: "ARS",
        maximumFractionDigits: 2,
      })
    : v;
}
