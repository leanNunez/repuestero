# ADR 0001 — Offline-first en el mostrador

- **Estado:** Aceptada (dirección definida) · **NO implementada todavía**
- **Fecha:** 2026-07-17
- **Contexto de fase:** decisión de arquitectura para una fase futura; el demo actual es online-only.

## Contexto

RepuestOS es un ERP para casas de repuestos: comercios **de mostrador**, donde la venta y el
descuento de stock ocurren en tiempo real frente al cliente. El sistema hoy es un SPA + API en la
nube: si se cae internet, la caja **deja de operar**. Para una demo no importa; para un producto
real es una objeción de primer orden — la conectividad en Argentina (zonas industriales, pueblos,
cortes de luz) no es 100% confiable, y "funciona con o sin internet" es algo que la competencia
(ej. Contabilium) vende explícitamente.

**El matiz fiscal (AFIP):** la factura electrónica **requiere** internet para obtener el CAE. Nunca
se puede estar 100 % offline para lo fiscal. Pero la **operación** —vender, mover stock,
presupuestar, cargar un remito, consultar catálogo/cuenta corriente— NO necesita AFIP en tiempo
real. AFIP contempla un **régimen de contingencia**: se opera y el CAE se solicita cuando vuelve la
conexión. La clave del diseño es separar **operación** (puede ser offline) de **fiscalización**
(online, diferible).

## Decisión

Adoptar una arquitectura **local-first / offline-first con sincronización**, implementada de forma
**acotada (scoped)**, no de una sola vez:

1. **Primera tajada: el flujo de mostrador** (venta + descuento de stock). Es el que no puede
   detenerse. El resto de los módulos siguen online mientras tanto.
2. **Frontend como PWA** instalable, con service worker que cachea el shell y los assets.
3. **Capa de datos local** (IndexedDB / SQLite-WASM) que la UI lee y escribe **al instante**, sin
   depender de la red.
4. **Motor de sincronización** que reconcilia local ↔ Postgres en la nube cuando hay conexión.
5. La **nube sigue siendo la fuente de verdad** para multi-tenant, multi-sucursal, backups y el
   gateway a AFIP.

Herramientas candidatas a evaluar sobre el Postgres existente: **PowerSync**, **ElectricSQL**,
**RxDB**. La elección se decide en el spike de implementación, no acá.

## Por qué es viable acá (las fundaciones ya están puestas)

Las invariantes que el proyecto ya tiene por diseño son, exactamente, lo que un motor de sync
necesita — no hay que reescribir el modelo para habilitar esto:

- **Libro mayor append-only** (movimientos inmutables, saldo como vista, §2.6 / §4.4): sincroniza
  replayando eventos, sin conflictos de "quién pisó el saldo de quién".
- **Idempotencia por hash** (el `remito_hash` con unique index de la ingesta visual): es
  literalmente la clave de deduplicación que un sync necesita para no aplicar dos veces la misma
  operación.
- **Numeración con autoridad de servidor** (secuencias / bloqueo transaccional, §2.1): resuelve el
  problema clásico de "dos cajas offline emiten el comprobante N° 5". El número se asigna en el
  sync (autoridad central) o con prefijo por dispositivo.
- **Plata en `numeric`** y **multi-tenant por RLS**: base consistente para reconciliar sin pérdida.

## Alternativas consideradas

| Opción | Por qué NO como respuesta final |
|--------|--------------------------------|
| **Cloud puro** (estado actual) | Lo que usan hoy Dux/Colppy/Alegra, y es válido con un router 4G de respaldo. Pero como ÚNICA opción deja la caja sin red = sin operar. Sirve para el demo, no para el diferencial. |
| **On-premise** (modelo del legacy Delphi/Paradox) | Anda sin internet, pero vuelve a los problemas que este proyecto arregla: hardware por cliente, backups a cargo del dueño, soporte remoto difícil. Es a dónde NO queremos volver. |
| **Offline-first con sync** (elegida) | Lo mejor de los dos: la caja opera local e instantánea, y reconcilia con la nube al volver. Más complejo, pero es la arquitectura correcta para el dominio. |

## Consecuencias

**A favor**
- La caja no se detiene por un corte de internet: resiliencia operativa real.
- Diferencial competitivo concreto ("funciona con o sin internet").
- Pieza de arquitectura de nivel senior para el CV: es un problema de sistemas distribuidos
  (conflict resolution, ordering, idempotencia, reconciliación), no "otro CRUD en la nube".

**En contra / a vigilar**
- **Complejidad de sincronización:** conflictos, orden de eventos, reconciliación. Es el costo real
  de esta decisión y por eso se hace **acotado**, no de golpe.
- **AFIP nunca es 100 % offline:** lo fiscal queda diferido (contingencia), no eliminado.
- **Alcance vs. tiempo (ver §8.4 del blueprint):** el riesgo del proyecto es querer construirlo
  todo. Esta ADR **no** se implementa hasta que Fase 1 esté deployada. Primero el demo online-only.

## Estado de implementación

- **No implementado.** El demo sigue siendo online-only, y está bien que así sea por ahora.
- **Disparador:** encarar la tajada del mostrador cuando el demo esté deployado y se priorice sobre
  las otras features abiertas.

Relacionado: blueprint §2.6 (ledger append-only), §4.3 (multi-tenancy/RLS), §7 (roadmap, fase
"offline resiliente"), §8.1 (riesgo original que esta ADR resuelve como dirección).
