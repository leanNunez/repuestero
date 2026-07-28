/** Lógica pura del alta de cliente. Sin React: se testea sin montar nada.
 *
 * El CUIT se valida ACÁ además de en el backend, y no es duplicación por descuido. El backend es
 * el que manda —esa validación no se toca— pero mandarle un CUIT que ya sabemos que está mal es
 * un viaje al servidor para volver con un error rojo que se podía evitar. Que el botón no se
 * habilite explica más rápido que un 422.
 */

const CUIT_RE = /^\d{2}-\d{8}-\d$/;
const PESOS_CUIT = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2] as const;

/** Espeja `app/core/cond_fiscal.py`. El orden es el del formulario: primero lo más frecuente en el
 *  mostrador. `EXENTO` va último porque casi no aparece. */
export const CONDICIONES_FISCALES = [
  { id: "CONSUMIDOR_FINAL", label: "Consumidor final" },
  { id: "MONOTRIBUTO", label: "Monotributo" },
  { id: "RESPONSABLE_INSCRIPTO", label: "Responsable inscripto" },
  { id: "EXENTO", label: "Exento" },
] as const;

export type CondFiscal = (typeof CONDICIONES_FISCALES)[number]["id"];

/** Valida formato y dígito verificador (módulo 11). Port exacto de `clientes.service.cuit_valido`.
 *
 * Si algún día cambia el algoritmo, cambia en los dos lados o el front empieza a bloquear CUITs
 * que el backend acepta — que es peor que no validar: el dato válido no entra y nadie sabe por qué.
 */
export function cuitValido(cuit: string): boolean {
  if (!CUIT_RE.test(cuit)) return false;

  const digitos = [...cuit.replace(/-/g, "")].map(Number);
  const suma = PESOS_CUIT.reduce((acc, peso, i) => acc + digitos[i] * peso, 0);
  const resto = suma % 11;

  let verificador = resto === 0 ? 0 : 11 - resto;
  if (verificador === 10) verificador = 9;

  return verificador === digitos[10];
}

export interface FormularioCliente {
  denominacion: string;
  cuit: string;
  cond_fiscal: CondFiscal;
  limite_cta_cte: string;
  telefono: string;
  email: string;
  direccion: string;
}

export const VACIO: FormularioCliente = {
  denominacion: "",
  cuit: "",
  cond_fiscal: "CONSUMIDOR_FINAL",
  limite_cta_cte: "",
  telefono: "",
  email: "",
  direccion: "",
};

/** El CUIT es OPCIONAL: un consumidor final que compra una vez no tiene por qué darlo. Pero si lo
 *  escribió, tiene que estar bien — un CUIT a medias es peor que ninguno, porque parece un dato. */
export function cuitAceptable(cuit: string): boolean {
  return cuit.trim() === "" || cuitValido(cuit);
}

export function puedeGuardar(f: FormularioCliente): boolean {
  return f.denominacion.trim() !== "" && cuitAceptable(f.cuit);
}

/** Arma el body del POST. Los opcionales vacíos viajan como `null`, no como `""`: la columna es
 *  nullable y un string vacío es un dato que después hay que limpiar. */
export function aPayload(f: FormularioCliente) {
  const opcional = (v: string) => (v.trim() === "" ? null : v.trim());

  return {
    denominacion: f.denominacion.trim(),
    cuit: opcional(f.cuit),
    cond_fiscal: f.cond_fiscal,
    limite_cta_cte: f.limite_cta_cte === "" ? "0" : f.limite_cta_cte,
    telefono: opcional(f.telefono),
    email: opcional(f.email),
    direccion: opcional(f.direccion),
  };
}
