/** Query string de una página de un padrón (clientes, proveedores).
 *
 * Vive suelto y no dentro de un hook porque es aritmética: el offset se deriva de la página, y la
 * aritmética se testea sin montar nada. Errar el ±1 saltea o repite una página entera y no lo nota
 * nadie hasta que falta un registro.
 */
export function queryPagina(q: string, page: number, pageSize: number): string {
  const params = new URLSearchParams({
    limite: String(pageSize),
    // La página 1 es offset 0: el usuario cuenta desde 1, el backend desde 0. `Math.max` porque
    // la URL la escribe cualquiera y `?page=0` no puede convertirse en un offset negativo y un 422.
    offset: String((Math.max(page, 1) - 1) * pageSize),
  });

  // Un `buscar=` vacío haría que el backend filtre por el patrón `%%`. Anda de casualidad; es más
  // honesto no mandar el parámetro cuando no hay búsqueda.
  const query = q.trim();
  if (query) params.set("buscar", query);

  return params.toString();
}
