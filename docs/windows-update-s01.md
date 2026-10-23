# Revisar S00/S01 en Windows conservando datos

Estos pasos actualizan tu carpeta existente. La rama es de revisión; no está fusionada en `main`. Los comandos fueron comprobados en Linux; la ejecución nativa en Windows sigue **no ejecutada**.

1. Cierra las dos terminales que ejecutan API/frontend con Ctrl+C. Mantén Docker Desktop iniciado. Abre PowerShell:

```powershell
cd C:\Users\Clemente\Reserve_System
git status --short
git branch --show-current
```

Si aparecen cambios locales, consérvalos antes de cambiar de rama:

```powershell
git stash push --include-untracked -m "Trabajo local antes de revisar S00 S01"
git stash list
```

Esto no guarda `.env` ni otros ignorados; permanecen en tu carpeta. No uses `reset --hard`, `clean`, ni descartes archivos. No apliques automáticamente el stash a la rama nueva: sus posibles conflictos requieren revisión. Puedes volver a tu rama anterior y ejecutar `git stash apply` después, conservando además el stash.

2. Haz una copia privada de la base antes de migrar:

```powershell
New-Item -ItemType Directory -Force .local\backups | Out-Null
docker compose up -d --wait db
docker compose exec -T db pg_dump -U postgres -d healthsync -Fc --file=/tmp/mas-pre-s01.dump
docker compose cp db:/tmp/mas-pre-s01.dump .local/backups/mas-pre-s01.dump
Copy-Item .env .local/backups/env-pre-s01.private
```

No compartas ni subas esas copias. El dump contiene datos y necesita tus claves originales. No se afirma que copiarlo pruebe una restauración: el ensayo de recuperación está en S04. Puedes fechar los nombres para no reemplazar copias anteriores.

3. Trae la rama y crea una rama local de revisión:

```powershell
git fetch origin
git switch -c review/s00-s01 --track origin/feature/s00-s01-team-access
python scripts/install.py
```

Si `review/s00-s01` ya existe, usa `git switch review/s00-s01` y, con árbol limpio, `git pull --ff-only`. El instalador conserva `.env` y el volumen, aplica solo la migración nueva 005 y verifica checksums. Si falla una migración, detén la actualización y conserva el mensaje sin claves; no edites SQL aplicado ni borres la base.

4. Arranca como antes. Primera terminal:

```powershell
cd C:\Users\Clemente\Reserve_System\backend
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

Segunda terminal:

```powershell
cd C:\Users\Clemente\Reserve_System\frontend
npm run dev
```

Abre `http://localhost:5173` **en tu PC**. La reserva ficticia sigue funcionando. El acceso del equipo permanece cerrado si Auth/MFA no están configurados; no aparecerá un administrador demo. Para revisar las pantallas ahora, consulta las imágenes ficticias en [demostración](demos/README.md) y las pruebas. Configurar identidades reales sigue el procedimiento de [equipo](team-access.md) con autorización.

5. Comprueba desde la raíz `python scripts/planning.py --check`. Pruebas backend desde `backend`: `uv run --frozen pytest -q`; crean una base temporal aparte y no eliminan tu base. Frontend: `npm test`, `npm run build`.

Para volver al código anterior: detener servidores, conservar cualquier cambio nuevo, `git switch main` y reinstalar dependencias de esa versión. **No revertir ni borrar tablas/datos de 005**: volver de código no autoriza una restauración destructiva ni elimina historia. La versión anterior no aplica los controles nuevos de equipo/MFA; no usarla como alternativa para un piloto alojado. Una recuperación de datos requiere restauración aislada revisada (S04), no `docker compose down -v`.
