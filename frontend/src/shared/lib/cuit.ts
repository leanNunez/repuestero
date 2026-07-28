/** Validación de CUIT, compartida por clientes y proveedores.
 *
 * Vivía en `features/clientes/model/estado.ts`. Se mudó acá cuando proveedores necesitó lo mismo:
 * que una feature importe de otra las ata por algo que no es de ninguna de las dos. Espeja la
 * misma mudanza del backend (`app/core/cuit.py`).
 *
 * Port exacto de `app.core.cuit.cuit_valido`. Si algún día cambia el algoritmo, cambia en los dos
 * lados o el front empieza a bloquear CUITs que el backend acepta — que es peor que no validar:
 * el dato válido no entra y nadie sabe por qué.
 */

const CUIT_RE = /^\d{2}-\d{8}-\d$/;
const PESOS = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2] as const;

export function cuitValido(cuit: string): boolean {
  if (!CUIT_RE.test(cuit)) return false;

  const digitos = [...cuit.replace(/-/g, "")].map(Number);
  const suma = PESOS.reduce((acc, peso, i) => acc + digitos[i] * peso, 0);
  const resto = suma % 11;

  let verificador = resto === 0 ? 0 : 11 - resto;
  if (verificador === 10) verificador = 9;

  return verificador === digitos[10];
}

/** El CUIT es OPCIONAL: un consumidor final que compra una vez no tiene por qué darlo. Pero si lo
 *  escribió, tiene que estar bien — un CUIT a medias es peor que ninguno, porque parece un dato. */
export function cuitAceptable(cuit: string): boolean {
  return cuit.trim() === "" || cuitValido(cuit);
}
