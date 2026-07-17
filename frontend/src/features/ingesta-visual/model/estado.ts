import type { Propuesta, RenglonPropuesta } from "@/entities/remito/schema";

/** El estado de la revisión: la propuesta de Repu + lo que el humano editó encima.
 *
 * Vive en un useReducer LOCAL de la página, no en Zustand, y es a propósito: la propuesta
 * es válida solo mientras esa pantalla está abierta. En un store global sobreviviría a la
 * navegación y se volvería mentira — volvés media hora después y "confirmás" un remito
 * contra un catálogo que ya cambió.
 */

export interface RenglonEditable extends RenglonPropuesta {
  /** Si entra en la carga. El humano manda. */
  incluir: boolean;
  /** Los editables arrancan con lo que leyó Repu y el humano los pisa. Strings: son plata. */
  codigo_editado: string;
  detalle_editado: string;
  cantidad_editada: string;
  costo_editado: string;
}

export interface Estado {
  paso: "capturar" | "revisar" | "listo";
  propuesta: Propuesta | null;
  renglones: RenglonEditable[];
  deposito: string;
  proveedorCodigo: string;
  numeroRemito: string;
}

export const ESTADO_INICIAL: Estado = {
  paso: "capturar",
  propuesta: null,
  renglones: [],
  deposito: "",
  proveedorCodigo: "",
  numeroRemito: "",
};

export type Accion =
  | { type: "propuesta"; propuesta: Propuesta }
  | { type: "renglon"; i: number; campo: keyof RenglonEditable; valor: string | boolean }
  | { type: "campo"; campo: "deposito" | "proveedorCodigo" | "numeroRemito"; valor: string }
  | { type: "confirmado" }
  | { type: "reset" };

function aEditable(r: RenglonPropuesta): RenglonEditable {
  return {
    ...r,
    // El default de incluir lo sugiere el server (apaga sin_codigo y texto_sospechoso).
    // El default seguro es NO escribir lo que no se puede escribir bien.
    incluir: r.incluir_sugerido,
    codigo_editado: r.codigo ?? "",
    detalle_editado: r.descripcion,
    cantidad_editada: r.cantidad,
    costo_editado: r.costo_unitario,
  };
}

/** Los flags que de verdad piden una mirada.
 *
 * `alta_sin_precio` NO cuenta: que un artículo sea nuevo es información, no un problema, y
 * ya se comunica con su badge azul. Si se pinta de ámbar lo normal, el ámbar deja de querer
 * decir "cuidado" y la gente aprende a ignorarlo — que es exactamente cómo un `salto_de_costo`
 * termina pasando de largo.
 */
export function flagsDeAtencion(r: Pick<RenglonEditable, "atencion">): string[] {
  return r.atencion.filter((f) => f !== "alta_sin_precio");
}

/** Ordena los renglones que necesitan atención PRIMERO.
 *
 * Que lo dudoso esté arriba no es cosmético: es lo que hace que la revisión sea una revisión
 * y no un "Confirmar" reflejo. Lo que está bien se mira rápido; lo marcado pide la vista.
 */
function porAtencion(a: RenglonEditable, b: RenglonEditable): number {
  return flagsDeAtencion(b).length - flagsDeAtencion(a).length;
}

export function reducer(estado: Estado, accion: Accion): Estado {
  switch (accion.type) {
    case "propuesta":
      return {
        ...estado,
        paso: "revisar",
        propuesta: accion.propuesta,
        renglones: accion.propuesta.renglones.map(aEditable).sort(porAtencion),
        numeroRemito: accion.propuesta.numero_remito ?? "",
      };

    case "renglon": {
      const renglones = [...estado.renglones];
      renglones[accion.i] = { ...renglones[accion.i], [accion.campo]: accion.valor };
      return { ...estado, renglones };
    }

    case "campo":
      return { ...estado, [accion.campo]: accion.valor };

    case "confirmado":
      return { ...estado, paso: "listo" };

    case "reset":
      return ESTADO_INICIAL;
  }
}

/** Un renglón incluido tiene que poder escribirse: sin código o sin cantidad no hay carga. */
export function renglonValido(r: RenglonEditable): boolean {
  return (
    r.codigo_editado.trim().length > 0 &&
    r.detalle_editado.trim().length > 0 &&
    Number(r.cantidad_editada) > 0 &&
    Number(r.costo_editado) >= 0
  );
}

export function puedeConfirmar(estado: Estado): boolean {
  const incluidos = estado.renglones.filter((r) => r.incluir);
  return (
    estado.deposito.trim().length > 0 &&
    incluidos.length > 0 &&
    incluidos.every(renglonValido)
  );
}
