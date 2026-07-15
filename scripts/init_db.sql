-- Bootstrap del Postgres local (solo dev; en Supabase esto se hace una vez a mano).
--
-- La clave del corazón del multi-tenant: la app NO se conecta como owner.
-- Un rol SUPERUSER o el owner de la tabla puede saltarse RLS. Por eso la app
-- usa app_user: NOSUPERUSER, sin BYPASSRLS, y NO es owner de nada.

create role app_user with login password 'app_password'
    nosuperuser nocreatedb nocreaterole noinherit;

grant usage on schema public to app_user;

-- Las tablas las crea Alembic (rol postgres). Estos default privileges hacen que
-- app_user reciba permisos DML sobre todo lo que postgres cree de ahí en más,
-- sin tener que acordarse de un GRANT en cada migración.
alter default privileges for role postgres in schema public
    grant select, insert, update, delete on tables to app_user;

alter default privileges for role postgres in schema public
    grant usage, select on sequences to app_user;

-- Rol read-only para el asistente NL2SQL. El SQL que genera el LLM corre con ESTE rol:
-- NOSUPERUSER, sin BYPASSRLS y con SOLO SELECT. Aunque el LLM genere un DELETE, la base lo
-- rechaza a nivel motor. Sigue sujeto a RLS → el GUC de tenant lo encierra en su organización.
create role app_readonly with login password 'readonly_password'
    nosuperuser nocreatedb nocreaterole noinherit;

grant usage on schema public to app_readonly;

alter default privileges for role postgres in schema public
    grant select on tables to app_readonly;
