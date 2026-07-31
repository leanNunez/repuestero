# Dirección de arte — Repuestero

Leer este documento antes de cualquier tarea de UI. Toda decisión visual nueva
se valida contra este bloque; si lo contradice, se discute acá primero.

## Direction Block

```
Tone: industrial, preciso, de mostrador
Signature move: "El número manda" — cada cifra que importa (KPI, importe, saldo)
  va en Chivo Mono tabular y a 44px, tres veces el cuerpo de texto. La app se
  reconoce de un vistazo por sus números enormes y sus columnas encolumnadas,
  como una planilla de mostrador bien llevada.
Type: Chivo Mono (números, códigos, KPIs) / Chivo (UI y body) / ratio 1.25
  Display real: 44px contra 14px de body = 3,1×. Una jerarquía tímida es lo
  que se lee como genérico.
Color: dominante rampa neutra grafito→gris→blanco (~90% de la superficie).
  Acento ÁMBAR #b45309 (claro) / #f59e0b (sobre grafito): señalética industrial,
  el color del bronce y del aceite. Va solo en la barra del item activo, en el
  logo y en detalles que piden atención — nunca como superficie grande.
  El celeste #2f6fe0 se retira a rol FUNCIONAL (botones, links) y al territorio
  del asistente, que es de donde vino: es el color del SVG de Repu.
Space: base 4px, densidad TIGHT (admin data-heavy; el usuario vino a ver filas).
  Canvas hundido + cards elevadas: la jerarquía de superficies se ve sin color.
Motion: 150ms / cubic-bezier(0.2, 0, 0, 1) — solo estados interactivos y
  entrada de dialog/toast. Nunca `transition-all`: se listan las propiedades.
Rejected: Inter/system-ui como cara de marca; indigo shadcn de fábrica;
  cards con sombra para datos tabulares; y el sidebar de COLOR SÓLIDO — es la
  marca registrada del admin template y violaba el ≤10% del acento.
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
