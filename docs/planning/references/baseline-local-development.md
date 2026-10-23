# Trabajar en tu computador y guardar el código en GitHub

Medical Appointment System, desarrollado por Tresuryx SpA, tiene React/Tailwind, FastAPI y PostgreSQL local. No necesitas contratar hosting ni conectar cuentas externas para probar la reserva como invitado con datos ficticios.

## Requisitos

- Git.
- Python 3.12 o superior; en Windows activa la opción para añadir Python al PATH.
- [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Node.js 24 LTS y npm.
- Docker Desktop iniciado, con Docker Compose disponible.

Los comandos siguientes sirven en una terminal desde el checkout; en Windows puedes usar PowerShell. Se han ejecutado en Linux; no se afirma validación nativa en Windows/macOS.

## Clonar e instalar

```text
git clone https://github.com/clefaraco/Reserve_System.git
cd Reserve_System
python scripts/install.py
```

En macOS/Linux usa `python3 scripts/install.py` si tu instalación no tiene el comando `python`. El instalador usa rutas relativas, `uv` para localizar el intérprete del proyecto y lockfiles. Genera `.env` privado solo si no existe; no lo sobrescribe. No aplica los textos legales demo a una base productiva.

## Ver la aplicación

En una primera terminal, desde la raíz:

```text
cd backend
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

En una segunda terminal, desde la raíz:

```text
cd frontend
npm run dev
```

En el navegador **de tu computador**, abre `http://localhost:5173`. No abras `frontend/index.html` como archivo: la aplicación requiere Vite y la API. Los servidores solo escuchan en tu equipo, no se publican en Internet.

Puedes elegir consulta, profesional y horario y reservar con datos ficticios. El checkbox de cuenta se habilita únicamente cuando se configure Supabase Auth en frontend y backend. El espacio de equipo tiene agenda, recepción y resumen operativo cuando se asignan perfiles y alcances. Reporterías avanzadas, edición completa de configuración, pagos, coberturas, telemedicina, carga de PDFs y entrega real de mensajes siguen pendientes, según `PRODUCT_BLUEPRINT.md`.

Docker ya queda iniciado por el instalador. Tras reiniciar tu computador, arranca Docker Desktop y ejecuta desde la raíz:

```text
docker compose up -d --wait db
```

Si un puerto está ocupado, cierra solamente el proceso propio que lo usa o configura el puerto y su proxy de manera coherente. No ejecutes `docker compose down -v` salvo que quieras eliminar expresamente la base local.

## Comprobar cambios

Desde `backend`:

```text
uv run --frozen python -m pytest -q
uv run --frozen ruff check app tests ../scripts
```

Desde `frontend`:

```text
npm test
npm run build
```

Las pruebas de integración crean y eliminan su propia base temporal en el PostgreSQL local. Para comprobar el flujo HTTP con ambos servidores iniciados, desde la raíz:

```text
uv run --frozen --project backend python scripts/smoke.py
```

Ese smoke test crea una reserva ficticia en la clínica demo; no debe ejecutarse sobre pacientes reales.

## Flujo de GitHub

GitHub guarda código, SQL, lockfiles e instrucciones. No aloja la base de datos ni hace que la aplicación quede publicada automáticamente.

```text
git switch -c feature/mi-cambio
git status
git add ruta/al/archivo
git diff --cached
git commit -m "Describe el cambio"
git push -u origin feature/mi-cambio
```

Revisa cada commit y abre un Pull Request. Antes de una sesión nueva actualiza tu checkout con los cambios remotos; evita trabajar sobre dos copias divergentes sin sincronizarlas.

`.env`, claves, `node_modules`, entornos Python, datos de PostgreSQL y resultados médicos no deben entrar a GitHub. Están excluidos los archivos locales habituales, pero `gitignore` no detecta por sí solo un secreto pegado en código: revisa el contenido antes de subirlo. Usa archivos `.env.example` exclusivamente con nombres y ejemplos sin credenciales. Si se filtra un secreto, hay que revocarlo; borrarlo del siguiente commit no lo elimina del historial.
