/** El estado de una compra en curso: proveedor + número de comprobante + renglones + condición.
 *
 * Vive en un useReducer LOCAL de la página, no en Zustand, a propósito (mismo criterio que la
 * venta): una compra a medio armar es válida solo mientras la pantalla está abierta.
 */

/** Depósito por defecto: la mercadería entra al central y el operador puede pisarlo. */
export const DEPOSITO_MOSTRADOR = "CEN";

export interface RenglonCompra {
  articulo_codigo: string;
  detalle: string;
  cantidad: string; // string: en el camino de escritura la plata/cantidad no pasa por Number
  costo_unitario: string; // neto, sin IVA
  alicuota_iva: number; // solo para el total en pantalla; el backend usa la del artículo
}

export interface Estado {
  paso: "armar" | "listo";
  proveedorCodigo: string;
  numeroComprobante: string;
  condicion: "contado" | "cta_cte";
  deposito: string;
  renglones: RenglonCompra[];
}

export const ESTADO_INICIAL: Estado = {
  paso: "armar",
  proveedorCodigo: "",
  numeroComprobante: "",
  condicion: "contado",
  deposito: DEPOSITO_MOSTRADOR,
  renglones: [],
};

export type Accion =
  | { type: "proveedor"; codigo: string }
  | { type: "numero"; valor: string }
  | { type: "condicion"; valor: "contado" | "cta_cte" }
  | { type: "deposito"; valor: string }
  | { type: "agregar"; renglon: RenglonCompra }
  | { type: "renglon"; i: number; campo: "cantidad" | "costo_unitario"; valor: string }
  | { type: "quitar"; i: number }
  | { type: "emitido" }
  | { type: "reset" };

export function reducer(estado: Estado, accion: Accion): Estado {
  switch (accion.type) {
    case "proveedor":
      return { ...estado, proveedorCodigo: accion.codigo };

    case "numero":
      return { ...estado, numeroComprobante: accion.valor };

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

/** Un renglón comprable: cantidad positiva y costo no negativo. */
export function renglonValido(r: RenglonCompra): boolean {
  return (
    r.articulo_codigo.trim().length > 0 &&
    Number(r.cantidad) > 0 &&
    Number(r.costo_unitario) >= 0 &&
    r.costo_unitario.trim().length > 0
  );
}

export function puedeEmitir(estado: Estado): boolean {
  return (
    estado.proveedorCodigo.trim().length > 0 &&
    estado.numeroComprobante.trim().length > 0 &&
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
 * renglón; esto es para que el operador vea a cuánto va la compra mientras la arma. */
export function totales(renglones: RenglonCompra[]): Totales {
  let neto = 0;
  let iva = 0;
  for (const r of renglones) {
    const base = Number(r.cantidad) * Number(r.costo_unitario);
    if (Number.isFinite(base) && base > 0) {
      neto += base;
      iva += (base * r.alicuota_iva) / 100;
    }
  }
  return { neto, iva, total: neto + iva };
}
