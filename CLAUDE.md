# Repuestero — ERP AI-native multi-tenant para casas de repuestos

## Objetivo ACTUAL
Estamos en **Fase 0 (fundaciones)**. NO construir el ERP completo.
La arquitectura completa está en `docs/blueprint.md` — leerlo antes de planificar.
Trabajar fase por fase. No adelantar ventas/compras/caja/cta cte/AFIP.

## Stack
- Backend: FastAPI + SQLAlchemy 2.0 + Alembic
- Datos: Supabase (Postgres + pgvector + Auth + RLS)
- IA (fases siguientes): LangGraph + Groq
- Frontend: React 19 + TanStack Router/Query + Zustand + Tailwind + shadcn/ui

## Reglas NO negociables (son los "pecados" del sistema viejo que arreglamos)
- Multi-tenant: TODA tabla lleva `org_id`. RLS por `org_id` del JWT.
- Plata: `numeric`, NUNCA float.
- Cuenta corriente: movimientos append-only, saldo como VISTA. Nunca columna saldo mutable.
- Numeración: `identity`/secuencias/`SELECT ... FOR UPDATE`. NUNCA `Max(id)+1`.
- IVA explícito por renglón (no columnas opacas).
- Los routers NO tocan la DB directo → capa `service`.
- Cambios de esquema SOLO por migración Alembic.

## Estilo
- Tipado con Pydantic. Tests con pytest. Commits chicos y descriptivos.
- Monolito modular, package-by-feature (catalogo/, inventario/, ...).
## Referencia de dominio
`docs/analisis-legacy.md` = análisis del sistema Delphi/Paradox viejo.
Es la fuente del modelo de datos y los flujos de negocio, y el mapa para el
importador de Paradox (Fase 2). NO es el sistema a construir — es de dónde
copiamos el dominio. Consultar cuando haya dudas sobre entidades o flujos.