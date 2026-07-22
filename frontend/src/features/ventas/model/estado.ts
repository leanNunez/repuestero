/** El estado de una venta en curso: cliente + renglones + condición.
 *
 * Vive en un useReducer LOCAL de la página, no en Zustand, y a propósito (mismo criterio que
 * la ingesta de remitos): una venta a medio armar es válida solo mientras la pantalla está
 * abierta. En un store global sobreviviría a la navegación y "confirmarías" contra un stock que
 * ya cambió.
 */

/** Depósito por defecto del mostrador. El backend exige `deposito_codigo`; para el flujo de caja
 * arranca en el central y el operador puede pisarlo. */
export const DEPOSITO_MOSTRADOR = "CEN";

export interface RenglonVenta {
  articulo_codigo: string;
  detalle: string;
  cantidad: string; // string: en el camino de escritura la plata/cantidad no pasa por Number
  precio_unitario: string; // neto, sin IVA
  alicuota_iva: number; // solo para el total en pantalla; el backend usa la del artículo
  lista_codigo: string | null; // de qué lista salió el precio precargado (para mostrar)
}

export interface Estado {
  paso: "armar" | "listo";
  clienteCodigo: string;
  condicion: "contado" | "cta_cte";
  deposito: string;
  renglones: RenglonVenta[];
}

export const ESTADO_INICIAL: Estado = {
  paso: "armar",
  clienteCodigo: "",
  condicion: "contado",
  deposito: DEPOSITO_MOSTRADOR,
  renglones: [],
};

export type Accion =
  | { type: "cliente"; codigo: string }
  | { type: "condicion"; valor: "contado" | "cta_cte" }
  | { type: "deposito"; valor: string }
  | { type: "agregar"; renglon: RenglonVenta }
  | { type: "renglon"; i: number; campo: "cantidad" | "precio_unitario"; valor: string }
  | { type: "quitar"; i: number }
  | { type: "emitido" }
  | { type: "reset" };

export function reducer(estado: Estado, accion: Accion): Estado {
  switch (accion.type) {
    case "cliente":
      return { ...estado, clienteCodigo: accion.codigo };

    case "condicion":
      return { ...estado, condicion: accion.valor };

    case "deposito":
      return { ...estado, deposito: accion.valor };

    case "agregar":
      return { ...estado, renglones: [...estado.renglones, accion.renglon] };

    case "renglon": {
      const renglones = [...estado.renglones];
      renglones[accion.i] = { ...renglones[accion.i], [accion.campo]: accion.valor };
      return { ...estado, renglones };
    }

    case "quitar":
      return { ...estado, renglones: estado.renglones.filter((_, i) => i !== accion.i) };

    case "emitido":
      return { ...estado, paso: "listo" };

    case "reset":
      return ESTADO_INICIAL;
  }
}

/** Un renglón vendible: cantidad positiva y precio no negativo. */
export function renglonValido(r: RenglonVenta): boolean {
  return (
    r.articulo_codigo.trim().length > 0 &&
    Number(r.cantidad) > 0 &&
    Number(r.precio_unitario) >= 0 &&
    r.precio_unitario.trim().length > 0
  );
}

export function puedeEmitir(estado: Estado): boolean {
  return (
    estado.clienteCodigo.trim().length > 0 &&
    estado.deposito.trim().length > 0 &&
    estado.renglones.length > 0 &&
    estado.renglones.every(renglonValido)
  );
}

export interface Totales {
  neto: number;
  iva: number;
  total: number;
}

/** Total en pantalla (solo presentación). El importe que se GUARDA lo calcula el backend por
 * renglón; esto es para que el operador vea a cuánto va la venta mientras la arma. */
export function totales(renglones: RenglonVenta[]): Totales {
  let neto = 0;
  let iva = 0;
  for (const r of renglones) {
    const base = Number(r.cantidad) * Number(r.precio_unitario);
    if (Number.isFinite(base) && base > 0) {
      neto += base;
      iva += (base * r.alicuota_iva) / 100;
    }
  }
  return { neto, iva, total: neto + iva };
}
