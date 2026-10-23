# Primer encargo de desarrollo · Medical Appointment System

Preparado el 23 de octubre de 2026 para Clemente Faraco. Este archivo contiene el prompt completo y la guía de referencia íntegra. Entregar el archivo completo a la IA desarrolladora. Los requisitos de pagos del prompt amplían S13 de la guía; las prioridades y valores iniciales siguen siendo propuestas salvo instrucciones expresas del dueño.

## Prompt listo para entregar

Actúa como responsable técnico de Medical Appointment System, desarrollado por Tresuryx SpA. Necesito iniciar un desarrollo ordenado, verificable y sin perder requisitos. Soy dueño del producto y no programo: explica las decisiones por su efecto en usuarios, costos, seguridad y operación.

Repositorio: https://github.com/clefaraco/Reserve_System

Esta entrega tiene dos objetivos concretos:
A. Instalar un control persistente del proyecto con backlog, decisiones, requisitos y Gantt.
B. Implementar S01, gestión segura de acceso y ciclo de vida del personal de una clínica, reutilizando lo existente.

La guía íntegra incluida después de este prompt es parte del alcance documental. Sus 15 solicitudes son el mapa de trabajo, no una orden de implementarlas todas ahora.

1. REVISIÓN INICIAL, SIN REINICIAR EL PROYECTO

Revisa AGENTS.md si existe, rama/commit actual, cambios locales y:
- docs/AI_CONTEXT.md
- docs/PRODUCT_BLUEPRINT.md
- docs/PAYMENTS_COVERAGE_TELEMEDICINE.md
- docs/privacy-security.md
- docs/cloudflare-supabase-target.md
- docs/local-development.md
- Los demás documentos relevantes, migraciones, código y pruebas de las áreas que modificarás.

La versión revisada previamente fue 2a9144bda99fb565ca157c7c42cf536c16f83deb; verifica el estado vigente y no retrocedas el repositorio para coincidir con ella.

Presenta un diagnóstico breve: existente, parcial, pendiente, simulado, integrado y probado, con evidencia de archivos y pruebas. No confundas “hay código de Supabase” con “Auth está conectado”. Mantén FastAPI/PostgreSQL y React actuales en esta entrega; la elección de hosting tiene su propio backlog.

Tras esta revisión continúa con la implementación autorizada; no termines solo con recomendaciones. Si falta una dependencia externa, avanza lo independiente y deja identificado qué queda bloqueado, por qué y cómo se desbloquea. No simules un éxito para cerrar el trabajo.

2. BACKLOG PERSISTENTE Y TRAZABILIDAD

Antes de desarrollar, crea o adapta el mecanismo de planificación existente. Si no hay uno, utiliza:
- docs/planning/backlog.json como fuente estructurada.
- docs/planning/BACKLOG.md como vista legible.
- docs/planning/GANTT.md como vista del calendario y dependencias.
- docs/planning/DECISIONS.md como historial de decisiones.
- docs/planning/README.md con reglas simples de actualización.
- Una copia íntegra de la guía adjunta bajo docs/planning/references/, con su procedencia y fecha.

Evita listas maestras que diverjan. Las vistas deben generarse desde la fuente estructurada con un mecanismo pequeño y reproducible; si ya hay uno adecuado, reutilízalo. El archivo de decisiones guarda el historial, no duplica estados del backlog.

Importa todos los requisitos de la guía y documentos del repositorio. Conserva S01 a S15 como IDs estables y añade S00 para este control del proyecto. Desglosa en tareas hijas cuando sea necesario; no pierdas los criterios originales al resumir. Da ID también a requisitos transversales. Relaciona cada requisito con las tareas que lo cubren y registra los que aún no tengan entrega asignada.

Registra al menos:
- ID, título, necesidad, fuente exacta/fecha y requisitos relacionados.
- Categoría: funcional, arquitectura, seguridad, privacidad, interfaz, datos, reportes u operación.
- Prioridad y justificación: P0 crítico, P1 alto, P2 mejora, P3 evolución.
- Etapa: entrega actual, antes del piloto, piloto, comercialización o etapa posterior.
- Alcance del piloto que justifica cada bloqueo; distingue bloqueo total de bloqueo de un módulo.
- Usuario, permisos/alcance, funcionamiento y configuración.
- Excepciones, criterios de aceptación y dependencias por ID.
- Estado, responsable asignado o “por asignar”, bloqueos y siguiente acción.
- Estimación, unidad, rango/confianza, supuestos, inicio/fin previstos y fechas reales cuando existan.
- Evidencia de validación y enlaces a cambios/PR/commit cuando existan.
- Historial de cambios de prioridad, alcance, fechas, división, sustitución o cancelación.

Estados: propuesto, listo, en desarrollo, bloqueado, en validación, terminado, diferido y cancelado. “Diferido” no significa eliminado. Un duplicado conserva referencia al ID canónico. Si una tarea se divide, conserva el vínculo con la original.

No borres requisitos, no reutilices IDs y no marques terminado por haber escrito una especificación. Una épica solo termina cuando sus criterios están cubiertos; mostrar por separado cobertura verificada, pendientes y bloqueos. No inventes porcentajes de avance o fechas reales.

Al empezar y cerrar cada entrega, lee y actualiza estos archivos. Toda nueva mejora detectada o solicitud del dueño debe registrarse con fuente, prioridad, etapa y criterio antes de cerrar el trabajo. El chat no será el único registro. Revisa explícitamente al final si quedó algún punto tratado sin registrar.

3. GANTT ÚTIL Y HONESTA

Después de la revisión inicial, estima la entrega actual con supuestos explícitos de capacidad. No conviertas una estimación en compromiso.

La Gantt debe:
- Mostrar tareas/hitos con los mismos IDs del backlog, dependencias, fechas y bloqueos.
- Separar línea base inicial y previsión vigente; registrar motivo de reprogramación.
- Mantener lo no estimado visible como “sin estimar”, con dependencia y siguiente paso, sin inventarle fechas.
- Usar Mermaid para la vista versionada si no existe otra herramienta adecuada.
- Distinguir duraciones de trabajo, días de calendario y espera por terceros.
- Señalar qué impide iniciar y qué impide cerrar cada tarea.
- Aclarar que la ruta crítica es provisional si faltan duraciones o recursos.

No programes secuencialmente todo el producto sin analizar dependencias. No prometas una fecha de go-live por completar el documento. Valida IDs únicos, dependencias existentes, ausencia de ciclos, criterios trazables y consistencia entre backlog y Gantt.

4. MAPA MÍNIMO QUE DEBE CONSERVARSE

Importa la guía íntegra y sus detalles, además de esta lista de control:
- S00: backlog, Gantt, decisiones y trazabilidad.
- S01: acceso, invitaciones, perfiles, alcances, bajas, MFA y bootstrap del administrador.
- S02: profesional canónico, ocupación entre sedes/recursos/modalidades, buffers, migración y conflictos previos.
- S03: seguridad de API/navegador, sesiones, autorización, abuso, rate limiting, logs y entornos.
- S04: backups, restauración, claves AES/HMAC/firmas, rotación y supresiones tras restaurar.
- S05: arquitectura, prueba Cloudflare/Supabase, costos, residencia y modularidad.
- S06: organización, catálogo, agendas y configuración delegada/versionada.
- S07: agenda operativa, asistencia, cambios, modales, accesibilidad y móvil.
- S08: avisos al paciente/equipo, proveedores, preferencias, outbox, reintentos y observabilidad.
- S09: identidad canónica de pacientes, duplicados, cuentas, representantes y menores.
- S10: reportes, personas únicas, ocupación histórica, tiempos reales y exportación autorizada.
- S11: derechos, privacidad, conservación, consentimientos y procedimientos revisados.
- S12: carga de resultados, cuarentena, malware, almacenamiento privado, acceso y purga.
- S13: tarifas, presupuestos, convenios/coberturas, pagos, caja, devoluciones, conciliación, liquidación y documentos tributarios.
- S14: telemedicina, acceso privado, consentimiento, incidencias y agenda compartida con presencial.
- S15: planos SaaS/clínica, planes, suscripciones, múltiples concesiones y soporte excepcional.
- Requisitos transversales de base de datos, concurrencia, migraciones, pruebas, CI, costos, operación, documentación y actualización Windows.

5. DECISIÓN NUEVA SOBRE PAGOS, REGISTRAR AHORA

Transbank y Mercado Pago son las primeras opciones previstas. También deben conservarse como candidatos Flow, Khipu, Compraquí de BancoEstado, integración directa con bancos y otros proveedores futuros.

Esto expresa preferencia de producto, no una confirmación de que sus APIs, contratos o capacidades estén disponibles.

Añade a S13 tareas diferenciadas por proveedor y una evaluación común:
- Modelo extensible con adaptadores, sin imponer una pasarela a todas las clínicas.
- Configuración por tenant/comercio, entornos de prueba/producción y permisos separados.
- Posible coexistencia de pasarelas habilitadas en la misma clínica; medios visibles según servicio, moneda, contrato y capacidades verificadas.
- Cada clínica cobra en su comercio/cuenta; suscripciones Tresuryx separadas, salvo decisión posterior explícita.
- Separar pasarela online, POS presencial, transferencia registrada y conexión bancaria automatizada. Registrar una transferencia manual no equivale a integrarse con un banco.
- Verificar documentación oficial, contratación, sandbox, costos y capacidades antes de elegir el primer conector.
- No confundir Fonasa/Isapres/i-med/coberturas con pasarelas.
- Mantener importes/moneda y referencias en servidor, webhooks auténticos, idempotencia, aislamiento por comercio, pagos tardíos, devoluciones y conciliación.
- No almacenar PAN completo ni CVV.
- La retención de horarios debe quedar incluida en el bloqueo de PostgreSQL antes de introducir pago previo.
- Definir costo/comisión y su tratamiento por clínica solo como decisión pendiente; no cobrar automáticamente un recargo al paciente.
- No hacer fallback a otra pasarela ni cobrar nuevamente ante estado desconocido sin resolver el intento anterior.

Actualiza los documentos funcionales pertinentes con esta decisión. En esta primera entrega no implementes ni actives cobros; tampoco construyas anticipadamente un framework de pagos que no necesita S01.

6. ENTREGA FUNCIONAL S01, EQUIPO Y ACCESOS

Objetivo: que el administrador de una clínica pueda invitar, asignar y retirar acceso a su personal con trazabilidad.

Reutiliza las membresías y alcances actuales. Mantén inicialmente un perfil principal por usuario/tenant; múltiples concesiones permanecen registradas para una entrega posterior.

Usuarios y límites:
- Administrador del tenant: gestiona personal de su clínica; no operadores SaaS.
- Recepción/coordinación: solo sucursales asignadas.
- Médico: solo recursos/agendas asignados; resultados exigen además autorización asistencial.
- Finanzas: funciones financieras/agregados autorizados, sin agenda nominal ni PDFs por defecto.
- Privacidad: sus procedimientos autorizados, sin acceso general automático a la agenda.
- Paciente: no se convierte en empleado por elegir perfil.
- Operador SaaS: no obtiene acceso clínico por administrar el servicio.

Pantalla Equipo:
- Listado paginado con información mínima, búsqueda permitida, perfil, estado y alcance.
- Invitar por correo, asignar perfil y sucursales/recursos válidos.
- Vista previa de permisos antes de confirmar.
- Editar perfil/alcance, reenviar o revocar invitación y desactivar/reactivar usuario.
- Diferenciar estado de membresía, invitación y entrega de correo; no mezclarlos.
- Toda acción queda auditada; desactivar conserva citas e historial.
- Estados de carga/vacío/error y modales accesibles, diseño claro índigo/menta y uso móvil.

Reglas:
- Invitación de 48 horas como valor inicial, token opaco almacenado mediante hash, un solo uso, revocable y vinculado a tenant, destinatario y permisos decididos por servidor.
- Aceptación exige identidad verificada del destinatario; no confiar en email o perfil enviados por el navegador.
- Cambiar permisos o revocar invalida invitaciones pendientes relacionadas de forma segura.
- Guardar contacto mínimo del personal con protección coherente con la existente; no usar tablas de pacientes para resolver identidades de empleados.
- La baja/reducción de alcance se aplica en la siguiente operación protegida, aunque exista un token aún vigente.
- Impedir desactivar, degradar o retirar acceso al último administrador activo, incluso con operaciones simultáneas.
- Aprovisionar el primer administrador con procedimiento administrativo explícito y auditado; no mediante registro público, correo hardcodeado ni privilegios demo.
- MFA obligatorio para personal en el piloto alojado, con validación efectiva en servidor; no basta una pantalla ni una bandera del frontend. Mantener el flujo de pacientes existente.
- Configuración de Auth ausente o proveedor caído falla sin conceder acceso. Los dobles de pruebas quedan aislados del runtime desplegable.
- No envíes invitaciones reales ni conectes cuentas sin autorización aplicable. Usa datos ficticios y adaptadores de prueba claramente identificados.
- No escribas tokens/enlaces de invitación, correos privados o secretos en logs.

Integra invitaciones con el mecanismo durable existente si es adecuado. Comprueba entrega, deduplicación y recuperación sin afirmar que un correo fue entregado solo porque quedó en outbox. Si faltan credenciales externas, entrega código y pruebas independientes, documenta la configuración segura pendiente y deja ese cierre bloqueado.

7. CRITERIOS OBLIGATORIOS DE S01

Prueba y reporta cada criterio como pasa, falla o no ejecutado:
A. Administrador A no lista ni modifica personal del tenant B.
B. Recepción de sede A no obtiene citas de B manipulando solicitudes.
C. Paciente o empleado no eleva privilegios editando perfil, token o IDs.
D. Invitación válida solo activa al destinatario correcto con el alcance previsto.
E. Invitación repetida, vencida, revocada o sustituida no concede acceso.
F. Aceptación concurrente no duplica membresías ni amplía permisos.
G. Cambio de permisos simultáneo se resuelve sin sobrescritura silenciosa.
H. Baja/reducción de alcance actúa con un token previamente válido.
I. Dos bajas/degradaciones concurrentes no dejan la clínica sin administrador.
J. Operador SaaS y finanzas siguen sin acceder a pacientes/resultados por estos cambios.
K. Fallo de Auth o sesión sin MFA donde es obligatorio no abre el espacio del equipo.
L. Auditoría registra acciones sin secretos; se conserva la historia anterior.
M. Modales funcionan con teclado, foco y cancelación; el flujo cabe en móvil.
N. Reserva invitada y demás funciones existentes pertinentes no se rompen.
O. Migraciones nuevas conservan datos, RLS, FKs compuestas y privilegios mínimos.
P. Backlog/Gantt incluyen las 15 solicitudes, pagos ampliados y hallazgos nuevos sin perder requisitos.

No marques toda S01 terminada si solo hay pantallas, mocks o parte del flujo. Registra lo validado y lo bloqueado por integración externa.

8. CONSERVACIÓN, VALIDACIÓN Y ENTREGA

No borres/resetées la base ni sobrescribas .env. No modifiques migraciones aplicadas; agrega nuevas. Conserva cifrado, RLS, FKs compuestas, auditoría, versiones, GiST con UTC/buffers e idempotencia. No expongas las tablas actuales directamente al navegador ni cambies a un rol SQL con BYPASSRLS para simplificar.

Usa pruebas de integración en PostgreSQL temporal para permisos, concurrencia y migraciones, además de pruebas de interfaz pertinentes. Ejecuta las comprobaciones del repositorio adecuadas al cambio. No ejecutes pruebas destructivas sobre datos reales.

Trabaja en una rama revisable. Si tienes permisos de GitHub, sube la rama y abre un PR en borrador con alcance y evidencia; no hagas merge ni despliegues. Si no puedes, entrega los cambios locales y explica el impedimento.

Al finalizar entrega:
- Qué quedó funcionando y cómo probarlo paso a paso con datos ficticios.
- Criterios con resultados y evidencia ligados al commit; integraciones reales frente a simuladas.
- Resumen del backlog: nuevos, terminados, bloqueados, diferidos y cambio de previsión.
- Gantt vigente, supuestos y desviaciones frente a línea base.
- Decisiones adoptadas, pendientes y costos/dependencias externas.
- Instrucciones para actualizar Windows sin perder cambios, claves o base existente.
- Limitaciones y siguiente entrega recomendada.

Si encuentras un bloqueo de seguridad imprescindible para S01, corrígelo dentro de su alcance. Registra y separa mejoras mayores para evitar que este encargo se convierta en una reescritura de todo el producto.

Comienza por revisar el estado real, crear el registro persistente y desarrollar S01.

---

## Anexo · guía íntegra de referencia

Fuente: Medical_Appointment_System_Guia_de_Desarrollo.md, versión consultada el 23 de octubre de 2026. Se conserva como referencia; el estado del repositorio debe comprobarse al comenzar. La nueva decisión de pasarelas se registra en el prompt anterior.

# Medical Appointment System
## Guía de solicitudes y mejoras para la IA desarrolladora

**Producto de Tresuryx SpA · Preparado para Clemente Faraco · 23 de octubre de 2026**

Esta guía convierte necesidades del negocio en entregas comprobables. Las solicitudes de abajo son propuestas: no significan que las funciones estén construidas, contratadas o conectadas. No se realizaron cambios en GitHub, instalaciones, despliegues ni pruebas ejecutables durante esta revisión.

## 1. Punto de partida y alcance de la revisión

Repositorio: https://github.com/clefaraco/Reserve_System

Versión consultada de `main`: `2a9144bda99fb565ca157c7c42cf536c16f83deb`. Volver a comprobarla antes de implementar: el repositorio puede cambiar.

Se leyeron los cinco documentos enlazados en el contexto y código seleccionado de autenticación, contexto de base de datos, esquema inicial, reserva, agenda, asistencia, resultados, notificaciones, instalación y migraciones; también se inspeccionaron pruebas existentes de espacios de trabajo. No fue una auditoría exhaustiva ni una certificación de seguridad. La existencia de una prueba no demuestra que haya pasado en esta revisión.

| Área | Evidencia actual | Pendiente o límite |
| --- | --- | --- |
| Aplicación | React/TypeScript y API FastAPI; instalación local descrita | Hosting productivo y operación comprobada |
| Identidad | Código de validación de tokens Supabase y consulta de correo verificado | Configuración real, aprovisionamiento y experiencia completa de acceso del equipo |
| Permisos | Roles consultados en servidor; filtro por sucursal/recurso | Gestión visual, concesiones múltiples y ciclo completo de altas/bajas |
| Organización | Jerarquía y consulta de sucursales autorizadas | Edición completa desde pantallas |
| Agenda | Reserva transaccional, idempotencia y protección por recurso documentadas y presentes en código | Identidad profesional compartida entre sus agendas; nuevas pruebas de concurrencia al modificarla |
| Recepción | Llegada, inasistencia y controles horarios/versiones | Configuración versionada de reglas y operación avanzada |
| Cierre | El servidor permite cierre por médico autorizado o administrador | Decidir si el cierre administrativo será una excepción diferenciada |
| Reportes | Conteos por estado y alcance; finanzas no recibe la agenda nominal | Personas únicas, ocupación histórica, duración real y reportes monetarios |
| Privacidad | Rutas y controles de exportación/solicitudes; cifrado de contacto e IP | Consola especializada, procedimientos completos y revisión jurídica/operativa |
| Cifrado | AES-GCM; descifrado exige el identificador de clave actualmente configurado | Lectura multiclave y rotación sin perder datos |
| Resultados | Autorización, enlace de 15 minutos y apertura auditada; adaptador S3 | Ingestión, escaneo y almacenamiento real; nuevo adaptador si se elige Supabase Storage |
| Notificaciones | Outbox, reintentos y llamadas a Auth/webhook configurable | Resend/WhatsApp reales, seguimiento de entrega y avisos al equipo |
| SaaS | Directorio global protegido y auditado | Planes, contratación, suscripciones y onboarding comercial |
| Pagos y telemedicina | Especificaciones funcionales | Módulos e integraciones reales |
| Cloudflare/Supabase | Documento de dirección propuesta | Decisión de arquitectura y prueba de compatibilidad |

**Matiz importante sobre reservas:** crear otra agenda para el mismo médico no demuestra que ese profesional quede protegido contra solapamientos entre sedes. El bloqueo actual se aplica al recurso individual.

## 2. Instrucción permanente para la IA desarrolladora

Copiar este bloque junto con una sola solicitud de la sección 5. Si la entrega necesita dividirse, conservar los criterios y dependencias en un backlog.

```text
Trabaja sobre Medical Appointment System, desarrollado por Tresuryx SpA.
El dueño del producto no programa. Explica las decisiones por su efecto en
usuarios, costo de implementación/operación, seguridad y mantenimiento.

Antes de cambiar código:
1. Comprueba rama, commit, instrucciones del repositorio y estado de archivos.
2. Lee docs/AI_CONTEXT.md y los documentos pertinentes. Contrasta con código,
   migraciones y pruebas. Distingue: existente, parcial, propuesto, simulado,
   integrado con proveedor real y comprobado mediante ejecución.
3. Explica brevemente qué reutilizarás, qué falta y qué entregará este cambio.
   No vuelvas a construir una capacidad que ya existe.
4. Resuelve decisiones reversibles con supuestos explícitos. Consulta solo
   decisiones que cambien materialmente derechos, acceso, datos, cobros,
   contratos, arquitectura o alcance y que no estén autorizadas.

Durante la implementación:
- Conserva datos y compatibilidad. Agrega migraciones nuevas; no reescribas
  migraciones aplicadas ni reinicies la base. No borres volúmenes Docker.
- Conserva RLS, FKs compuestas, cifrado, auditoría, idempotencia, versiones,
  buffers y la restricción de exclusión de agenda en PostgreSQL.
- Valida identidad, permiso y alcance en cada operación de servidor.
  Un selector de perfil, tenant o sucursal no concede acceso.
- Separa paciente, personal de clínica, finanzas, privacidad y plano SaaS.
  Administrar el SaaS no otorga acceso clínico.
- No expongas tablas actuales al navegador mediante Supabase sin un rediseño
  explícito y pruebas. Una clave privilegiada no reemplaza el aislamiento.
- No incluyas secretos, .env, pacientes, resultados, tokens o enlaces privados
  en GitHub, capturas compartidas, logs o datos de prueba. Usa datos ficticios.
- Mantén el nombre visible y la firma. Conserva identificadores técnicos
  históricos salvo migración justificada.
- Mantén React/Tailwind y el diseño claro índigo/menta. Usa Dialog accesible
  para errores, éxitos y confirmaciones; explica qué puede hacer el usuario.
- Implementa pruebas proporcionales al riesgo, especialmente denegaciones,
  concurrencia, aislamiento, cambios de versión y preservación de datos.
  Usa bases temporales para integración; no Production.
- No conectes cuentas, envíes mensajes reales, contrates proveedores ni
  publiques servicios como consecuencia implícita de diseñar una función.
  Prepara el código y deja claros los pasos externos que requieran autorización.

Entrega:
- Explicación en lenguaje sencillo y demostración con datos ficticios.
- Estado de cada criterio: pasa, falla o no ejecutado; incluye evidencia
  suficiente sin datos privados. No inventes pruebas ni entregas de mensajes.
- Archivos y migraciones relevantes, limitaciones y dependencias.
- Instrucciones seguras para actualizar el checkout Windows existente,
  comprobando cambios locales antes de sincronizar. Mi PC no se actualiza sola.
- Recuperación/reversión de aplicación y datos cuando corresponda. Volver a
  una versión anterior no autoriza borrar datos nuevos.
- Documentación de estado actual y backlog actualizados con lo realmente hecho.

Implementa únicamente la solicitud seleccionada y sus dependencias necesarias.
Registra las mejoras adicionales con motivo, prioridad y prueba de aceptación.
No declares una integración activa porque exista un diseño o un simulador.
```

## 3. Cómo preparar cada nueva solicitud

No necesitas describir tablas, frameworks ni funciones. Basta con decir, por ejemplo, “quiero que recepción vea solo sus sucursales y pueda confirmar citas”. La solicitud resultante debe incluir:

| Campo | Qué debe explicar |
| --- | --- |
| Problema y resultado | Qué dificultad resuelve y qué cambiará para el usuario |
| Estado actual | Evidencia del código; qué se reutiliza y qué falta |
| Usuarios y permisos | Quién consulta, crea, modifica, aprueba y exporta; alcance por tenant/sucursal/recurso |
| Pantalla y flujo | Dónde empieza, pasos, información visible y resultado |
| Configuración | Qué controla Tresuryx, qué delega la clínica y valor inicial propuesto |
| Datos | Mínimos necesarios, sensibilidad, conservación y relaciones |
| Excepciones | Sin permiso, duplicado, sesión vencida, conflicto simultáneo, proveedor caído |
| Criterios | Escenarios observables de éxito, rechazo y conservación |
| Dependencias | Proveedor, contrato, configuración externa o entrega previa |
| Límites y entrega | Qué funciona al terminar y qué queda fuera |
| Costo y operación | Servicios nuevos, mantenimiento y efecto de no hacer el cambio |

No usar “seguro”, “rápido”, “responsive” o “cumple” como único criterio. Ejemplo verificable: “una recepcionista de sucursal A no obtiene citas de B al alterar la solicitud HTTP, y la respuesta no revela pacientes de B”.

## 4. Orden recomendado

Son prioridades propuestas, sin estimaciones de días ni presupuesto todavía.

| Orden | Solicitudes | Para qué |
| --- | --- | --- |
| 1 | S01 y S02 | Poder probar accesos reales de equipo y operar sin doble reserva del mismo médico |
| 2 | S03, S04 y S05 | Preparar seguridad, recuperación y decisión de alojamiento antes de pacientes reales |
| 3 | S06, S07 y S08 | Administrar la clínica y reducir trabajo manual |
| 4 | S09 y S10 | Identidad de pacientes y reportes fiables |
| 5 | S11 y S12 | Completar derechos y documentos clínicos |
| 6 | S13 y S14 | Cobros/coberturas y atención remota |
| 7 | S15 | Escalar comercialmente el SaaS |

Las actividades de seguridad y recuperación pueden prepararse desde el principio. No necesitan esperar al término de todas las pantallas. La salida a pacientes reales depende de los controles aplicables al piloto, no solo de que termine una fila de esta tabla.

## 5. Solicitudes propuestas

### S01. Acceso y ciclo de vida del personal

**Objetivo.** Que una clínica pueda dar acceso al equipo y retirarlo con trazabilidad.

**Actual.** Hay validación de tokens, membresía principal y alcances; faltan configuración real y administración completa. Tener código Supabase no prueba que Auth esté operativo.

**Usuarios/permisos.** Administrador del tenant gestiona personal de su clínica. Cada empleado ve sus funciones autorizadas. Solo un operador SaaS autorizado puede realizar el aprovisionamiento inicial definido; no recibe permisos clínicos por ello.

**Funcionamiento.** Pantalla Equipo con invitación, estado pendiente/activo/desactivado, perfil y sucursales/agendas. El destinatario verifica su identidad; la invitación no permite elegir privilegios. Mostrar vista previa de permisos antes de guardar. Desactivar conserva citas e historial.

**Configuración propuesta.** Empezar conservando un perfil principal por usuario y tenant; múltiples perfiles se desarrollan en una ampliación explícita. Invitación de 48 horas y segundo factor obligatorio para personal en el piloto alojado, sujetos a validación del proveedor. Verificar el segundo factor en servidor. Proteger el último administrador activo.

**Excepciones.** Invitación vencida, duplicada, usuario ya existente, fallo de correo y desactivación simultánea. No afirmar “correo entregado” por encolarlo. La baja bloquea nuevas operaciones de esa clínica aun con un token no vencido; cerrar la interfaz no basta.

**Comprobación.** Aceptar dos veces una invitación no duplica acceso; recepción A no ve B; paciente no se autoasigna rol; operador SaaS no obtiene PDFs; usuario dado de baja falla en su siguiente operación protegida. Fallo de Auth muestra un modal y no abre un acceso alternativo.

**Alcance.** Preparar y probar flujo con identidades ficticias en entorno de desarrollo; cuentas, dominio y envío real requieren configuración autorizada. No migrar el backend para hacer esta entrega.

### S02. Un médico, varias agendas, una sola ocupación

**Objetivo.** Evitar citas simultáneas del mismo profesional entre sedes, recursos y futuras modalidades.

**Actual.** GiST protege el recurso; falta la identidad profesional canónica por tenant.

**Usuarios/permisos.** Administrador vincula recursos al profesional correcto. Coordinación opera solo sus sedes; médico consulta sus agendas. Ninguno puede saltarse el bloqueo.

**Funcionamiento.** Crear identidad estable y relacionarla con recursos existentes. La disponibilidad y confirmación consideran toda su ocupación dentro del tenant sin revelar pacientes o detalles de otra sede. La migración identifica conflictos previos y entrega un informe restringido; no anula ni mueve citas automáticamente.

**Configuración propuesta.** Una identidad por persona dentro de cada tenant; buffers aplicados al intervalo ocupado y coexistencia con el bloqueo del recurso. Para el piloto, traslado entre sedes se cubre con bloqueos explícitos configurados; reglas automáticas de viaje quedan pendientes. El bloqueo entre tenants independientes requiere diseño adicional de privacidad.

**Excepciones.** Recursos históricos sin vinculación, duplicados sospechados y conflictos vigentes requieren revisión. No inferir identidad definitiva solo por nombre.

**Comprobación.** Dos reservas concurrentes en recursos del mismo médico no pueden confirmarse si chocan; tampoco dos reprogramaciones. Se respetan buffers y cambios de huso horario. No hay filtración de otra sede y todas las citas previas permanecen. La protección funciona contra solicitudes directas, no solo desde la pantalla.

### S03. Seguridad de acceso, navegador y API

**Objetivo.** Reducir abuso de reservas, escalamiento de permisos y exposición accidental.

**Actual.** Hay validación de identidad, autorización en servidor, RLS, cabeceras y cifrado; falta comprobar el endurecimiento del despliegue y sus límites reales.

**Usuarios/permisos.** Pacientes usan rutas propias/públicas; equipo usa rutas autorizadas. Operación consulta señales técnicas sin contenido clínico. Políticas obligatorias no son desactivables por una clínica.

**Funcionamiento.** Inventariar rutas y permisos; comprobar acceso por objeto/propiedad y respuestas mínimas. Añadir límites persistentes o distribuidos donde corresponda, tamaños máximos de formularios, manejo de fallos de identidad y sesiones, política de contenido del frontend y protección de transporte en el alojamiento elegido. Revisar logs del proxy además de la aplicación.

**Configuración propuesta.** Límites distintos para login/OTP, disponibilidad, reserva y exportación. La IA propone valores y los valida con tráfico ficticio de una clínica; no restringir toda una clínica solo por compartir IP. Definir la arquitectura de sesión según el alojamiento; si se eligen cookies, incluir protección CSRF y atributos adecuados.

**Excepciones.** Tráfico legítimo, accesibilidad, pérdida del proveedor de identidad y expiración de sesión. Mostrar reintento/espera sin revelar si un correo está registrado. No registrar tokens ni contenido sensible.

**Comprobación.** Cambio de tenant, paciente, recurso y rol falla cuando no hay permiso; límites operan con más de una instancia y resisten encabezados falsos; cuerpo sobredimensionado se rechaza; mensajes de error no contienen PII. Probar sesión de personal sin segundo factor y caída de JWKS. Documentar controles no ejecutados.

### S04. Recuperación de datos y rotación de claves

**Objetivo.** Poder recuperar la operación y renovar claves conservando acceso a datos antiguos.

**Actual.** Existe cifrado con identificador de clave; el código revisado no implementa un keyring multiclave. Backups restaurados y rotación completa siguen pendientes.

**Usuarios/permisos.** Operación autorizada administra respaldos y claves con separación de funciones. Ni recepción ni administrador de clínica acceden a secretos o respaldos completos del servicio.

**Funcionamiento.** Lectura con versiones anteriores permitidas, escritura con clave activa, recifrado por lotes reanudable y validación antes de retirar claves. Diseñar también rotación de HMAC y firmas: cambiar AES no resuelve las demás claves. Cifrar respaldos, restringirlos y restaurar en entorno aislado. Reaplicar supresiones que deban mantenerse después de una restauración.

**Configuración propuesta.** Separación por entorno y secretos fuera de GitHub. Proponer como objetivo inicial del piloto RPO de 24 horas y RTO de 8 horas: son metas a validar, no capacidades actuales ni un SLA. Ajustar frecuencia y costo al riesgo aprobado.

**Excepciones.** Clave ausente, backup incompleto, recifrado interrumpido o acceso revocado fallan sin descartar datos. No retirar una clave mientras existan datos o copias que la necesiten, salvo decisión de supresión válida.

**Comprobación.** Datos con clave A y B se leen durante la transición; interrupción no corrompe registros; se restaura una reserva y su auditoría en un entorno aislado; se miden pérdida real y tiempo de recuperación; secretos no aparecen en salidas. Entregar procedimiento comprensible de recuperación.

### S05. Decisión de arquitectura y mantenibilidad

**Objetivo.** Elegir alojamiento con evidencia y ordenar el código para cambiar módulos sin romper reservas.

**Actual.** FastAPI funciona como backend del proyecto; Cloudflare/Supabase es una dirección propuesta. S3 y el proceso de notificaciones requieren adaptación si cambia el runtime.

**Usuarios/permisos.** Tresuryx decide arquitectura y costos; clínicas y pacientes conservan sus permisos y flujos. La evaluación no concede acceso a datos reales.

**Funcionamiento.** Documentar responsabilidades de identidad, API, PostgreSQL, archivos y trabajos de fondo. Comparar mantener el backend actual alojado frente a migrar al runtime objetivo. Medir una operación transaccional representativa con datos ficticios y rol mínimo. Explicar costo inicial, mensual, migración, mantenimiento y recuperación, verificando documentación/precios vigentes al decidir.

**Configuración propuesta.** Mantener una aplicación modular con límites entre reserva, identidad, organización, privacidad, notificaciones y finanzas. Separar contratos de proveedores mediante adaptadores. No introducir cambios de stack o infraestructura por estilo. El archivo principal puede dividirse gradualmente por dominio conservando rutas y pruebas.

**Excepciones.** Incompatibilidad de dependencias, conexiones, tareas durables, cifrado o residencia de datos produce una decisión documentada, no un bypass de seguridad. Una región de base de datos no prueba residencia de todo el procesamiento.

**Comprobación.** La prueba conserva transacción completa, RLS, auditoría, cifrado y exclusión concurrente. Detallar qué se ejecutó y qué falta. Comparación de costos con fecha y supuestos. Esta entrega termina con decisión y prototipo aislado; migración productiva es una solicitud posterior.

### S06. Organización, servicios y configuración versionada

**Objetivo.** Que una sede pequeña se configure con pocos pasos y una red pueda administrar su jerarquía.

**Actual.** Estructura jerárquica consultable; faltan formularios completos y publicación de políticas.

**Usuarios/permisos.** Administrador del tenant administra sus sedes y catálogo. Delegados solo campos y sedes concedidos. Tresuryx habilita módulos y límites; clínica no puede ampliar su plan ni desactivar controles obligatorios.

**Funcionamiento.** Asistente de organización → sedes/husos → profesionales → servicios/agenda → revisión. Mostrar borrador, dependencias, valor efectivo, origen y fecha de aplicación. Guardar y publicar son acciones distintas. Desactivar conserva historia y advierte sobre citas futuras.

**Configuración propuesta.** Jerarquía geográfica opcional para una sede única. Herencia tenant → sucursal → servicio/profesional para campos delegables; no para ampliar permisos. Conservar condiciones aceptadas de citas existentes. Límites actuales de anticipación, cambio y asistencia se muestran como reglas actuales, no como configurables hasta implementarlas.

**Excepciones.** Ciclos, zona horaria inválida, profesional ocupado, dependencia no configurada y edición concurrente. Pedir recarga si la versión cambió; no sobrescribir en silencio.

**Comprobación.** Se configura una sede sin crear región/agencia; no hay ciclos; un delegado no edita otra sede; un cambio futuro no altera citas previas; un módulo sin proveedor no se anuncia activo. No se eliminan recursos con historia para “limpiar” el catálogo.

### S07. Agenda operativa y experiencia de pantallas

**Objetivo.** Agilizar recepción y coordinación con información clara y accesible.

**Actual.** Hay agenda diaria paginada, filtro de sede, llegada y estados; la gestión completa desde la interfaz debe comprobarse por acción.

**Usuarios/permisos.** Recepción registra llegada y acciones administrativas permitidas en su sede. Coordinación gestiona agenda dentro de su alcance. Médico cierra sus atenciones. Finanzas mantiene su vista agregada.

**Funcionamiento.** Filtros consistentes, estado de carga/vacío/error, detalle mínimo de cita y acciones válidas según permiso/estado. Confirmar, reprogramar y anular reutilizan API existente cuando corresponda, con auditoría y versión. Una reprogramación muestra hora anterior/nueva y huso. Evitar dobles clics sin depender solo del botón deshabilitado.

**Configuración propuesta.** Conservar inicialmente llegada desde una hora antes hasta un día después e inasistencia desde diez minutos después. Su futura variación se versiona en S06. Recomendar que el cierre administrativo excepcional se distinga del cierre clínico, con motivo y permiso específico; no cambiar unilateralmente el permiso actual.

**Excepciones.** Sesión expirada, cita cambiada por otro usuario, horario ocupado y conexión perdida muestran un modal con siguiente paso. Si el resultado del guardado es desconocido, consultar antes de repetir.

**Comprobación.** Flujo completo con teclado; foco regresa al botón al cerrar modal; a 360 px no hay acciones esenciales inaccesibles; cancelar modal no modifica datos; dos cambios simultáneos generan conflicto controlado. Al cambiar de usuario/tenant se descartan datos anteriores. Navegación no muestra pacientes en títulos de URL ni cachés compartidas.

### S08. Notificaciones fiables y seguimiento de incidencias

**Objetivo.** Saber si una confirmación salió y avisar al equipo cuando cambia su agenda.

**Actual.** Outbox y worker con reintentos; entrega real y avisos internos siguen pendientes. El worker revisado hace llamadas externas dentro de una transacción: evaluar su impacto antes de cambiar el patrón de bloqueo.

**Usuarios/permisos.** Paciente administra canales permitidos; personal recibe avisos de su alcance; operación reintenta eventos autorizados sin ver contenido clínico. Preferencias no conceden acceso.

**Funcionamiento.** Separar encolado, aceptado por proveedor, entregado y fallido solo si hay evidencia de cada estado. Bandeja interna del equipo, correo transaccional y adaptadores por canal se dividen en subentregas. Recuperación con evento estable, reintentos, cola agotada y estado desconocido. Si se acortan transacciones con leases, preservar orden, revalidación, recuperación y deduplicación.

**Configuración propuesta.** Proveedor por entorno/tenant según contrato; plantillas mínimas sin resultados ni diagnósticos. Retención de metadatos operativos definida; destinos de webhook limitados para impedir llamadas arbitrarias desde configuración. Reintento manual auditado.

**Excepciones.** El proveedor acepta y luego se pierde la respuesta; paciente retira consentimiento; cita se cancela antes de recordatorio; aviso se queda sin intentos.

**Comprobación.** Dos workers no provocan duplicados evitables; eventos viejos no envían horario anulado; no se marca entregado por recibir un 200 genérico; reinicio recupera pendientes; revocación de canal se respeta. La ventana de carreras y las garantías del proveedor quedan explícitas.

### S09. Identidad de pacientes y representantes

**Objetivo.** Reconocer personas sin confundir familiares ni unir historiales incorrectamente.

**Actual.** Perfiles de reserva no constituyen identidad canónica; representantes y personas únicas están pendientes.

**Usuarios/permisos.** Paciente verifica vinculaciones propias. Personal autorizado revisa posibles duplicados con información mínima. Representante solo accede a personas y acciones expresamente autorizadas; privacidad supervisa casos sensibles.

**Funcionamiento.** Separar persona atendida, cuenta de acceso y contacto. Implementar primero paciente canónico y vinculación verificada; representantes constituyen una subentrega con pruebas propias. Migrar referencias conservando citas/consentimientos/auditoría y dejar ambiguos para revisión. Toda unión registra evidencia y permite corrección controlada.

**Configuración propuesta.** Identidad por tenant. No unir personas automáticamente por nombre, correo compartido o teléfono; no exigir RUT/DNI/CPF como solución general. Para el piloto, acciones de representación deshabilitadas hasta contar con verificación y reglas aprobadas.

**Excepciones.** Familia comparte email; menor de edad; cuenta comprometida; autorización revocada; documentos contradictorios. Retirar representación no borra evidencia ni cancela por sí solo la atención.

**Comprobación.** Madre e hijo con mismo correo siguen siendo personas distintas; cuenta ajena no reclama historial; revocación quita acceso futuro; persona repetida se cuenta una vez solo después de vinculación válida. No cruzar identidades entre clínicas independientes sin diseño y autorización específicos.

### S10. Reportes fiables y exportación controlada

**Objetivo.** Que cada perfil tome decisiones con cifras que pueda interpretar y comprobar.

**Actual.** Conteos de citas por estado/día/alcance; no personas únicas, ingresos ni duración real.

**Usuarios/permisos.** Administrador consulta su tenant; coordinación sus sedes; médico sus recursos; finanzas agregados operativos y, cuando exista, información monetaria autorizada. Exportar requiere permiso separado de visualizar.

**Funcionamiento.** Primero ampliar reportes operativos basados en eventos existentes, con rango, sede, huso, definición y fecha de actualización. Presentar citas creadas, agendadas para el período, realizadas, anuladas e inasistencias como medidas distintas. Detalle nominal solo a quien tenga permiso. Exportaciones auditadas, limitadas y con descarga protegida.

**Configuración propuesta.** Un diccionario por indicador: numerador, denominador, fecha, estados y limitaciones. Personas únicas depende de S09. Ocupación histórica depende de guardar jornadas/bloqueos vigentes históricamente; asistencia no prueba duración real. Ingresos dependen de cobros confirmados de S13. Evitar totales que mezclen monedas sin regla explícita.

**Excepciones.** Denominador cero, períodos anteriores a migración, datos tardíos y falta de permisos. Mostrar “sin datos” o “no medible”; no inventar ceros. Consolidación entre tenants no se deriva del permiso SaaS.

**Comprobación.** Un conjunto ficticio conocido produce totales reproducibles; fronteras de día/huso son correctas; exportación y pantalla concilian con mismos filtros; finanzas no recibe nombres/PDFs; archivos tabulares neutralizan fórmulas aportadas por usuarios. Cambios de estado se reflejan sin doble conteo.

### S11. Gestión de privacidad y derechos

**Objetivo.** Que las solicitudes tengan responsable, seguimiento y respuesta verificable.

**Actual.** Hay API y controles; falta consola integral y procedimientos de ejecución/respuesta.

**Usuarios/permisos.** Titular solicita derechos; responsable de privacidad de la clínica gestiona solo sus casos. Administrador SaaS consulta únicamente señales operativas autorizadas. Separar aprobación y ejecución cuando la política lo exija.

**Funcionamiento.** Bandeja por estado, identidad verificada, responsable, fundamento, plazos aprobados, evidencias y respuesta. Canal alternativo para invitado sin revelar existencia de un paciente antes de verificarlo. Retención desconocida o impedimento legal bloquea supresión y explica el siguiente paso al responsable.

**Configuración propuesta.** Reglas por jurisdicción/clase de documento revisadas profesionalmente. No inventar un plazo universal ni presentar consentimiento como base única. Versionar documentos reales. Describir correctamente los registros seudonimizados retenidos; no prometer anonimización irreversible.

**Excepciones.** Solicitud incompleta, identidad dudosa, retención vigente, cita futura, almacenamiento pendiente de purga y backup restaurado. No borrar el rastro de la decisión.

**Comprobación.** Solo privacidad autorizada ejecuta el procedimiento; límites vigentes impiden supresión; el titular accede solo a su exportación; acciones dejan responsable/fecha/motivo; restauración respeta supresiones aplicables. No declarar cumplimiento legal por aprobar pruebas técnicas.

### S12. Carga y entrega de resultados

**Objetivo.** Completar el recorrido desde carga autorizada hasta lectura segura.

**Actual.** Existe acceso seguro de lectura; faltan ingestión, malware y almacenamiento operativo.

**Usuarios/permisos.** Un cargador autorizado incorpora documentos de su alcance; médico requiere autorización asistencial; paciente accede a lo propio. Recepción, finanzas y operador SaaS no obtienen permisos clínicos automáticamente.

**Funcionamiento.** Cargar en cuarentena, validar tamaño/tipo real, escanear, verificar integridad, vincular a paciente confirmado y publicar. Fallo/timeout de escaneo conserva cuarentena. Versionar correcciones y retiradas. Al abrir, comprobar identidad y autorización actuales además de la vigencia del enlace.

**Configuración propuesta.** Bucket privado y proveedor escogido explícitamente; conservar enlace de 15 minutos, sin tratarlo como credencial suficiente. Si cambia S3 por Supabase Storage, implementar adaptador y probar sus garantías. Retención por clase documental, no borrado masivo por fin de suscripción.

**Excepciones.** Archivo malicioso, PDF inválido, asignación errónea, relación asistencial revocada, doble carga y purga incompleta.

**Comprobación.** Documento en cuarentena no se descarga; enlace filtrado no permite acceso a otra cuenta; revocación actúa aunque el enlace no venza; auditoría registra aperturas; integridad alterada falla; carga no publica datos en logs. Probar purga y descarga en el proveedor elegido antes de llamarlo integrado.

### S13. Presupuestos, coberturas y cobros

**Objetivo.** Saber cuánto acepta pagar el paciente y conciliar lo realmente cobrado.

**Actual.** Especificación; no cobros, caja, bonos ni integración i-med activos.

**Usuarios/permisos.** Paciente acepta presupuesto; recepción tramita casos permitidos; finanzas cobra/conciliación según permiso; devolución y aprobación pueden ser funciones separadas. Tresuryx habilita el módulo; clínica configura contratos y comercio propios.

**Funcionamiento.** Dividir en entregas: tarifas/presupuesto → registro de pagos presenciales/caja → un proveedor online → devoluciones/conciliación → conectores de cobertura. Cada fase conserva sus criterios independientes. Separar presupuesto, cobertura, pago, devolución, liquidación y cita. Un retorno del navegador no acredita un cobro.

**Configuración propuesta.** Cada clínica recibe en su comercio y Tresuryx factura SaaS aparte, sujeto a decisión comercial. Sin PAN/CVV almacenado. Importes/moneda calculados en servidor; fotografía versionada del presupuesto aceptado. Cobertura desconocida va a revisión, sin cobro particular automático. Retenciones de horario deben entrar en GiST antes de habilitar checkout.

**Excepciones.** Pago tardío, webhook repetido/desordenado, proveedor sin respuesta, precio cambiado, devolución fallida y reprogramación con diferencia.

**Comprobación.** Dos pagos simultáneos no asignan la misma hora; monto/moneda manipulados fallan; webhook ajeno no afecta otro comercio/tenant; repetición no duplica movimientos; pago fuera de plazo inicia compensación/revisión sin desplazar a otro paciente; anular cita no declara una devolución inexistente. No anunciar integración activa por probar un simulador.

### S14. Telemedicina privada

**Objetivo.** Habilitar consulta remota con acceso vinculado a la cita y política de incidentes.

**Actual.** Módulo especificado; proveedor, sesiones y flujos pendientes.

**Usuarios/permisos.** Médico asignado, paciente y acompañante autorizado. Soporte no ingresa por defecto. Recepción puede ayudar con la cita sin acceder al contenido clínico.

**Funcionamiento.** Crear sesión privada cuando se cumplan condiciones; prueba de dispositivo, sala de espera, ingreso por identidad verificada, ventana de acceso y registro de asistencia. Compartir ocupación profesional con presencial mediante S02. Inicio/fin de conexión no se presenta como duración clínica sin definición aprobada.

**Configuración propuesta.** Modalidades por servicio/profesional; grabación, transcripción e IA desactivadas. Proponer ingreso diez minutos antes y cierre de admisión treinta minutos después del fin programado como valores a validar. Consentimiento, jurisdicción, incidentes y proveedor requieren decisiones explícitas.

**Excepciones.** Médico ausente, desconexión, paciente sin cámara, acompañante sin autorización y nueva cita. Definir contacto alternativo y cómo se decide devolución o reprogramación.

**Comprobación.** Token de otra cita/cuenta o vencido no entra; cancelación/revocación quita acceso; no hay sala pública reutilizable; no se superpone atención remota/presencial; fallo técnico muestra ayuda y deja seguimiento sin datos clínicos en logs. Prueba real autorizada del proveedor antes de habilitar a pacientes.

### S15. Administración comercial SaaS y permisos múltiples

**Objetivo.** Escalar el servicio conservando separación entre operación técnica, comercial y clínica.

**Actual.** Directorio SaaS protegido; planes, suscripciones y concesiones múltiples pendientes.

**Usuarios/permisos.** Operador comercial administra planes y metadatos autorizados. Administrador de clínica gestiona su contrato/configuración permitida. Personal puede necesitar varios roles con alcance específico; no recibe el máximo alcance de todos ellos indiscriminadamente.

**Funcionamiento.** Separar dos entregas: catálogo/versiones de planes y ciclo comercial; luego concesiones múltiples con matriz de conflictos. Mostrar módulo contratado, configurado y operativo como estados diferentes. Migrar rol principal a concesión equivalente sin ampliar permisos. Soporte excepcional, si se solicita, requiere una entrega específica con autorización, finalidad, caducidad y auditoría.

**Configuración propuesta.** Políticas explícitas por acción y alcance; restricciones obligatorias prevalecen sobre concesiones. Relación asistencial sigue siendo requisito independiente para resultados. Un usuario puede ser recepción A y finanzas B sin ver pacientes B. Cambios de plan tienen vigencia y tratamiento claro de datos preexistentes.

**Excepciones.** Suscripción impaga, downgrade con uso superior, revocación parcial y operador con varias funciones. No eliminar historia ni bloquear automáticamente derechos por deuda comercial.

**Comprobación.** Agregar finanzas B no amplía la agenda nominal de recepción A; retirar una concesión mantiene solo las otras autorizadas; rol comercial no abre resultados; plan deshabilitado se hace cumplir en servidor; cambios tienen trazabilidad y no se cobra dos veces un mismo período.

## 6. Mejoras transversales que deben acompañar cada entrega

| Tema | Instrucción práctica | Evidencia esperada |
| --- | --- | --- |
| Base de datos | Validar FKs compuestas, RLS y privilegios para entidades nuevas; cambios compatibles y migraciones incrementales | Prueba con rol runtime y dos tenants; datos previos intactos |
| Rendimiento | Medir consultas reales; revisar plan, paginación y límites antes de añadir índices | Medición reproducible, volumen ficticio y comparación antes/después |
| Conexiones | Mantener actor/tenant ligados a la transacción y limpiar contexto al reutilizar conexión | Solicitudes alternadas entre tenants sin contaminación |
| API | Validación estricta, versiones, idempotencia donde aplica y respuestas mínimas | Reintentos, campos no permitidos, concurrencia y conflicto controlado |
| Frontend | Componentes por dominio; carga/vacío/error y permisos coherentes; limpiar datos al cambiar contexto | Recorridos con roles distintos, teclado y móvil |
| Observabilidad | Identificador de incidente opaco, métricas técnicas, colas fallidas y alertas útiles | Fallo provocado detectable sin exponer pacientes ni secretos |
| Desarrollo | Pruebas necesarias y análisis de dependencias/secretos en CI | Resultado ligado al commit, sin afirmar que el análisis prueba seguridad total |
| Publicación | Separar desarrollo, pruebas y producción; revisar protección de rama/controles exigidos | Estado de configuración comprobado, no supuesto por existir un archivo CI |
| Costos | Explicar nuevos servicios, cuotas, retención y responsables; evitar estimaciones sin supuestos | Comparación fechada y alcance económico de la entrega |
| Datos de prueba | Ficticios y aislados; restauraciones no deben disparar mensajes reales | Entorno recuperado con comunicaciones externas deshabilitadas |

Los índices, particiones, cachés y rediseños se justifican con medidas. Toda caché con información de usuario debe incorporar alcance y revocación; no sacrificar autorización por velocidad.

## 7. Plantilla para comprobar una entrega

Pedir a la IA que complete esta tabla con evidencia de lo que ejecutó. Un resultado “no ejecutado” es válido y debe quedar visible; no equivale a aprobado.

| Criterio | Resultado esperado | Estado | Evidencia / limitación |
| --- | --- | --- | --- |
| Flujo principal | Usuario autorizado termina la tarea | Pendiente | |
| Permiso denegado | Perfil sin permiso falla también por API | Pendiente | |
| Otro tenant/sucursal | No se obtiene ni modifica información fuera de alcance | Pendiente | |
| Concurrencia/reintento | No duplica ni sobrescribe un cambio ajeno | Pendiente | |
| Privacidad | Sin PII/tokens en errores, logs o exportaciones indebidas | Pendiente | |
| Datos anteriores | Reservas e historia conservadas tras migración | Pendiente | |
| Interfaz | Modales accesibles, móvil, error y recuperación | Pendiente | |
| Integración externa | Separar simulador, sandbox y operación real autorizada | Pendiente | |
| Windows | Pasos de actualización claros y validación nativa identificada | Pendiente | |
| Recuperación | Se puede resolver fallo de despliegue/migración sin borrar datos | Pendiente | |

## 8. Fuentes y límites

Documentos del repositorio, fijados a la versión revisada:

- [Producto y perfiles](https://github.com/clefaraco/Reserve_System/blob/2a9144bda99fb565ca157c7c42cf536c16f83deb/docs/PRODUCT_BLUEPRINT.md)
- [Pagos, cobertura y telemedicina](https://github.com/clefaraco/Reserve_System/blob/2a9144bda99fb565ca157c7c42cf536c16f83deb/docs/PAYMENTS_COVERAGE_TELEMEDICINE.md)
- [Privacidad](https://github.com/clefaraco/Reserve_System/blob/2a9144bda99fb565ca157c7c42cf536c16f83deb/docs/privacy-security.md)
- [Dirección Cloudflare/Supabase](https://github.com/clefaraco/Reserve_System/blob/2a9144bda99fb565ca157c7c42cf536c16f83deb/docs/cloudflare-supabase-target.md)
- [Desarrollo local](https://github.com/clefaraco/Reserve_System/blob/2a9144bda99fb565ca157c7c42cf536c16f83deb/docs/local-development.md)

Código utilizado como evidencia: `backend/app/auth.py`, `db.py`, `booking.py`, `workspaces.py`, `main.py`, `worker.py`, `crypto.py`, `database/001_schema.sql`, `frontend/src/Workspace.tsx`, `scripts/install.py`, `scripts/migrations.py` y pruebas de espacios de trabajo. Las especificaciones cubren más que esta inspección de código.

Referencias primarias consultadas para las propuestas de acceso:

- [OWASP, Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html): denegación por defecto, mínimo privilegio y verificación de cada solicitud.
- [Supabase, Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security): roles privilegiados pueden omitir RLS; una clave de servicio no equivale a aislamiento por clínica.

Las recomendaciones de arquitectura, prioridades, valores iniciales y división de entregas son propuestas de esta guía. No sustituyen pruebas de carga, revisión especializada ni revisión jurídica. No se evaluó legislación para emitir una conclusión legal, ni se verificaron precios o contratos de proveedores.
