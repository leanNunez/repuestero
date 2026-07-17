# Gotchas de Repuestero

Trampas reales que nos mordieron (o casi) construyendo el sistema, con el fix. Sirve para no
tropezar dos veces y como checklist al montar el entorno en otra máquina o en CI.

---

## Entorno

### El Python del sistema no tiene pip ni ensurepip
`python3 -m venv` falla con *"ensurepip is not available"* (falta `python3.12-venv`, que pide
sudo). **Fix**: se usa `uv` (binario user-local, sin sudo): `curl -LsSf https://astral.sh/uv/install.sh | sh`,
después `uv venv` + `uv pip install -e ".[dev]"`. `uv` queda en `~/.local/bin`.

### Los tests necesitan Postgres real, no SQLite
RLS, `tsvector`, `pgvector` y `pg_trgm` son features del motor: no existen en SQLite. Testear
sin Postgres es testear humo. **Fix**: `docker compose up -d db` antes de `pytest`.

---

## Multi-tenant / RLS

### `postgres` es SUPERUSER y bypassea RLS
El rol `postgres` (owner/superuser) NO está sujeto a RLS, ni siquiera con `force row level
security`. Es a propósito: el importador y el seed lo usan (`MIGRATIONS_DATABASE_URL`) para crear
orgs y sembrar datos sin pelear con las políticas. La app corre como `app_user` (NOSUPERUSER, sin
BYPASSRLS) = el rol realmente sujeto a RLS. **No confundir**: si un test "ve todo", fijate con qué
rol te conectaste.

### Los DEFAULT PRIVILEGES son POR BASE
`scripts/init_db.sql` corre `alter default privileges ... in schema public` solo sobre la base
`repuestos`. Una base de tests nueva NO los hereda → `app_user` no tendría permisos DML sobre las
tablas que crea Alembic. **Fix**: en el fixture de tests se replican los `ALTER DEFAULT PRIVILEGES`
ANTES de migrar (ver `tests/conftest.py::migrated_db`).

### `with check` es tan importante como `using`
`using` controla qué filas VES; `with check` controla qué filas podés ESCRIBIR. Sin `with check`,
un tenant podría INSERTAR filas dentro de otro aunque no pudiera leerlas.

### La vista `stock` necesita `security_invoker = true`
Por defecto una vista corre con permisos de su OWNER → saltearía el RLS de `stock_movimientos` y
un tenant vería el stock de otro. La vista se crea con `security_invoker = true` para que corra
como quien la consulta.

---

## Datos / seed

### El importador valida — no le metas basura
Todo entra por la capa `service`, que valida. Un seed que no respete esto se RECHAZA:
- **CUIT**: formato `XX-XXXXXXXX-X` **y** dígito verificador módulo 11 (pesos `5,4,3,2,7,6,5,4,3,2`).
- **Stock**: `motivo` ∈ {inicial, compra, venta, ajuste, transferencia}; `cantidad != 0`.
- **Compatibilidad**: `origen` ∈ {manual, catalogo_proveedor, extraido_ia}; si es `extraido_ia`,
  `confirmado` DEBE ser `false` (lo que infiere la IA lo confirma un humano).

### El seed se genera, no se tipea a mano
`seeds/generar_demo.py` produce los CSVs con FKs consistentes por construcción y CUITs/precios
calculados. Escribir 120 filas cruzadas a mano garantiza romper una FK.

---

## Auth

### Sin proyecto Supabase, se emite un JWT HS256 propio
`security.py` soporta HS256 (secreto simétrico) además de JWKS. Para probar sin Supabase se firma
un JWT con `SUPABASE_JWT_SECRET`: claims `sub` (user_id), `aud="authenticated"`, `exp` futuro.
Recorre el mismo camino de código que producción; solo no ejercita el JWKS de Supabase.

### Sin fila en `miembros`, el circuito da 403
El `org_id` NO viene del JWT — se resuelve leyendo `miembros` por `user_id`. Un usuario
autenticado pero sin membresía recibe 403. Al importar, usar `--miembro <user_id>`.

---

## Búsqueda / embeddings

### El modelo del plan no estaba en fastembed
`intfloat/multilingual-e5-small` NO está en esta versión de fastembed. **Fix**: se usa
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384d, multilingüe). Es SIMÉTRICO →
sin prefijos `query:`/`passage:` (esos son de la familia e5). La dimensión 384 quedó igual, no
cambió la migración. Verificá con `TextEmbedding.list_supported_models()`.

### `websearch_to_tsquery` usa AND — inútil para lenguaje natural
"necesito frenar el auto" no matchea ningún artículo por texto (exige TODOS los términos), así que
la búsqueda caía solo en el vector. **Fix**: `replace(websearch_to_tsquery(...)::text, ' & ', ' | ')::tsquery`
para modo OR sobre los lexemas YA parseados y stemmed por Postgres (seguro, sin inyección).

### Un entrypoint ORM standalone necesita importar el registry
`reindex.py` fallaba con `NoReferencedTableError` (FK `articulos.org_id → organizaciones`) porque
solo importaba `catalogo.models`, no `core.models`. **Fix**: `import app.core.registry` (importa
TODOS los modelos → `Base.metadata` completo). Vale para cualquier CLI que use el ORM sin pasar por
Alembic o por el importador.

### pgvector en SQL crudo: pasar el vector como literal
No hace falta registrar adaptadores: se formatea el vector como `'[0.1,0.2,...]'` y se castea con
`cast(:qvec as vector)` en el SQL.

### Los embeddings NO se generan en el hot path
Cargar el modelo (~120MB) y embeber es caro. NO se hace en `crear_articulo`; se corre
`python -m app.catalogo.reindex` después de importar. Carga perezosa con `lru_cache`.

---

## Migraciones / Alembic

### Excluir vistas y columnas generadas del autogenerate
`stock` es una vista mapeada como entidad; sin excluirla, el autogenerate intentaría un
`create_table("stock")`. Se marca con `info={"is_view": True}` y `env.py::include_object` la
filtra. Las columnas generadas (`busqueda` tsvector) se mapean con `Computed(...)` para que el ORM
y la migración queden en sync.

### `path_separator = os` en alembic.ini
Alembic 1.16+ tira `DeprecationWarning` sin `path_separator`. Se agregó a `alembic.ini`.

---

## Pendiente / a resolver (para el asistente conversacional — próximo slice)

- **Groq necesita API key.** A diferencia de todo lo anterior, el asistente (LangGraph + Groq) NO
  se puede verificar end-to-end sin una `GROQ_API_KEY`. Definir: ¿hay key para dev, o se stubbea
  el LLM para la demo/tests? Es el primer blocker del slice.
- **NL2SQL read-only debe correr con un rol que NO pueda escribir** — no reusar `app_user` con DML
  para las queries que arma el LLM. Idea: rol `app_readonly` (solo SELECT) + RLS, así ni un prompt
  injection puede mutar datos. (A diseñar en el plan del asistente.)
