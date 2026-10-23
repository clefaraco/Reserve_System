# Contexto para la IA que ayuda a preparar instrucciones

Este archivo es el punto de partida. Comparte su contenido y los documentos enlazados; no compartas `.env`, credenciales, datos de pacientes ni resultados médicos. Si una IA no puede abrir el repositorio, pega los documentos en el chat. El archivo describe el código de esta entrega, no capacidades futuras garantizadas.

## Mensaje listo para copiar

> Actúa como analista de producto y ayúdame a convertir mis necesidades en instrucciones claras para la IA desarrolladora. Soy una persona sin conocimientos de programación: explícame las decisiones por su impacto en usuarios, costos, seguridad y operación. El producto se llama Medical Appointment System, desarrollado por Tresuryx SpA. Es un SaaS de gestión médica para consultorios pequeños y redes de clínicas con distintas regiones, comunas, agencias y sucursales. Antes de generar un prompt revisa el estado real del proyecto y separa lo implementado de lo propuesto. No afirmes que una integración existe por aparecer en una especificación. Lee el contexto del repositorio y ayúdame a definir un cambio concreto, sus usuarios, permisos, flujo, excepciones y criterios de aceptación. No me pidas claves o datos reales ni propongas borrar la base existente. Si una decisión pendiente no bloquea el trabajo, propone un valor razonable y decláralo.

Repositorio: https://github.com/clefaraco/Reserve_System

## Requisitos y decisiones vigentes

- Producto visible: Medical Appointment System. Firma: Tresuryx SpA. `HealthSync` era el nombre anterior; identificadores técnicos históricos permanecen para conservar compatibilidad.
- Desarrollo local: Windows del usuario, carpeta `Reserve_System` dentro de su carpeta personal. Se actualiza mediante GitHub; este chat trabaja sobre otro checkout y sube cambios. La máquina del usuario no se actualiza sola.
- UI: React 19, TypeScript, Tailwind 4 y Vite 8. Paleta clara índigo/menta, diseño moderno, responsive. Errores/confirmaciones/éxitos en modales accesibles, nunca alertas de sistema.
- Backend ACTUAL: Python 3.12+ con FastAPI, psycopg y PostgreSQL 17 en Docker local. El usuario ya pudo ejecutar y ver la aplicación. Hay instalación portable con `python scripts/install.py`, que conserva claves y datos y aplica migraciones nuevas.
- Alojamiento OBJETIVO a evaluar: Cloudflare Workers/Static Assets o Pages, Supabase PostgreSQL/Auth/Storage y Resend. Todavía no está desplegado ni migrado a Workers. No asumir que FastAPI o el adaptador S3 se trasladan sin cambios.
- Privacidad: Chile Ley 21.719, Brasil LGPD y Argentina Ley 25.326; controles técnicos no equivalen a un dictamen de cumplimiento. Minimización, cifrado, consentimiento versionado, solicitudes de derechos, auditoría y retención revisada.
- Cada tenant tiene sus datos aislados con RLS y FKs compuestas. API con rol SQL sin propiedad ni BYPASSRLS. Las tablas actuales no se exponen directamente al navegador mediante Supabase.
- La restricción GiST con rangos UTC y buffers es obligatoria para evitar solapamientos, incluso al añadir pagos/telemedicina. Los cambios respetan límites y versiones.
- Paciente, administrador SaaS de Tresuryx, administrador del tenant, coordinación, recepción, médicos, finanzas y privacidad son ámbitos distintos. La interfaz no concede permisos por seleccionar un perfil.
- Pagos, seguros/Isapres/Fonasa/i-med, convenios, copagos y telemedicina son módulos requeridos con configuración delegada y versionada; las integraciones reales están pendientes.

## Implementado

- Reserva por servicio/profesional/fecha y hora, como invitado o con inscripción de cuenta mediante outbox y Magic Link verificado cuando se configura Auth.
- Confirmación, modificación y anulación de citas por paciente, portal con próximas citas e historial, exportación y solicitud de anonimización.
- API de privacidad y anonimización revisada, PII/IP cifrada, auditoría append-only y lecturas sensibles auditadas.
- Esquema y proxy de lectura segura de resultados con enlaces firmados de 15 minutos y auditoría por apertura. El almacenamiento externo y carga/escaneo aún requieren integración.
- Organización jerárquica, vinculación de sucursales y permisos de personal por sucursal o recurso.
- Espacio de equipo: agenda diaria paginada, sucursal, mínimo nombre de paciente para personal autorizado, recepción, cierre de atención/incomparecencia y resumen agregado.
- Perfil finanzas: resumen operativo sin nombres ni PDFs; no caja ni contabilidad monetaria todavía.
- Plano SaaS: operadores autorizados y directorio de organizaciones, acceso auditado; sin acceso clínico automático ni gestión comercial completa.
- Migraciones 003/004 agregan capacidades preservando reservas previas; no se inventa un historial de cambios anterior a su instalación.

## Pendiente

- Conectar Supabase/Auth real y aprovisionar identidades/perfiles; no hay usuarios demo con privilegios automáticos.
- Pantallas completas de edición de organización, usuarios y configuración; concesiones múltiples por usuario; consola comercial de planes/suscripciones.
- Identidad canónica de paciente para contar personas únicas sin duplicar perfiles de reserva; representantes/familiares y sus autorizaciones.
- Identidad profesional canónica para bloquear solapamientos de la misma persona cuando se publique en varias sedes/recursos. La restricción actual protege el recurso individual; no declarar resuelto ese caso por asignar varias agendas a una cuenta.
- Reportería avanzada, ocupación histórica y tiempos reales; las métricas actuales cuentan citas, no personas únicas.
- Avisos internos del personal y entrega real Resend/WhatsApp, preferencias, observabilidad y recuperación de eventos.
- Pagos online, caja, devoluciones, conciliación, documentos tributarios y conectores de cobertura/bonos.
- Sesiones privadas de telemedicina, proveedor real, consentimiento específico, reglas de acceso y manejo de incidentes.
- Ingestión de PDFs, malware, infraestructura, rotación multiclave, auditoría externa WORM, backups/recuperación y validaciones jurídicas/operativas.

## Estructura para orientar los prompts

```text
backend/app/main.py          API principal de reserva/paciente/privacidad/Vault
backend/app/workspaces.py    sesión, organización, agenda, asistencia y plano SaaS
backend/app/db.py            contexto transaccional y auditoría
backend/app/booking.py       reserva, disponibilidad, idempotencia y outbox
backend/app/worker.py        procesamiento de notificaciones
backend/tests/              integración real en PostgreSQL temporal
frontend/src/BookingFlow.tsx reserva, cuenta y portal del paciente
frontend/src/Dialog.tsx     modales accesibles y confirmaciones
frontend/src/Workspace.tsx  espacio del equipo y directorio SaaS
frontend/src/brand.ts        nombre del producto y empresa
database/001_schema.sql      esquema base histórico
database/002_demo.sql        catálogo ficticio inicial
database/003_*.sql           organización, alcances e historial operativo
database/004_*.sql           auditoría del plano SaaS
scripts/install.py          preparación local
scripts/bootstrap.py        base Docker y migraciones incrementales
scripts/migrations.py       versiones/checksums de migraciones
```

Lee [Producto y perfiles](PRODUCT_BLUEPRINT.md), [Pagos/coberturas/telemedicina](PAYMENTS_COVERAGE_TELEMEDICINE.md), [Privacidad](privacy-security.md), [Cloudflare/Supabase](cloudflare-supabase-target.md) y [Desarrollo local](local-development.md). Las propuestas AWS anteriores son alternativas históricas, no una decisión de contratar AWS ahora.

## Plantilla de prompt de desarrollo

```text
Objetivo y necesidad del negocio:
Usuario o perfil que lo necesita:
Qué puede hacer y sobre cuáles tenants/sucursales/recursos:
Flujo principal y qué se muestra al usuario:
Excepciones, errores y mensajes modales:
Reglas de precios/cobertura/tiempos si corresponden:
Configuración: qué habilita Tresuryx y qué puede cambiar la clínica:
Datos mínimos y restricciones de privacidad:
Integraciones existentes frente a las que aún se deben implementar:
Criterios de aceptación observables:
Datos y comportamiento anteriores que deben conservarse:
Qué debe quedar funcionando en esta entrega y qué queda para después:

Revisa el código actual antes de implementar. Reutiliza lo existente, conserva
RLS, auditoría, cifrado, bloqueo de agenda e idempotencia. Agrega migraciones
nuevas, pruebas pertinentes e instrucciones para actualizar Windows. No
afirmes que algo funciona si solo se escribió un diseño o se usó un proveedor
simulado. No publiques datos privados ni credenciales en GitHub.
```

Una buena instrucción concreta: “Permitir a recepción registrar la llegada de un paciente en sus sucursales, con confirmación modal, evitando duplicados y sin que pueda cerrar clínicamente la consulta”. Una petición como “haz todo el sistema completo” necesita dividirse en entregas verificables, conservando un mapa global como estos documentos.

## Actualización S00/S01 · entrega de revisión

Antes de preparar otra solicitud, leer [planificación persistente](planning/README.md), su `backlog.json`, decisiones y evidencia. S00–S15 se conservan con requisitos originales; no crear otra lista maestra en el chat.

La rama S00/S01 agrega migración 005, invitaciones/equipo, versiones, último administrador concurrente, MFA obligatorio del personal y adaptador de correo apagado. Ver [estado comprobado y bloqueos](planning/VALIDATION_S00_S01.md) y [procedimiento](team-access.md). Auth/MFA/correo reales siguen pendientes; no hay privilegios demo ni despliegue. Pagos: Transbank/Mercado Pago primeras opciones; Flow, Khipu, Compraquí, bancos y otros conservados en S13, solo documentación. S01 no se considera terminada mientras falte validar la integración externa autorizada.
