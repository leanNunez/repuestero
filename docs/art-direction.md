# Dirección de arte — Repuestero

Leer este documento antes de cualquier tarea de UI. Toda decisión visual nueva
se valida contra este bloque; si lo contradice, se discute acá primero.

## Direction Block

```
Tone: preciso, sobrio, de mostrador
Signature move: "Columnas de plata" — todo importe en Chivo Mono con cifras
  tabulares, alineado a la derecha, formato es-AR. La app se reconoce por sus
  columnas de números perfectamente encolumnadas, como una planilla de
  mostrador bien llevada.
Type: Chivo Mono (números, códigos, KPIs) / Chivo (UI y body) / ratio 1.25
Color: dominante neutro zinc / acento celeste #2f6fe0 en ≤10% de la superficie
  (sidebar, primary, focus ring, links) / neutros existentes.
  UN solo azul: el celeste marca (4.70:1 con texto blanco → AA). El indigo
  #4f46e5 shadcn-default queda eliminado.
Space: base 4px, densidad TIGHT (admin data-heavy; el usuario vino a ver filas)
Motion: 150ms / cubic-bezier(0.2, 0, 0, 1) — solo estados interactivos y
  entrada de dialog/toast. Nada más se anima.
Rejected: Inter/system-ui como cara de marca; indigo shadcn de fábrica;
  cards con sombra para datos tabulares (tablas > cards).
```

## Tipografía

- **Chivo** (UI y body) + **Chivo Mono** (importes, códigos, KPIs), superfamilia
  de Omnibus-Type. Self-hosted vía `@fontsource-variable/*`; nunca Google Fonts CDN.
- Escala con ratio 1.25 desde body 14px: `12 / 14 / 18 / 22 / 28 / 35 / 44`,
  tokenizada en `@theme` con line-height por tier (más grande → más apretado).
- `tabular-nums` lo aplican los primitivos (`Money`, `Table`), no global.

## Política de feedback

- **Toasts (sonner): SOLO confirmaciones efímeras** sin datos que el usuario
  necesite retener ("Movimiento registrado", "Copiado").
- **Errores: siempre inline**, nunca toast — un toast se va y el problema queda
  (`features/caja/model/estado.ts`).
- **Éxitos persistentes con datos** (número de comprobante emitido) →
  `SuccessPanel`, no toast.

## Self-check antes de entregar UI

1. Probar en 375px Y 1440px, en claro Y oscuro.
2. Screenshot en escala de grises: la jerarquía debe leerse sin color.
3. Columnas de importes: encolumnadas con datos reales (la signature move).
4. Un solo `<h1>` por vista.
