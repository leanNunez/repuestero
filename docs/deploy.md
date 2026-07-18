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
      `0004` (head), 15 tablas.
- [ ] **Rotar el password del rol `postgres`** (se pegó en un chat). Supabase → Database → Reset
      database password. Actualizar la `MIGRATIONS_DATABASE_URL` con el nuevo.
- [ ] **Token de HF Inference** creado (huggingface.co/settings/tokens → Fine-grained → sólo
      "Make calls to Inference Providers"). Es el `HF_TOKEN`.

---

## 1. Backend → Render

El repo ya trae `render.yaml` (Blueprint) y `Dockerfile`. En Render: **New → Blueprint**, apuntá al
repo y detecta el `render.yaml`. Crea el servicio `repuestero-api` (Docker, plan free).

### Secrets (Render → el servicio → Environment)

Las variables con valor fijo ya vienen en `render.yaml` (`ENV=production`,
`EMBEDDINGS_BACKEND=remote`). Las `sync: false` se cargan a mano. Espejá los schemes de tu `.env`
local; la DB es **síncrona** → pooler **session mode, puerto 5432** (NO el 6543).

| Clave | Valor | Rol / Nota |
|---|---|---|
| `DATABASE_URL` | `...pooler...:5432/postgres` | rol **app_user** (DML sujeto a RLS) |
| `DATABASE_READONLY_URL` | `...:5432/postgres` | rol **app_readonly** (SQL del asistente) |
| `MIGRATIONS_DATABASE_URL` | `...:5432/postgres` | rol **owner/postgres** (corre `alembic upgrade head` al arrancar) |
| `HF_TOKEN` | `hf_...` | **embeddings remotos** — sin esto el backend arranca y se cae |
| `SUPABASE_URL` | `https://<proj>.supabase.co` | |
| `SUPABASE_JWKS_URL` | JWKS de Supabase | validación de JWT |
| `GROQ_API_KEY` | `gsk_...` | asistente NL2SQL |
| `OPENAI_API_KEY` | `sk-...` | ingesta visual (multimodal) |
| `ALLOWED_ORIGINS` | URL de Vercel, **sin barra final** | CORS. Se completa en el paso 3. |

> Ya vienen del `render.yaml` (no las toques salvo que quieras): `ENV=production` (**no `prod`**),
> `EMBEDDINGS_BACKEND=remote`.

### Verificar

- `https://<servicio>.onrender.com/health` → `{"status":"ok"}`
- `/docs` debe dar **404** (Swagger apagado) → confirma que `ENV=production` tomó.

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
  (~50s). Aceptable para una demo.
- **Latencia de embeddings:** cada búsqueda semántica y cada arranque (el `startup` precomputa los
  embeddings de defensa) hacen llamadas HTTP a HF. Suma unos cientos de ms por búsqueda. El free de
  HF da 100K créditos/mes — de sobra para una demo.
- **Migraciones al boot:** el `CMD` corre `alembic upgrade head` en cada arranque (idempotente, ya
  en `0004`), pero necesita `MIGRATIONS_DATABASE_URL` válida o el contenedor no levanta.
- **Backend local con Docker:** la imagen no baquea el modelo (deploy remoto). Si algún día corrés
  la imagen con `EMBEDDINGS_BACKEND=local`, el primer request baja el modelo (~120MB) una vez.
