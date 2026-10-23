# Evidencia de entrega S00/S01 · 23 de octubre de 2026

Código revisado desde `2a9144bda99fb565ca157c7c42cf536c16f83deb`, rama `feature/s00-s01-team-access`. Registro de la revisión validada en el commit de entrega y su actualización de publicación. **S00 comprobada; S01 no terminada**, por falta de configuración y validación externa autorizada de Auth/OTP/MFA/correo. No hay merge, despliegue, cobros ni invitaciones reales.

## Ejecución

- **Pasa:** 64 pruebas backend en PostgreSQL temporal nuevo, con rol runtime sin propiedad/BYPASSRLS. Incluyen las 31 anteriores y pruebas nuevas de equipo, concurrencia, Auth, entrega, planificación y compatibilidad criptográfica.
- **Pasa:** 11 pruebas frontend (Vitest), compilación TypeScript y build Vite.
- **Pasa:** Chromium real 1280 y 360 px: foco inicial/restaurado, Tab/Shift+Tab, Escape sin modificación, confirmación explícita, cero diálogos de sistema, sin desbordamiento ni errores JS. API de esta demostración **simulada**, egress externo bloqueado. [Capturas y resultados](../demos/README.md).
- **Pasa:** smoke HTTP con API y Vite reales: readiness, catálogo, disponibilidad, reserva ficticia, reintento idempotente, conflicto de horario y proxy/frontend. Primer intento llegó a API pero falló porque Vite 5173 estaba detenido; se inició y se repitió con resultado completo pasa.
- **Pasa:** ruff, `git diff --check`, generador de planificación y comprobación de vistas.
- **Pasa:** migración 005 aplicada incrementalmente a base local existente; pruebas temporales verifican conservación de pacientes/reservas/auditoría y repetición/checksum de migraciones. SQL 001–004 intacto, sin reset ni modificación de `.env`/claves.
- **Pasa con alcance limitado:** npm audit de dependencias de producción: cero avisos. pip-audit 2.10.1 sobre export frozen completo de runtime: inicialmente 7 entradas (4 IDs únicos) en cryptography 46.0.7; actualizado a **50.0.2**, nueva auditoría sin avisos conocidos. Vector AES-GCM generado con 46.0.7 se descifra con la nueva versión. No se rotan claves ni se cambia el formato de datos.
- **Pasa con alcance limitado:** revisión local de patrones comunes de secretos en archivos a versionar, sin coincidencias. No equivale a análisis exhaustivo de secretos/dependencias ni a certificación de seguridad.
- **No ejecutado:** Auth/OTP y MFA de cuenta real, inscripción TOTP real, Resend sandbox/entrega real, contratos/precios/cuotas, scheduler alojado, CI en GitHub, protección de rama, validación nativa Windows, restauración de backup y ensayo de producción. Hay configuración de CI básica, no prueba de que GitHub la haya ejecutado.

## Criterios obligatorios

“Pasa” abajo significa comportamiento comprobado en entorno aislado. Las identidades y respuestas de proveedor son dobles de prueba; no hay adaptador de identidad ficticia en runtime. La integración real tiene su criterio y bloqueo separado S01.06.

| ID | Resultado | Evidencia |
|---|---|---|
| S01.AC-A · Tenant ajeno | pasa | `test_team_tenant_boundaries_privilege_escalation_and_scopes`; otro tenant no lista/invita; RLS runtime nueva tablas |
| S01.AC-B · Sucursal ajena | pasa | `test_branch_and_resource_reduction_applies_to_prior_session`; `test_workspaces.py` |
| S01.AC-C · Escalamiento navegador/token/IDs | pasa | roles/campos extra rechazados en `test_team.py`; JWT firma/issuer/audience/exp alterados rechazados en `test_healthsync.py` |
| S01.AC-D · Destinatario y alcance | pasa | `test_valid_invite_verified_recipient_server_grants_repeated_and_concurrent`; respuestas Auth sin sujeto/correo confirmado rechazadas |
| S01.AC-E · Repetida/vencida/revocada/sustituida | pasa | `test_unusable_invites_never_grant` y aceptación repetida |
| S01.AC-F · Aceptación concurrente | pasa | dos solicitudes simultáneas: una 200 y otra 409; una membresía con alcance exacto |
| S01.AC-G · Edición concurrente | pasa | versiones de membresía e invitación: una actualización válida y otra 409; creación duplicada no sobrescribe |
| S01.AC-H · Sesión previa y baja/reducción | pasa | mismo sujeto/token ficticio; perfil/sucursal/recurso consultados de nuevo en servidor; desactivación y reactivación |
| S01.AC-I · Último administrador | pasa | carrera por API y `test_database_guard_rejects_concurrent_last_admin_changes`; persiste un admin activo |
| S01.AC-J · SaaS/finanzas separados | pasa | calendario nominal denegado y resultados reales de fixture inaccesibles a finanzas/operador; paciente conserva lo propio |
| S01.AC-K · Auth/MFA | pasa | AAL1 denegado; Auth ausente, fallo de red y respuesta no verificable cierran acceso; firmado JWT asimétrico. Proveedor real: no ejecutado |
| S01.AC-L · Auditoría e historia | pasa | eventos append-only, sin token/correo/ciphertext en cambios; preservación de reserva/auditoría; bootstrap registrado |
| S01.AC-M · Modales/teclado/móvil | pasa | `Team.test.tsx`, `Dialog.test.tsx`, `scripts/test_team_browser.cjs` y `docs/demos/browser-results.json` |
| S01.AC-N · Regresión reservas | pasa | pruebas anteriores completas + smoke real; invitado, UTC, buffers, concurrencia, idempotencia, versiones, historial, privacidad y lectura de resultados |
| S01.AC-O · Conservación/migraciones | pasa | `test_migrations.py`, `test_new_composite_fks_and_rls_with_runtime_role`, rol mínimo y FKs compuestas |
| S01.AC-P · Control del proyecto | pasa | guía íntegra y documentos congelados, manifest, S00–S15, S13 por proveedor; `test_planning.py` rechaza IDs eliminados/duplicados/ciclos/criterios vacíos |
| S01.06 · Recorrido externo autorizado | **no ejecutado** | Sin cuentas conectadas, dominio, credenciales y autorización. Impide cerrar S01 y habilitar el módulo del piloto alojado |

No hay criterios finales con resultado falla después de las correcciones. Hubo fallos detectados y corregidos durante desarrollo: privilegio innecesario al intentar bloquear tenants (reemplazado por advisory lock), alcance incorrecto de consultas de prueba como propietario (corregidas por tenant), tipado de prueba UI, foco modal y dependencia criptográfica. La evidencia final corresponde al código corregido, sin ocultar integración pendiente.

## Reproducción y límites

Desde `backend`: `uv run --frozen pytest -q` y `uv run --frozen ruff check app tests ../scripts`. Desde raíz: `python scripts/planning.py --check`, `npm --prefix frontend test`, `npm --prefix frontend run build`. Para navegador ver [demo](../demos/README.md); para instalación existente [Windows](../windows-update-s01.md).

Las pruebas crean/eliminan únicamente bases de nombre aleatorio `healthsync_test_*` / `healthsync_migration_test_*`. No enviar/restaurar copias con comunicaciones externas habilitadas. La prueba HTTP usa exclusivamente la clínica demo reconocida y crea reservas ficticias. La migración y tests no autorizan una restauración destructiva ni borrar volúmenes.

La línea base se conserva; se registran cierres técnicos observados. Estimación inicial 25–48 horas efectivas con una persona, sin medición de duración real ni capacidad calendario confirmada. No hay fecha comprometida de fin S01/go-live; espera por terceros sigue sin estimar. S02–S15 conservan su alcance, dependencias y criterios; pagos únicamente documentados. Hallazgos abiertos: entrega de mensajes de pacientes, leases/latencia, conservación de invitaciones/contactos, vinculación de empleados antiguos y CI/operación alojada.

## Revisión publicada

Código funcional validado: [397de0d9cfd90c724880b95502efb6218d591e5c](https://github.com/clefaraco/Reserve_System/commit/397de0d9cfd90c724880b95502efb6218d591e5c). La actualización posterior solo enlaza evidencia/publicación y regenera las vistas; no cambia código funcional. Las seis comprobaciones de planificación se reejecutaron tras regenerarlas.

Rama remota subida correctamente con Git nativo. `gh pr create --draft` falló con `Post https://api.github.com/graphql: Forbidden`; no existe un PR creado por esta sesión. [Abrir el PR manualmente](https://github.com/clefaraco/Reserve_System/pull/new/feature/s00-s01-team-access), seleccionando **Create draft pull request** y usando [descripción preparada](PR_DESCRIPTION.md). Sin merge ni despliegue. Esto es un bloqueo de acceso a la API de GitHub, no un fallo de las pruebas del producto.
