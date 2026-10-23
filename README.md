# HealthSync

Base ejecutable de un SaaS de reservas médicas: React + Tailwind, FastAPI y PostgreSQL 17. Incluye aislamiento por clínica, reserva transaccional, portal del paciente, consentimientos versionados, cifrado de contacto, auditoría y base del Vault de resultados.

**Es una base de desarrollo, no una certificación de cumplimiento ni un despliegue de producción.** Los documentos de demostración no son avisos legales válidos. La matriz de controles, límites y obligaciones de despliegue está en [Privacidad y seguridad](docs/privacy-security.md).

La propuesta de proveedores, ubicación de datos, pasos de despliegue y reportería está en [Plan de producción y reportería](docs/production-reporting-plan.md). Ese plan distingue lo implementado de las integraciones y módulos pendientes.

**Para empezar desde tu computador:** sigue [Desarrollo local y GitHub](docs/local-development.md). La dirección de alojamiento simplificada se describe en [Cloudflare + Supabase](docs/cloudflare-supabase-target.md); esa migración todavía no está implementada y el código actual se ejecuta con FastAPI.

## 1. Entregables

| Entregable | Archivo |
| --- | --- |
| Esquema completo, RLS, claves compuestas, GiST y auditoría | [database/001_schema.sql](database/001_schema.sql) |
| Arquitectura, árbol de carpetas y secuencia transaccional | [docs/architecture.md](docs/architecture.md) |
| Controlador HTTP y portal/privacidad/Vault | [backend/app/main.py](backend/app/main.py) |
| Motor de creación de reservas y eventos | [backend/app/booking.py](backend/app/booking.py) |
| Flujo React Guest → Registered y portal | [frontend/src/BookingFlow.tsx](frontend/src/BookingFlow.tsx) |
| Worker de recordatorios, correo, WhatsApp y Magic Link | [backend/app/worker.py](backend/app/worker.py) |

## 2. Instalar

Requisitos: Python 3.12+, `uv`, Node 22.12+ (probado con 24), npm y Docker con Compose. Utiliza el checkout existente; cada tarea cloud ya tiene aislamiento propio. No hace falta crear worktrees.

Desde la raíz:

```bash
python scripts/install.py
```

Instala dependencias con lockfiles, crea `.env` ignorado con claves aleatorias privadas, inicia PostgreSQL y aplica el esquema y catálogo ficticio a una base **nueva**. Las ejecuciones posteriores conservan la base y las claves. No regenera contraseñas ni sobrescribe `.env`. El bootstrap local no es un gestor de migraciones para producción; para cambios posteriores agrega migraciones numeradas y revísalas.

## 3. Arrancar

Los procesos deben iniciarse otra vez al restaurar una máquina. En terminales separadas:

```bash
# Raíz
docker compose up -d --wait db

# Terminal API
cd backend
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers

# Terminal web, desde la raíz
cd frontend
npm run dev
```

Vite sirve el frontend en el puerto 5173 y redirige `/v1` a la API. La clínica demo usa el huso `America/Santiago`; el servidor intercambia instantes con offset y guarda UTC. El catálogo está disponible en `/v1/10000000-0000-4000-8000-000000000001/catalog`.

Comprueba con peticiones locales: `/health` debe devolver `{"status":"ok"}`, el catálogo debe contener una consulta y `/availability` debe devolver horarios para una fecha dentro de 180 días. Una reserva necesita un `Idempotency-Key` UUID v4 y los IDs actuales de los documentos obtenidos del catálogo. Las pruebas de integración incluyen ejemplos completos. No uses datos de pacientes reales en este entorno.

## 4. Validar

```bash
cd backend
uv run --frozen python -m pytest -q
uv run --frozen ruff check app tests ../scripts

# Desde la raíz
cd frontend
npm test
npm run build
```

Las pruebas crean una **base temporal propia** en el PostgreSQL local y la eliminan al terminar; no borran la base de desarrollo. Ejercitan conexiones con el rol restringido, no SQLite ni mocks de PostgreSQL. Los proveedores externos se simulan donde corresponde: las pruebas no demuestran entrega real de correos, WhatsApp ni funcionamiento de un bucket de producción.

Con API y Vite iniciados, `backend/.venv/bin/python scripts/smoke.py` desde la raíz comprueba el flujo HTTP completo, el proxy y los conflictos. Crea una reserva ficticia en la clínica demo y comprueba reintentos. El script rechaza un catálogo sin los marcadores de demostración.

## 5. Activar cuentas y notificaciones

Para probar cuentas con un proyecto Supabase propio:

1. Configura Auth con claves asimétricas ES256/RS256, confirmación de correo obligatoria, Site URL del frontend y redirect allowlist exacta. Configura SMTP de producción y sus límites.
2. Añade `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` al `.env` del backend. Añade los equivalentes `VITE_SUPABASE_URL` y `VITE_SUPABASE_PUBLISHABLE_KEY` en `frontend/.env.local`. Usa **solo** la clave publicable en el navegador.
3. Reinicia la API y Vite. El checkbox de cuenta se habilita cuando ambos lados están configurados.
4. Ejecuta el worker por clínica:

```bash
cd backend
.venv/bin/python -m app.worker --tenant 10000000-0000-4000-8000-000000000001
```

La reserva inserta una inscripción pendiente y un evento outbox. El worker llama a Supabase OTP con `create_user=true`; el paciente verifica el correo. El portal entonces reclama **solo** perfiles con opt-in pendiente, correo verificado y plazo vigente de 24 horas. No se vincula por un email escrito en un formulario ni por un ID de reserva. No hay llamada externa dentro de la transacción de reserva: creación/vinculación de cuenta es un proceso eventual y reintentable.

Para email operativo/WhatsApp configura `NOTIFICATION_WEBHOOK_URL` (HTTPS) y `NOTIFICATION_WEBHOOK_TOKEN` con un adaptador propio. Debe aceptar el contrato JSON de `worker.py`, deduplicar por `Idempotency-Key`, devolver 2xx solo al aceptar la entrega y usar plantillas transaccionales aprobadas. El worker revalida consentimiento, paciente activo y versión de reserva; reintenta hasta 10 veces cada cinco minutos. Los eventos agotados necesitan monitorización y recuperación operativa. Supabase OTP tiene sus propios límites y no promete deduplicación de Magic Links tras un fallo de confirmación de entrega.

Sin estos proveedores, la reserva como invitado funciona y los eventos quedan pendientes; **no se afirma que se haya enviado un mensaje**. Las notificaciones contienen un aviso genérico, sin especialidad ni resultado médico. Un invitado sin cuenta gestiona sus cambios con la clínica; no se expone un enlace público de gestión sin verificación.

## 6. Supabase y producción

Aplica `001_schema.sql` con un propietario de migraciones y asigna una contraseña segura a `healthsync_app` por un canal administrativo. Conecta FastAPI con ese rol, nunca con `postgres`, el propietario o `service_role`. No expongas el esquema `healthsync` mediante PostgREST ni concedas acceso a `anon`/`authenticated`: la autorización de paciente y personal se aplica en FastAPI y RLS limita cada transacción al tenant.

El SQL es compatible con PostgreSQL de Supabase (`btree_gist`); la extensión y la creación de roles requieren los permisos administrativos del proyecto. Para conexiones administradas configura TLS verificado (`sslmode=verify-full` y CA correspondiente). El helper Docker se limita a desarrollo local. Los detalles del Vault de fase 2 y la configuración de almacenamiento están en [Arquitectura](docs/architecture.md).
