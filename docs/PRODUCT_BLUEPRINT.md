# Medical Appointment System · Tresuryx SpA

Documento de alcance del producto. Distingue capacidades actuales de módulos por desarrollar; una especificación no equivale a una integración activa.

## Producto y diseño

Nombre visible: **Medical Appointment System**. Desarrollador: **Tresuryx SpA**. Identificadores técnicos históricos `healthsync`, nombres de base, roles SQL y variables se conservan para no romper instalaciones existentes. No renombrarlos sin migración.

Interfaz clara, moderna, adaptable a móvil/escritorio: blanco, gris azulado, índigo suave, menta y estados semánticos legibles. No usar color como única señal. Mensajes de error, éxito y confirmaciones usan el componente modal `Dialog.tsx`; no usar `window.alert`, `window.confirm`, `window.prompt` ni burbujas nativas de validación. La información estática y los estados de carga pueden mostrarse dentro de la pantalla. Los modales requieren título, descripción, foco, Escape/cancelación y confirmación explícita de acciones destructivas. No mostrar errores técnicos ni datos privados de terceros.

## Organizaciones de distintos tamaños

Una clínica o consultorio es un **tenant**, con sus datos aislados. Una sede pequeña no debe completar una jerarquía corporativa para reservar. Una red grande puede utilizar:

`Tenant/red → país → región/estado/provincia → comuna/localidad → agencia/unidad → sucursal → especialidad → profesional/recurso → servicio`.

Los niveles geográficos son configurables por país, no exclusivos de Chile. Cada sucursal mantiene su huso horario. Una red puede contener varios países, aunque cada despliegue debe respetar las condiciones de residencia y transferencia que correspondan. Si los responsables legales son entidades independientes, evaluar tenants distintos; no unir organizaciones solo para facilitar un informe. Una consolidación autorizada entre tenants necesita un diseño explícito.

La migración 003 agrega unidades organizativas jerárquicas, vinculación de sucursales, alcance de personal por sucursal y asignación de agendas a médicos. Hay FKs compuestas, RLS y rechazo de ciclos. Las rutas actuales permiten consultar la organización, no administrarla completamente desde formularios.

Antes de habilitar profesionales que atiendan en varias sedes, agregar una identidad profesional canónica por tenant y una restricción de agenda sobre esa identidad, además de la del recurso. Hoy GiST protege cada recurso; crear dos recursos distintos para la misma persona no debe convertirse en una forma de reservarle dos consultas simultáneas. El calendario asignado a una cuenta permite consultar varios recursos, pero no sustituye esa garantía pendiente de identidad/ocupación profesional. Presencial y telemedicina deben compartir ese bloqueo.

## Dos niveles de administración

| Perfil | Responsabilidad final | Estado actual |
| --- | --- | --- |
| Administrador SaaS de Tresuryx | Organizaciones, planes, módulos contratados, límites, operación del servicio, soporte y suscripciones | Directorio de tenants protegido por identidad global, acceso auditado; gestión comercial pendiente |
| Administrador del tenant | Organización, sedes, profesionales, servicios, agendas, usuarios, permisos, políticas e integraciones de la clínica | Acceso al espacio operativo, estructura visible, agenda, registro de asistencia y resumen; edición completa pendiente |
| Coordinador de agenda | Reservas y cambios dentro de sucursales asignadas | Consulta de agenda y cambios protegidos por alcance; gestión avanzada pendiente |
| Recepción | Llegada de pacientes, agenda diaria, confirmaciones, anulaciones e inasistencia | Agenda scoped, check-in e inasistencia; no puede cerrar clínicamente una atención |
| Médico/profesional | Su calendario, pacientes citados, cierre de atención y resultados autorizados | Agendas asignadas y asistencia; resultados además exigen relación asistencial vigente |
| Finanzas/contabilidad | Precios, caja, copagos, cobros, reembolsos, liquidaciones, conciliación y documentos | Resumen operativo agregado por sucursal; módulo monetario pendiente, sin acceso a nombres ni PDFs clínicos |
| Responsable de privacidad | Solicitudes de titulares, revisión de retención y evidencias | API de solicitudes y anonimización revisada; consola especializada pendiente |
| Paciente | Reservar, próximas citas, historial, confirmar/modificar/anular, exportar datos, solicitar derechos, pagar y acceder a resultados | Reserva y autogestión básica, pestañas próximas/historial, privacidad; pagos y telemedicina pendientes |

El paciente es una relación de propiedad de sus datos, no un rol de personal. El rol SaaS se almacena en un plano de control separado y no concede por sí solo acceso a citas, nombres, PII o resultados. Soporte excepcional futuro requiere autorización explícita, finalidad, plazo, trazabilidad y políticas legales; no implementar un botón de suplantación irrestricta.

Los permisos se validan en servidor. Ocultar un botón, elegir un perfil o un tenant en el navegador no autoriza nada. Actualmente hay un perfil principal por usuario y tenant; antes de soportar personas con varios perfiles simultáneos se deben implementar concesiones múltiples y resolver conflictos de alcance. No conceder `admin` como sustituto de una asignación clínica.

## Base operativa implementada en esta iteración

- `/v1/{tenant}/session`: identidad de sesión, perfil, capacidades y rol SaaS propio.
- `/organization`: sucursales autorizadas y sus ancestros organizativos.
- `/staff/appointments`: agenda paginada, filtrada por día/sucursal y alcance; entrega nombre mínimo y audita las lecturas, sin email/teléfono ni ciphertexts.
- `/staff/summary`: conteos agregados de citas por estado, no personas únicas.
- `/staff/appointments/{id}/attendance`: recepción, cierre de atención e inasistencia con permisos, horario, bloqueo y versión.
- `/v1/platform/tenants`: directorio de metadatos para operadores SaaS verificados; no selecciona un tenant clínico.
- `attendance_records`: llegada/cierre; `appointment_events`: historial append-only desde la migración. El historial anterior a la instalación no se inventa.
- `workspace_events` y `platform.operator_events`: accesos agregados/operativos auditados con IP cifrada; no se inventa un paciente ficticio para registrar la lectura de un informe.

El check-in se habilita desde una hora antes de la cita y hasta un día después; una atención se cierra cuando ya comenzó y solo por médico asignado/admin. La inasistencia requiere diez minutos desde la hora prevista. Son reglas iniciales explícitas; su configuración versionada por tenant es una ampliación pendiente.

Médicos y personal deben recibir alertas de cambios, cancelaciones y próximos pacientes. Actualmente hay outbox de avisos al paciente; bandeja interna, preferencias del personal y entrega a empleados están por implementar. No confundir un resumen de agenda con notificaciones entregadas.

## Configuración por Tresuryx y por clínica

Separar cuatro capas:

1. **Requisitos de seguridad/jurisdicción:** aislamiento, verificación de identidad, auditoría, conservación, cifrado y controles obligatorios. Un cliente no puede deshabilitarlos para eludir obligaciones.
2. **Plan habilitado por Tresuryx:** módulos y límites contratados (agenda, red de sedes, cobertura, pagos, telemedicina, resultados, reportes, API, etc.). Habilitar un módulo no significa que sus proveedores estén conectados.
3. **Políticas del tenant:** configuración clínica aprobada con responsables, vigencia y versión.
4. **Sobrescrituras autorizadas:** sucursal → especialidad/servicio/profesional, solo para campos delegables. Mostrar el valor efectivo y de dónde viene; una sede no puede ampliar permisos o módulos que el tenant/plan no permite.

La futura consola debe incluir: asistente de primera configuración, borradores, validación de dependencias, vista previa de la experiencia del paciente, prueba de conexión, publicación con fecha efectiva, historial y reversión segura de políticas futuras. No modificar condiciones de citas/presupuestos ya aceptados sin una política y consentimiento aplicables. Las claves se almacenan en mecanismos de secretos, nunca dentro del JSON de configuración ni en el navegador. Pedir un dato solo cuando un módulo habilitado y su finalidad lo justifiquen.

Configuraciones previstas: país/huso/moneda, geografía y sedes, identidad de pacientes y representantes, roles/alcances, catálogo, reglas de anticipación/buffers, pagos, convenios y coberturas, telemedicina, comunicaciones, retención y reportes. [Pagos, cobertura y telemedicina](PAYMENTS_COVERAGE_TELEMEDICINE.md) define los flujos y dependencias.

## Reportes y finanzas

La primera entrega muestra citas del día, atenciones realizadas e inasistencias dentro del alcance del usuario. No presenta cifras de facturación, ocupación real o personas únicas que el modelo todavía no permite demostrar.

Antes de métricas definitivas: paciente canónico por tenant con vinculación verificada, conservación histórica de jornadas/bloqueos, definiciones consistentes de cohortes/husos y eventos de asistencia/pago. La duración programada no equivale al tiempo real de consulta. Un ingreso requiere un cobro confirmado, no una reserva creada. Reembolsos, autorizaciones, deudas y liquidaciones tienen fechas y estados distintos.

Finanzas de Tresuryx (suscripciones SaaS) y finanzas de la clínica (prestaciones/coberturas) son dominios y permisos distintos. Una suscripción impaga no debe bloquear automáticamente el ejercicio de derechos ni eliminar historias clínicas.

## Secuencia del producto

1. Identidad visual, modales, modelo de organización y acceso, agenda operativa y contexto compartido para colaboración.
2. Configuración y gestión de usuarios/recursos desde la clínica, identidad canónica y reportería validada.
3. Presupuestos, convenios y coberturas; pagos online y caja con conciliación.
4. Telemedicina y resultados con proveedores reales, autorizaciones y privacidad.
5. Administración comercial SaaS, automatización de onboarding y operación de redes grandes.

Cada etapa requiere migraciones que preserven datos, permisos, escenarios de concurrencia, pruebas funcionales y documentación de qué quedó implementado. Publicar código en GitHub no publica automáticamente servicios ni activa proveedores externos.
