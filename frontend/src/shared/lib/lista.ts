/** Mueve el índice activo de una lista navegable con flechas. `-1` = nada activo todavía.
 *
 * Vive suelto y no dentro del componente por dos motivos. Uno es aritmético: los bordes —la lista
 * vacía, el salto desde "nada elegido", la vuelta de punta a punta— son tres casos que en un
 * `onKeyDown` no se prueban nunca y que se rompen justo cuando alguien navega sin mouse. El otro
 * es que exportar una función desde un archivo de componentes le rompe el fast refresh a Vite.
 *
 * Da la vuelta a propósito: en el mostrador se busca con una mano y se teclea con la otra, y
 * frenar en la última opción obliga a contar cuántas veces apretar para volver arriba.
 */
export function moverIndice(actual: number, delta: number, total: number): number {
  if (total <= 0) return -1;
  // Desde "nada activo", bajar lleva a la primera y subir a la última.
  if (actual < 0) return delta > 0 ? 0 : total - 1;
  return (actual + delta + total) % total;
}
