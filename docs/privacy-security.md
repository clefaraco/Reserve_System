# Privacidad desde el diseño y cumplimiento

Esta base implementa controles técnicos para Chile, Brasil y Argentina. El cumplimiento requiere validar finalidades, bases jurídicas, contratos, conservación y transferencias con el responsable de cada clínica. No se puede garantizar “cumplimiento estricto” solo generando SQL y componentes.

## Matriz de controles y alcance

| Requisito | Implementado | Decisión jurídica/operativa pendiente |
| --- | --- | --- |
| Minimización | Nombre y correo; teléfono solo si se activa WhatsApp; no RUT/DNI/CPF, fecha de nacimiento, diagnóstico ni historia clínica en reservas | Justificar cualquier campo adicional por finalidad |
| Datos sensibles | Consentimiento separado de términos; checkbox sin marcar; documento inmutable con versión, contenido y SHA-256, timestamp de servidor, actor e IP cifrada en auditoría | Determinar base jurídica válida; consentimiento no es la única base posible ni debe imponerse cuando no corresponde |
| Acceso/portabilidad | Exportación JSON del perfil, reservas, consentimientos, evidencias de acceso y metadatos de resultados | Canal alternativo para invitados, verificación de identidad, formato interoperable y plazos de cada país; los PDFs se obtienen por Vault |
| Rectificación/oposición/revocación | Registro autenticado y auditable de solicitudes por perfil | Tramitación y respuesta humana; la ejecución automática de estas tres clases aún no está implementada |
| Supresión | Solicitud, revisión de privacidad, soft delete, borrado de PII/HMAC/vínculo Auth e IPs separadas, cancelación de mensajes pendientes | Retención aprobada explícitamente y vencida, sin hold legal, sin reservas futuras ni objetos pendientes de purga |
| Aislamiento | `tenant_id` en todas las tablas, RLS FORCE, rol sin BYPASSRLS, FKs compuestas, consultas privadas autorizadas en API | No exponer credenciales de servicio ni esquema por PostgREST; revisar operadores y accesos excepcionales |
| Auditoría | Triggers de escritura; lecturas sensibles a través de API registradas y confirmadas antes de respuesta; eventos sin PII directa, evidencia IP separada | Archivo externo WORM, segregación de administrador, monitorización y auditoría SQL de accesos operativos |
| Cifrado | PII/IP con AES-256-GCM, nonce aleatorio, AAD vinculado al tenant/paciente, HMAC de correo por tenant; resultados requieren SSE-KMS | KMS/HSM, rotación y keyring, discos/volúmenes PostgreSQL y backups cifrados, TLS verificado, restauración probada |
| Recordatorios | Eventos transaccionales 24h/2h, versión de reserva, reintentos, consentimiento WhatsApp revalidado | Proveedor, DPA, transferencias, plantillas, deduplicación y entrega reales |
| Vault | URL firmada 15 min y autenticación, autorización, verificación SHA-256 y auditoría por apertura | Ingestión PDF, malware, bucket privado, IAM, KMS, provisión administrativa de relaciones asistenciales y purga verificable |

## Alcance real de anonimización

El endpoint conserva IDs aleatorios y las relaciones de reservas/auditoría. Quita el contacto cifrado, índice de correo, vínculo con identidad y evidencia IP, sin romper FKs. **Eso no garantiza anonimización irreversible de toda la historia**: fechas, recursos y hechos clínicos pueden reidentificar a alguien por información externa. El resultado se describe como evidencia seudonimizada retenida; debe evaluarse riesgo de reidentificación, acceso restringido, agregación o purga al vencer las obligaciones aplicables.

`retention_until=NULL` significa “aún no evaluado”, no permiso para borrar. La acción falla cerrada ante plazo desconocido, retención vigente o `legal_hold=true`. El responsable establece la retención por el procedimiento administrativo aprobado; no hay un parámetro público para saltársela. La retención médica no debe reemplazarse por un plazo inventado común a los tres países. También hay que purgar objetos, réplicas, índices externos y copias exportadas cuando sea legalmente procedente. Los backups requieren vencimiento/purga y una lista de supresiones para reaplicarlas durante una restauración.

Los documentos legales y eventos de auditoría son append-only por privilegios y triggers. Las IPs cifradas viven en `privacy_contexts`: un evento inmutable referencia una evidencia que puede borrarse con una decisión legal válida. Se conserva quién autorizó y ejecutó esa supresión. IDs de actor y correlaciones de auditoría siguen siendo datos seudónimos sujetos a base jurídica, acceso y conservación; no deben publicarse.

## Límites de confianza

- RLS no contiene a un superusuario ni a un propietario capaz de ejecutar DDL. El proceso rechaza credenciales de propietario/BYPASSRLS. Producción requiere cuentas separadas para migración, runtime y exportación de auditoría, y un destino WORM en otra cuenta. Un administrador podría desactivar triggers: esta base no pretende impedirlo matemáticamente.
- Las lecturas sensibles del gateway usan `audit()`; las escrituras usan triggers. Si una lectura autorizada precede a una validación fallida, su auditoría se vuelve a confirmar después del rollback. Accesos operativos por SQL, backups o consola requieren auditoría de infraestructura (por ejemplo pgAudit) y procedimientos de acceso, fuera de estos controladores. Nunca conceder lectura de tablas a clientes.
- La IP proviene del socket. El arranque local desactiva proxy headers. En producción, configurar la allowlist exacta del reverse proxy y normalización de IP; jamás aceptar el primer `X-Forwarded-For` de Internet. La IP tampoco prueba por sí sola la identidad o validez de un consentimiento.
- El catálogo publica solo datos del profesional destinados a publicación. La API de disponibilidad revela horarios libres, no IDs de pacientes ni motivos de indisponibilidad.
- No guardar PII, tokens, correos, URLs del Vault o cuerpos de respuesta de proveedores en logs/trazas. El arranque desactiva access logs y los errores de validación omiten el input. Aplicar redacción equivalente en proxy, APM y almacenamiento.
- El frontend guarda la sesión en memoria y no persiste PII en localStorage. Requiere una CSP de producción, dependencias actualizadas y protección XSS; para requisitos de mayor assurance, adoptar un BFF con cookies HttpOnly/Secure/SameSite y protección CSRF. La configuración CORS es una allowlist exacta, no autorización.

## Antes de admitir datos reales

Configurar HTTPS/HSTS, proxy confiable, límite de cuerpo de 32 KiB para formularios, rate limiting distribuido para reservas/OTP/disponibilidad y detección de abuso. Un `Idempotency-Key` no sustituye protección contra bots. Las notificaciones usan una clave estable para deduplicación, pero la entrega es at-least-once: el proveedor debe garantizar deduplicación y monitorearse la cola agotada. No se admite contenido médico en mensajes.

Provisionar Auth con confirmación de correo obligatoria, claves asimétricas, expiración corta, redirect allowlist exacta y MFA para personal. El rol clínico exige una relación asistencial vigente en `care_relationships`; establecer el procedimiento administrativo para concederla, revocarla y documentar su finalidad. Revisar periódicamente membresías y bajas. Configurar restricciones de egress para el proyecto Supabase, proveedor de notificaciones y bucket regional exactos, sin abrir destinos innecesarios.

Gestionar claves independientes mediante KMS/gestor de secretos; el `.env` generado es exclusivamente de desarrollo. El código usa un `key_id` y falla ante una versión desconocida: **rotación multiclave y recifrado aún deben implementarse** antes de rotar una clave con datos existentes. Cifrar el volumen de PostgreSQL y backups también protege metadatos de salud que deben poder indexarse (servicio, profesional, fecha); cifrar el JSON de contacto por sí solo no protege esos metadatos en disco.

Completar registro de actividades de tratamiento, evaluación de impacto, responsable/encargados y contratos, reglas para menores/representantes, política de conservación por clase documental, atención de titulares, gestión de incidentes y notificación, derechos específicos por jurisdicción y revisión de transferencias internacionales. Publicar documentos reales versionados en lugar de los textos `demo-1`. Este prototipo no incluye facturación, ficha clínica, un sistema completo de delegación familiar ni una consola administrativa de cumplimiento.

## Referencias normativas oficiales

- Chile: [Biblioteca del Congreso Nacional / LeyChile](https://www.bcn.cl/leychile/), Ley 21.719 y Ley 19.628; revisar también Ley 20.584 para información y documentación clínica. La entrada en vigor general de la Ley 21.719 está prevista para el **1 de diciembre de 2026**; validar disposiciones transitorias, reglamentos y criterios vigentes al desplegar.
- Brasil: [Lei 13.709/2018 — LGPD, texto oficial](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm), especialmente bases de datos sensibles, derechos del titular, seguridad y transferencias; revisar regulación y guías de la [ANPD](https://www.gov.br/anpd/pt-br).
- Argentina: [Ley 25.326, texto oficial](https://servicios.infoleg.gob.ar/infolegInternet/anexos/60000-64999/64790/norma.htm), y normativa/criterios de la [AAIP](https://www.argentina.gob.ar/aaip/datospersonales).

Estas referencias orientan la revisión; esta entrega no representa una verificación jurídica actualizada de toda norma secundaria ni un dictamen legal.
