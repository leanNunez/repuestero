-- Bootstrap de Repuestero en Supabase. Correr UNA vez en el SQL Editor (como rol `postgres`)
-- ANTES de las migraciones. Espeja scripts/init_db.sql (que es para el Postgres local de dev).
--
-- Por qué a mano: Supabase no trae los roles de la app. La clave del multi-tenant es que la app
-- NO se conecta como owner (un owner/superuser se saltea RLS). Se conecta como app_user:
-- NOSUPERUSER, sin BYPASSRLS, y que no es owner de nada.
--
-- IMPORTANTE: cambiá 'CAMBIAME_*' por passwords fuertes y usalos en las connection strings
-- (DATABASE_URL con app_user, DATABASE_READONLY_URL con app_readonly).

-- pgvector: el catálogo lo necesita (la migración 0001 crea columnas vector).
create extension if not exists vector;

-- Rol de la app: DML sobre el negocio, sujeto a RLS.
create role app_user with login password 'CAMBIAME_APP'
    nosuperuser nocreatedb nocreaterole noinherit;
grant usage on schema public to app_user;

-- Default privileges: app_user recibe DML sobre todo lo que `postgres` cree de acá en más
-- (las tablas las crea Alembic conectado como postgres). Sin esto, cada migración necesitaría
-- GRANTs manuales.
alter default privileges for role postgres in schema public
    grant select, insert, update, delete on tables to app_user;
alter default privileges for role postgres in schema public
    grant usage, select on sequences to app_user;

-- Rol read-only del asistente NL2SQL. El SQL que genera el LLM corre con ESTE rol: sólo SELECT,
-- sin BYPASSRLS. Aunque el LLM genere un DELETE, el motor lo rechaza. Sigue sujeto a RLS.
create role app_readonly with login password 'CAMBIAME_RO'
    nosuperuser nocreatedb nocreaterole noinherit;
grant usage on schema public to app_readonly;
alter default privileges for role postgres in schema public
    grant select on tables to app_readonly;
