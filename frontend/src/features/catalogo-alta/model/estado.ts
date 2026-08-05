/** Lógica pura del alta de artículo. Sin React: se testea sin montar nada.
 *
 * La reja del formulario es la MISMA que la del service (`alta_articulo`), no una distinta: el
 * backend es el que manda, pero mandarle un precio sin lista es un viaje al servidor para volver
 * con un 422 que se podía evitar. Que el botón no se habilite explica más rápido que un error rojo.
 */

import type { ArticuloAltaRequest } from "@/entities/articulo/schema";

/** Vocabulario CERRADO: son las alícuotas que reconoce AFIP, no una preferencia nuestra. Mismo
 *  criterio que `CONDICIONES_FISCALES` — un input libre invita al typo "2.1" y nada lo atrapa.
 *
 *  El orden es el del mostrador: 21 primero porque es lo que lleva casi todo un repuesto. Los
 *  valores viajan con dos decimales para espejar `numeric(5,2)` de la columna. */
export const ALICUOTAS_IVA = [
  { id: "21.00", label: "21 %" },
  { id: "10.50", label: "10,5 %" },
  { id: "27.00", label: "27 %" },
  { id: "0.00", label: "0 %" },
] as const;

export type AlicuotaIva = (typeof ALICUOTAS_IVA)[number]["id"];

export interface FormularioArticulo {
  codigo: string;
  detalle: string;
  costo: string;
  alicuota_iva: AlicuotaIva;
  marca: string;
  rubro: string;
  codigo_barra: string;
  costo_dolar: string;
  punto_pedido: string;
  precio: string;
  /** El id de la lista como string: es lo que emite un `<select>`. `""` = ninguna elegida. */
  lista_id: string;
}

export const VACIO: FormularioArticulo = {
  codigo: "",
  detalle: "",
  costo: "",
  alicuota_iva: "21.00",
  marca: "",
  rubro: "",
  codigo_barra: "",
  costo_dolar: "",
  punto_pedido: "",
  precio: "",
  lista_id: "",
};

/** Hay un precio de venta utilizable. `Number("")` y `Number("   ")` dan 0, así que el campo
 *  vacío cae solo. */
export function tienePrecio(f: FormularioArticulo): boolean {
  return Number(f.precio) > 0;
}

/** Hay algo escrito en el precio que NO es un precio: un "0", o lo que no sea un número.
 *
 * Bloquea el guardado en vez de descartarse en silencio. El backend valida `gt=0`, así que un
 * precio en cero no se puede fijar; si el payload lo mandara como `null`, el artículo se crearía
 * "sin precio" y la persona vería una advertencia sobre algo que sí escribió. Prefiero el botón
 * apagado: obliga a decidir entre poner un precio o dejar el campo vacío. */
export function precioInvalido(f: FormularioArticulo): boolean {
  return f.precio.trim() !== "" && !tienePrecio(f);
}

/** Precio sin lista elegida.
 *
 * No hay lista por defecto a nivel sistema, así que elegir una en silencio sería inventar el
 * precio de venta de un artículo. El backend responde 422; acá se ve antes de mandar. */
export function precioSinLista(f: FormularioArticulo): boolean {
  return tienePrecio(f) && f.lista_id === "";
}

export function puedeGuardar(f: FormularioArticulo): boolean {
  return (
    f.codigo.trim() !== "" &&
    f.detalle.trim() !== "" &&
    !precioInvalido(f) &&
    !precioSinLista(f)
  );
}

/** Arma el body del POST.
 *
 * Los opcionales vacíos viajan como `null`, no como `""`: la columna es nullable y un string
 * vacío es un dato que después hay que limpiar. El `.trim()` de acá NO reemplaza al del service
 * (`_normalizar`) — ese es el que arbitra la unicidad del código; este solo evita mandar basura.
 *
 * Costo y punto de pedido caen en `"0"` cuando están vacíos, no en `null`: la columna es NOT NULL
 * con default 0 y un artículo sin costo cargado cuesta cero, no "se desconoce".
 *
 * La lista viaja SOLO si hay precio. Un `lista_id` suelto el backend lo ignora con una
 * advertencia, pero mandarlo sería decir que fijamos un precio que no fijamos. */
export function aPayload(f: FormularioArticulo): ArticuloAltaRequest {
  const opcional = (v: string) => (v.trim() === "" ? null : v.trim());
  const oCero = (v: string) => (v.trim() === "" ? "0" : v.trim());
  const conPrecio = tienePrecio(f);

  return {
    codigo: f.codigo.trim(),
    detalle: f.detalle.trim(),
    costo: oCero(f.costo),
    costo_dolar: opcional(f.costo_dolar),
    alicuota_iva: f.alicuota_iva,
    punto_pedido: oCero(f.punto_pedido),
    codigo_barra: opcional(f.codigo_barra),
    marca: opcional(f.marca),
    rubro: opcional(f.rubro),
    precio: conPrecio ? f.precio.trim() : null,
    lista_id: conPrecio && f.lista_id !== "" ? Number(f.lista_id) : null,
  };
}
