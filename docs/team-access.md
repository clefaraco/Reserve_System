# Equipo y accesos · S01

Medical Appointment System · Tresuryx SpA. El código de gestión está implementado; la conexión y validación con Auth/MFA/correo reales siguen pendientes. No se habilita un piloto con pacientes reales por completar estas pantallas.

## Funcionamiento

El administrador activo con MFA abre **Espacio de equipo → Equipo**. Puede buscar por correo exacto, paginar, invitar, revisar permisos, editar perfil/alcance, revocar o emitir otra invitación, desactivar y reactivar. Los cambios usan una versión y bloqueo por clínica: si otro administrador guardó antes, se pide recargar. Un administrador no puede dejar la clínica sin otro administrador activo. Se conserva la membresía desactivada, citas e historia.

Un destinatario abre el enlace temporal recibido, verifica el correo y un segundo factor y acepta. El correo y los permisos del navegador nunca deciden la autorización: el servidor verifica identidad con Supabase, AAL2 del JWT asimétrico y los permisos guardados en la invitación. Repetir/alterar un enlace o aceptar simultáneamente no duplica acceso. Reenvío y edición de permisos pendientes sustituyen y revocan el enlace previo, verificando su versión. Crear otra invitación al mismo correo mientras hay una pendiente devuelve conflicto; no sobrescribe silenciosamente. Una invitación vencida no concede acceso aunque no se haya limpiado físicamente.

La invitación dura 48h. Su token tiene 256 bits aleatorios; la tabla guarda SHA256 y la cola una copia AES-GCM con AAD por tenant/evento. El token de recepción se retira inmediatamente del fragmento URL y queda solo en memoria. No se imprime ni aparece en el directorio/admin. Al cambiar de usuario, la interfaz descarta el directorio anterior. El correo de empleado se cifra por separado, sin usar pacientes. Contactos de membresías antiguas pueden figurar “pendiente de vinculación” (S01.LEGACY), sin inferir identidad.

## Permisos efectivos

| Perfil principal | Alcance | Límite |
|---|---|---|
| Administrador clínica | Su tenant | No operadores SaaS ni otras clínicas |
| Recepción / coordinación | Sucursales asignadas | Sin acceso a sedes ajenas; recepción sin cierre clínico |
| Médico | Recursos asignados | Resultados además requieren relación asistencial vigente |
| Finanzas | Agregados de sucursales asignadas | Sin calendario nominal, nombres ni PDFs |
| Privacidad | Procedimientos autorizados | Sin agenda general automática |
| Paciente | Lo propio | Ninguna autoasignación de perfil de personal |
| Operador SaaS | Metadatos globales autorizados | No acceso clínico por operar el servicio |

Cada operación protegida consulta membresía/alcance vigente, aunque conserve el token anterior. MFA es obligatorio en servidor; falta de configuración, firma inválida, correo no verificado, AAL1 o proveedor no disponible cierran el acceso del equipo. Un empleado que también es paciente conserva sus funciones propias de paciente sin convertirlas en acceso clínico general. No hay bypass de desarrollo desplegable.

## Primer administrador: procedimiento explícito

1. Tresuryx registra la autorización administrativa fuera del chat: identidad del responsable de la clínica, tenant exacto y aprobador. Verificar destinatario por canal autorizado. No enviar todavía correo real sin autorización.
2. Configurar un proyecto Auth de pruebas autorizado: confirmación de correo, firma asimétrica, MFA TOTP, URLs exactas y plantilla OTP que incluya el código. Configurar backend y frontend con URL y clave **publicable**, sin service-role ni tablas clínicas expuestas al navegador. Credenciales mediante el mecanismo de secretos del entorno, sin sobrescribir `.env` existente.
3. Un DBA autorizado aprovisiona la identidad de operador propietario en `platform.operators`, vinculando el UUID confirmado desde Auth. Es una tarea administrativa restringida, nunca registro público ni correo hardcodeado. Conservar autorización y evidencia del cambio en el registro de operación; registrar `platform.operator_events` con actor, request UUID e IP cifrada mediante las herramientas administrativas aprobadas. La API runtime no puede crear operadores. No hay operadores demo automáticos.
4. Con sesión del operador **con MFA**, desde `backend`, ejecutar:

```text
uv run --frozen python ../scripts/bootstrap_admin.py --tenant UUID-DE-LA-CLINICA
```

La herramienta pide sesión y correo de forma oculta, valida el operador propietario activo y que no exista personal previo, y crea una invitación de administrador auditada. No activa la membresía ni envía el correo. El destinatario deberá verificar su propia identidad/MFA al aceptar. Repetir antes de aceptación sustituye la invitación anterior; después de existir personal el bootstrap queda denegado. Recuperación de una clínica antigua sin administrador requiere procedimiento DBA auditado, no autoasignación pública.

5. Solo tras autorizar envíos: dominio verificado y cuenta Resend, remitente, secretos, webhook firmado, egress y URL HTTPS exacta de la aplicación del **tenant correcto**. El adaptador actual usa un remitente/proyecto por entorno; routing de dominios/plantillas múltiples pertenece a S08. No configurar una URL genérica que seleccione otra clínica.

```text
STAFF_EMAIL_SEND_ENABLED=true
RESEND_API_KEY=secreto-en-gestor
RESEND_WEBHOOK_SECRET=secreto-svix-en-gestor
STAFF_EMAIL_FROM=remitente-del-dominio-verificado
STAFF_ACCEPT_URL=https://dominio-exacto-de-la-clinica/
```

No copies estos valores de ejemplo como claves reales. Los nombres están en `.env.example`; la instalación no activa envíos. Ejecutar explícitamente, desde `backend`, `uv run --frozen python -m app.staff_delivery --tenant UUID` procesa como máximo un evento. Programación/operación durable del disparador se revisan antes del piloto; no hay un scheduler externo contratado/configurado aquí.

## Entrega de correo y recuperación

- **queued:** persistió en PostgreSQL; no se ha enviado.
- **accepted:** respuesta con ID del proveedor; no confirma entrega al buzón.
- **delivered:** webhook de entrega autenticado (Svix HMAC, timestamp, cuerpo exacto, ID del proveedor y tenant), procesado idempotentemente.
- **failed / unknown:** rechazo o resultado desconocido. No se reenvía automáticamente tras timeout/5xx. Consultar proveedor; administración puede revocar y reemitir, invalidando enlaces anteriores. No cambiar silenciosamente de proveedor.
- **superseded:** mensaje que aún estaba encolado para una invitación revocada/sustituida o ya consumida. Se conservan los estados aceptado/entregado/desconocido de mensajes que ya pudieron salir.

El evento proporciona una clave estable de idempotencia al proveedor. Un 429 se reprograma cinco minutos, hasta cinco intentos; no se promete entrega exactamente una vez frente a caída después del envío y antes del commit. Verificar el contrato real de deduplicación/retención del proveedor en S01.06. Las llamadas ocurren bajo transacción/lock para impedir enviar una invitación revocada mientras se procesa; su costo en latencia y un futuro esquema de leases quedan en S08.LEASE. El outbox histórico de pacientes requiere su propia corrección S08.DELIVERY.

Webhook: `POST /v1/{tenant_id}/team-delivery-webhook`. Sin secreto configurado rechaza. Cuerpo ≤32 KiB; firma fuera de ventana de cinco minutos rechazada. Eventos repetidos no duplican entrega ni degradan un estado final. Respuestas/eventos no almacenan cuerpo privado ni token en auditoría.

La validación con proveedor real (OTP, inscripción MFA, envío/entrega, recuperación y límites comerciales) **no se ha ejecutado**. No se conectaron cuentas ni enviaron invitaciones reales. Ver [evidencia](planning/VALIDATION_S00_S01.md). No hacen falta servicios nuevos pagados para las pruebas locales ficticias; contratos, precios, cuotas y dominio deben evaluarse antes del piloto.
