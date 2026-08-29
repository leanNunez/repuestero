# Deploy de Repuestero

Todo en tiers **gratuitos**:

```
Frontend (Vercel)  ─HTTPS→  Backend (Render, Docker, free)  ─→  Supabase (Postgres + pgvector + Auth)
                                     │
                                     └─ embeddings ─→  HF Inference API (free tier)
```

## Por qué esta arquitectura

El backend usa el modelo de embeddings `paraphrase-multilingual-MiniLM-L12-v2`. Cargarlo
**local** (fastembed) come ~615MB de RAM → el backend llega a ~734MB → **no entra** en los 512MB
del free de Render (OOM al arrancar, porque `app/main.py` carga el modelo en el `startup`).

Solución (Camino B): **`EMBEDDINGS_BACKEND=remote`**. Los embeddings se generan vía la **HF
Inference API** (llamada HTTP), que sirve el MISMO modelo. El proceso nunca carga fastembed → baja
a **~140MB** → entra en el free con 73% de aire. Verificado que los vectores remotos son idénticos
a los locales (coseno 1.0), así que **la base no se toca ni se reindexa**.

> Ojo: "HF Inference API" (un endpoint que llamás por HTTP) es un producto DISTINTO de "HF Spaces"
> (hosting de apps). Spaces Docker pasó a ser pago; la Inference API sigue con free tier (100K/mes).
> Por eso el HOSTING va en Render y sólo los EMBEDDINGS pegan a HF.

---

## 0. Prerrequisitos

- [x] Supabase bootstrapeado: roles `app_user`/`app_readonly`, extensión `vector`, migraciones en
      `0013` (head).
- [ ] **Rotar el password del rol `postgres`** (se pegó en un chat). Supabase → Database → Reset
      database password. Actualizar la `MIGRATIONS_DATABASE_URL` con el nuevo.
- [ ] **Token de HF Inference** creado (huggingface.co/settings/tokens → Fine-grained → sólo
      "Make calls to Inference Providers"). Es el `HF_TOKEN`.

---

## 1. Backend → Render

El repo ya trae `render.yaml` (Blueprint) y `Dockerfile`. En Render: **New → Blueprint**, apuntá al
repo y detecta el `render.yaml`. Crea el servicio `repuestero-api` (Docker, plan free).

`render.yaml` trae `autoDeploy: false` a propósito: **el deploy lo dispara GitHub Actions**, nunca
un push directo a Render. Ver "Migrar y desplegar" más abajo — es un paso más, pero es lo que evita
que el contenedor migre en cada arranque (ver Gotchas: eso fue lo que convirtió una Supabase
pausada en una caída total, antes de este cambio).

### Secrets (Render → el servicio → Environment)

Las variables con valor fijo ya vienen en `render.yaml` (`ENV=production`,
`EMBEDDINGS_BACKEND=remote`). Las `sync: false` se cargan a mano. Espejá los schemes de tu `.env`
local; la DB es **síncrona** → pooler **session mode, puerto 5432** (NO el 6543).

| Clave | Valor | Rol / Nota |
|---|---|---|
| `DATABASE_URL` | `...pooler...:5432/postgres` | rol **app_user** (DML sujeto a RLS) |
| `DATABASE_READONLY_URL` | `...:5432/postgres` | rol **app_readonly** (SQL del asistente) |
| `MIGRATIONS_DATABASE_URL` | `...:5432/postgres` | rol **owner/postgres**. El proceso web YA NO la usa para migrar (eso corre en CI, ver abajo); queda acá solo para scripts de operación puntuales (`app/catalogo/reindex.py`, `app/importador/__main__.py`) si alguna vez se corren contra Render. |
| `HF_TOKEN` | `hf_...` | **embeddings remotos** — sin esto el backend arranca igual (la carga es perezosa), pero el asistente falla al primer uso |
| `SUPABASE_URL` | `https://<proj>.supabase.co` | |
| `SUPABASE_JWKS_URL` | JWKS de Supabase | validación de JWT. Sin esto (y sin `SUPABASE_JWT_SECRET`) el backend arranca igual, pero todo endpoint autenticado responde 503 |
| `GROQ_API_KEY` | `gsk_...` | asistente NL2SQL |
| `OPENAI_API_KEY` | `sk-...` | ingesta visual (multimodal) |
| `ALLOWED_ORIGINS` | URL de Vercel, **sin barra final** | CORS. Se completa en el paso 3. |

> Ya vienen del `render.yaml` (no las toques salvo que quieras): `ENV=production` (**no `prod`**),
> `EMBEDDINGS_BACKEND=remote`, `autoDeploy: false`.

### Verificar

- `https://<servicio>.onrender.com/health` → `{"status":"ok"}` (no toca la base — puede dar 200
  aunque Supabase esté pausada).
- `https://<servicio>.onrender.com/health/db` → `{"status":"ok"}` si además la base responde;
  `503` si no (ese es el diagnóstico real de "¿está pausada Supabase?").
- `/docs` debe dar **404** (Swagger apagado) → confirma que `ENV=production` tomó.

### Migrar y desplegar (GitHub Actions, no Render)

`.github/workflows/ci.yml` trae dos jobs que solo corren en push a `main`, y solo si
`backend`+`frontend` (el resto de la suite) pasaron:

1. **`migrate`** — corre `alembic upgrade head` contra `MIGRATIONS_DATABASE_URL` (secret del
   **repo de GitHub**, Settings → Secrets and variables → Actions — no confundir con el de
   Render). Mismo valor que el de Render (rol owner, pooler puerto 5432): los runners de GitHub
   son IPv4-only y la conexión directa de Supabase es IPv6-only, así que tiene que ser el pooler.
2. **`deploy`** — si migró bien, dispara `RENDER_DEPLOY_HOOK_URL` (otro secret del repo de
   GitHub: Render → el servicio → Settings → Deploy Hook → copiar la URL).

Si `migrate` falla, `deploy` no corre — Render nunca despliega código con una migración a medias.
Fallback manual si CI no está disponible: `uv run alembic upgrade head` desde tu máquina (mismo
`MIGRATIONS_DATABASE_URL`), y después disparar el hook a mano con `curl`.

---

## 2. Frontend → Vercel

- Import del repo, **Root Directory = `frontend/`**. Framework: Vite.
- Env vars (Vercel → Settings → Environment Variables):

| Clave | Valor |
|---|---|
| `VITE_API_URL` | la URL del backend en Render, sin barra final |
| `VITE_SUPABASE_URL` | `https://<proj>.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | anon key (es pública, segura para el front) |

---

## 3. Cerrar el círculo (CORS)

1. Copiar la URL final de Vercel (`https://<app>.vercel.app`).
2. Pegarla en `ALLOWED_ORIGINS` del servicio de Render (**sin barra final**) → redeploy.
3. Abrir el front → login con Supabase → probar catálogo + asistente (Repu). Sin errores de CORS
   en consola = circuito completo vivo.

---

## Gotchas

- **Render free se duerme** tras ~15 min sin tráfico; el primer request despierta con cold start
  (~50s). Con **750 instance-hours/mes por workspace**: si se agotan, Render suspende TODOS los
  servicios free hasta el mes siguiente — un ping 24/7 son 744h de 750, sin margen real. El
  keep-alive va por ventana horaria (ver el plan de "siempre arriba" para los números).
- **Service-initiated traffic:** Render puede suspender un servicio free que inicie mucho tráfico
  saliente — y nombra explícitamente "accessing an external database" e "invoking external APIs".
  Repuestero hace las dos en cada request. El keep-alive de `/health` no toca la base a propósito.
- **Latencia de embeddings:** cada búsqueda semántica hace una llamada HTTP a HF (backend remoto).
  Ya NO pasa en el arranque: la primera consulta al asistente paga esa llamada la primera vez
  (`app/asistente/seguridad.py::_asegurar_embeddings`), no cada cold start. El free de HF da 100K
  créditos/mes — de sobra para una demo.
- **Migraciones:** ya NO corren en el arranque del contenedor (ver "Migrar y desplegar" arriba).
  Antes el `CMD` corría `alembic upgrade head && uvicorn`: con la base pausada, alembic fallaba, el
  `&&` cortaba y el proceso nunca levantaba — una pausa recuperable se convertía en caída total.
- **Base caída no es lo mismo que backend caído:** `/health` no toca Postgres (siempre 200 si el
  proceso está vivo); `/health/db` sí, y da 503 si la base no responde. Un `OperationalError` en
  cualquier endpoint cae en el handler global de `app/main.py` → 503, nunca 500 ni 401.
- **Backend local con Docker:** la imagen no baquea el modelo (deploy remoto). Si algún día corrés
  la imagen con `EMBEDDINGS_BACKEND=local`, el primer request baja el modelo (~120MB) una vez.
