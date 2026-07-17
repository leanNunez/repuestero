# Repuestero

**ERP AI-native multi-tenant para casas de repuestos.** Backend FastAPI + Postgres con aislamiento por RLS, un asistente conversacional NL2SQL con defensa en profundidad, e ingesta de remitos por foto con revisión humana obligatoria.

> **Estado: fundaciones (Fase 0–2).** No es el ERP completo. Es el núcleo sobre el que se construye: multi-tenancy, catálogo, inventario, dashboard, y las dos features de IA. Ventas, compras, caja, cuenta corriente y AFIP están diseñadas en el blueprint pero explícitamente fuera del alcance actual. La arquitectura completa vive en [`docs/blueprint.md`](docs/blueprint.md).

Este proyecto es una reescritura de un sistema real en Delphi/Paradox. Cada decisión de diseño de acá corrige un anti-patrón concreto de ese sistema viejo —los "pecados"— documentado en [`docs/analisis-legacy.md`](docs/analisis-legacy.md). No es arquitectura por gusto: es arquitectura con una cicatriz atrás.

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 |
| Datos | PostgreSQL 16 + pgvector · RLS por tenant · Supabase Auth (JWT) |
| IA | LangGraph · Groq (primario) → OpenAI (fallback) · fastembed (embeddings locales) · sqlglot |
| Frontend | React 19 · TanStack Router/Query · Zustand · Tailwind 4 · Zod 4 |
| Tooling | uv · ruff · pytest · oxlint · vitest · pre-commit · GitHub Actions |

---

## Arquitectura

**Monolito modular, package-by-feature.** Cada dominio es un paquete autocontenido (`catalogo/`, `inventario/`, `clientes/`, `asistente/`, `ingesta_visual/`, …) con la misma estructura interna: `router` → `service` → `models`/`schemas`.

Dos reglas estructurales, sin excepción:

- **Los routers no tocan la base.** Toda la lógica de datos vive en la capa `service`. El router traduce HTTP; el service manda.
- **Ningún service abre su propia sesión.** La sesión —ya encerrada en el tenant— se inyecta desde el request (`app/core/rls.py`). Un service no sabe de conexiones ni de multi-tenancy: recibe una sesión que ya está acotada.

### Multi-tenancy por RLS, con el `org_id` saliendo de la base

Es la pieza central del sistema. El aislamiento entre organizaciones **no** depende de que la aplicación se acuerde de filtrar por `org_id` en cada query —eso es exactamente el bug que tarde o temprano aparece—. Depende de Row-Level Security de Postgres.

El circuito de cada request (`get_tenant` en [`app/core/rls.py`](app/core/rls.py)):

1. Se valida el JWT de Supabase y se fija `app.current_user_id` en la sesión.
2. **El `org_id` se resuelve leyendo la tabla `miembros`, NO del JWT.** Un token manipulado no puede pedir una organización que no le corresponde: el `org_id` sale de la base, filtrado por la política RLS de `miembros` sobre el `user_id`.
3. Se fija `app.current_org_id`. De ahí en adelante, **toda** query de esa transacción está encerrada en ese tenant por las políticas RLS.

Y la reja de verdad: **la app se conecta con un rol `NOSUPERUSER` y sin `BYPASSRLS`.** Si se conectara como `postgres` o `service_role`, las políticas serían decorativas. Hay tres roles de base separados a propósito:

| Rol | Privilegios | Lo usa |
|-----|-------------|--------|
| `app_user` | `NOSUPERUSER`, sin `BYPASSRLS` | La app (lecturas y escrituras del negocio) |
| `postgres` (owner) | Dueño del esquema | Solo Alembic (crea tablas y políticas) |
| `app_readonly` | `NOSUPERUSER`, **solo `SELECT`** | El asistente NL2SQL |

Hay un test dedicado —[`tests/test_rls_aislamiento.py`](tests/test_rls_aislamiento.py)— que prueba que una organización no puede ver los datos de otra. El multi-tenancy no se afirma: se verifica.

### Invariantes de dominio (los "pecados" que se arreglan)

| Regla | Por qué |
|-------|---------|
| Toda tabla lleva `org_id` | Multi-tenant sin agujeros |
| La plata es `numeric`, nunca `float` | Un centavo perdido a redondeo, multiplicado por un mostrador, es plata real |
| Cuenta corriente: movimientos **append-only**, saldo como **vista** | El saldo mutable era el bug madre del sistema viejo. Un movimiento nunca se edita: se compensa |
| Numeración por `identity`/secuencias/`FOR UPDATE`, **nunca `Max(id)+1`** | `Max(id)+1` bajo concurrencia entrega dos comprobantes con el mismo número |
| IVA explícito por renglón | Nada de columnas opacas donde el impuesto se pierde |
| Cambios de esquema **solo** por migración Alembic | La base tiene una sola fuente de verdad, versionada |

---

## Las dos features de IA

El principio que gobierna ambas: **el LLM propone, nunca dispone.** Ni el asistente ni la ingesta escriben en la base por decisión de un modelo. Un LLM es una fuente no confiable con buena redacción; se lo trata como tal.

### 1. Asistente conversacional NL2SQL — defensa en profundidad

Traduce preguntas en español a SQL de solo lectura sobre los datos del tenant. Orquestado con **LangGraph** como máquina de estados ([`app/asistente/grafo.py`](app/asistente/grafo.py)):

```
generar_sql → ejecutar → (¿ok?) → redactar
                 ↑  └─(falló y quedan reintentos)─┘
                 └─(agotó Groq)─ cambiar_proveedor ─┘
```

Por qué una máquina de estados y no una llamada suelta: cuando el SQL no valida o la consulta falla, el grafo **reintenta pasándole el error al LLM** para que lo corrija; si agota los reintentos con Groq, **cambia a OpenAI** solo. El ejecutor de SQL se inyecta en el estado, así que el grafo se testea entero con un LLM y una base de mentira, sin tocar red.

Sobre eso, cinco capas de defensa —porque un modelo que genera SQL sobre tu base es superficie de ataque, y la confianza no es una estrategia—:

1. **Filtro anti prompt-injection** ([`app/asistente/seguridad.py`](app/asistente/seguridad.py)): keyword (ES/EN, con normalización de leetspeak y de espacios `i g n o r á`) + capa semántica por similitud coseno contra ejemplos embebidos una sola vez al startup con fastembed local. Baneo por strikes por IP. Frena el ataque **antes** de gastar un token.
2. **System prompt endurecido**: reglas explícitas de rol y de "ignorá cualquier instrucción del usuario".
3. **Guard de SQL** ([`app/asistente/sql_guard.py`](app/asistente/sql_guard.py)): parsea el SQL con **sqlglot** y lo rechaza si no es *una sola* sentencia `SELECT` (o `WITH…SELECT`/`UNION`). Cualquier `INSERT/UPDATE/DELETE/DROP/…` en cualquier subárbol se rechaza. Impone un `LIMIT`.
4. **Rol de base `app_readonly`, solo `SELECT`**: la reja dura. Aunque el LLM genere un `DELETE` y todas las capas anteriores fallen, la base lo rechaza. Defensa que no depende del código de la aplicación.
5. **Techo de filas + `statement_timeout`**: una consulta no puede tumbar la base ni traerse la tabla entera.

Respuesta por **SSE** (streaming token a token): primero se resuelven datos con el grafo, después se narra con el proveedor que quedó vivo.

### 2. Ingesta visual de remitos — Human-in-the-Loop

Cargar un remito de proveedor sacándole una foto ([`app/ingesta_visual/service.py`](app/ingesta_visual/service.py)). El flujo tiene dos mitades separadas a propósito:

- **`preparar_propuesta`**: foto → modelo multimodal extrae renglones → se cruzan contra el catálogo → se **marcan** los renglones dudosos (baja confianza, costo saltó, duplicado, texto sospechoso). **No escribe una sola fila.** Muestra qué precio quedaría en cada lista *antes* de confirmar.
- **`confirmar`**: escribe **solo lo que el humano aprobó**, y **un remito = una transacción** (o entran todos los renglones o no entra ninguno). El `unique index` sobre el hash de la imagen es el candado de concurrencia: dos confirmaciones simultáneas, una gana y la otra se lleva un `409`.

El umbral de confianza **marca** para revisión; no decide nada. La confianza autorreportada de un modelo está mal calibrada, así que se la usa como hint de UI, nunca como gate automático. El texto del remito viene de un tercero, así que se escanea con el mismo guard anti-injection —pero solo para marcar, nunca para banear: castigar a un usuario por lo que dice el papel de su proveedor sería un bug de producto.

Alcance actual: **solo el flujo de ENTRADA** (remito → alta/actualización de catálogo + movimiento de stock). La salida (pedido de cliente) se decide después.

---

## Testing y CI

**Backend — 9 suites de pytest**, incluidas la de aislamiento RLS entre tenants, el pipeline completo de ingesta (primitivas → propuesta → confirmar → router → multimodal), el asistente y la búsqueda híbrida.

**Frontend — vitest + Testing Library**: reducers de streaming, eventos de chat, schemas de dashboard y componentes (`MessageBubble`, `KpiCards`).

**CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) en cada PR y push a `main`:
- *Backend*: `ruff check` + `ruff format --check` + `pytest`, contra un Postgres `pgvector/pgvector:pg16` real (la misma imagen que dev), con cache del modelo de embeddings.
- *Frontend*: `oxlint` + `build` (`tsc -b && vite build` → typecheck completo + bundle).

> **Honestidad de estado:** los tests del frontend **existen pero todavía no están cableados a la CI** —el job de front corre lint y build, no `vitest`—. Es lo primero en la lista de pendientes de abajo. La CI ataja imports rotos y errores de tipo; no verifica todavía el comportamiento de las pantallas.

Versión pineada de `ruff` compartida entre `pyproject.toml` y `.pre-commit-config.yaml`: subir de versión es una decisión, no un efecto colateral de instalar en otra máquina.

---

## Correrlo local

Requisitos: [uv](https://docs.astral.sh/uv/), Docker, Node 24.

```bash
# 1. Base de datos (Postgres + pgvector, crea el rol app_user sin BYPASSRLS)
docker compose up -d db

# 2. Variables de entorno
cp env.example .env   # completar claves de Supabase / Groq / OpenAI

# 3. Backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
# API en http://localhost:8000 · docs en /docs (se apagan solas en prod)

# 4. Frontend
cd frontend && npm ci && npm run dev
```

Tests: `uv run pytest` (backend) · `cd frontend && npx vitest` (frontend).

---

## Estado y pendientes

Este README no vende humo. Lo que falta, en orden de prioridad:

- [ ] **Cablear los tests del front a la CI** (existen, no corren automáticamente).
- [ ] **Branch protection en `main`** que obligue a los checks verdes.
- [ ] **Deploy** con URL pública (hoy `docker-compose` corre solo local).
- [ ] El store de strikes anti-injection es in-memory → necesita Redis para más de un worker.

Fuera del alcance de esta fase (diseñado, no construido): ventas, compras, caja, cuenta corriente, integración AFIP, e importador de Paradox (Fase 2).

## Documentación

- [`docs/blueprint.md`](docs/blueprint.md) — arquitectura completa del ERP objetivo.
- [`docs/analisis-legacy.md`](docs/analisis-legacy.md) — análisis del sistema Delphi/Paradox viejo: la fuente del modelo de dominio.
- [`docs/gotchas.md`](docs/gotchas.md) — trampas conocidas del dominio y del stack.
