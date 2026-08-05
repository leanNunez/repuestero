import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  articuloAltaResponseSchema,
  type ArticuloAltaRequest,
  type ArticuloAltaResponse,
} from "@/entities/articulo/schema";
import { apiPost } from "@/shared/api/client";

/** Alta de artículo. El código lo TIPEA la persona (es el del fabricante), así que el 409 por
 *  duplicado es un resultado esperable de esta mutación, no una rareza.
 *
 *  Se invalida el prefijo `["catalogo"]` ENTERO y no solo el listado: un artículo con rubro nuevo
 *  tiene que aparecer en el dropdown de filtros, que vive en `["catalogo","rubros"]` y está
 *  cacheado 5 minutos. Invalidar solo el listado dejaría el filtro sin la opción recién creada. */
export function useCrearArticulo() {
  const qc = useQueryClient();

  return useMutation<ArticuloAltaResponse, Error, ArticuloAltaRequest>({
    mutationFn: (vars) => apiPost("/catalogo/articulos", vars, articuloAltaResponseSchema),
    // Sin retry: los errores de acá son de negocio (409 por código repetido, 422 por precio sin
    // lista). Reintentar a ciegas no cambia el resultado y, si el alta llegó a escribir, el
    // segundo intento choca contra el unique y muestra un error de un alta que SÍ funcionó.
    retry: false,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["catalogo"] });
    },
  });
}
