# Dirección propuesta: Cloudflare + Supabase + Resend

Esta propuesta simplifica el alojamiento para la etapa inicial y reemplaza la recomendación anterior de contratar ECS/Fargate para el MVP. No hay un despliegue activo ni una migración implementada por el solo hecho de escribir este documento.

## Responsabilidades

| Servicio | Responsabilidad propuesta |
| --- | --- |
| GitHub | Código fuente, revisiones y posteriormente CI/CD |
| Cloudflare Workers con Static Assets, o Pages para el frontend | Servir React compilado; elegir un único modo de publicación |
| Cloudflare Worker API | Autorización y lógica de servidor adaptadas al runtime, integraciones y acceso a datos |
| Supabase PostgreSQL | Datos persistentes, aislamiento por clínica, transacciones y restricción de horarios |
| Supabase Auth | Identidad, sesiones y verificación de correo |
| Supabase Storage privado | Resultados de exámenes, mediante un adaptador nuevo y política de acceso revisada |
| Resend | Correo transaccional; integrar el adaptador y configurar un dominio verificado |
| Worker programado / mecanismo de ejecución durable | Consumir el outbox con reintentos, control de concurrencia y deduplicación |

Supabase sí es una plataforma de backend: aporta base de datos, Auth, Storage y funciones. No ejecuta automáticamente los controladores FastAPI existentes. Cloudflare Workers aporta cómputo de backend; no reemplaza por sí solo la base PostgreSQL.

## Estado del código y compatibilidad

El código que puedes clonar y ejecutar hoy mantiene el stack pedido inicialmente: React, FastAPI/Python y PostgreSQL. La aplicación local no depende de Workers. La alternativa Cloudflare/Supabase requiere una migración posterior explícita; no deben anunciarse esas integraciones como terminadas.

Workers dispone de runtimes JavaScript/TypeScript y Python, pero no se debe asumir compatibilidad de este conjunto de dependencias con un contenedor Python convencional. Hay que validar FastAPI/ASGI, acceso PostgreSQL, cifrado, SDK de almacenamiento y límites de ejecución. El stack actual usa psycopg, cryptography, boto3 y un worker persistente. Un Python Worker no es simplemente ejecutar Uvicorn en Cloudflare.

Para un MVP apoyado en estas cuentas, la ruta más sencilla a evaluar es un Worker TypeScript con operaciones transaccionales acotadas en PostgreSQL. Supabase Edge Functions, que tienen un runtime distinto, son otra opción para operaciones de servidor; evitar duplicar la misma lógica sin necesidad. La decisión sobre migrar el backend Python se toma de forma explícita, porque cambia el stack original solicitado.

## Controles que debe conservar la migración

1. **Reserva atómica:** PostgreSQL debe crear paciente/consentimientos/reserva/inscripción/outbox en una sola transacción. No reemplazarlo por varias llamadas REST independientes. Una RPC cuidadosamente diseñada puede encapsularla; GiST sigue decidiendo los conflictos.
2. **Aislamiento:** el SQL actual confía en contexto `app.*` establecido por FastAPI y no concede acceso a `anon`/`authenticated`. No exponer esas tablas directamente al navegador sin rediseñar y probar sus políticas. Una clave `service_role` puede omitir RLS; esconderla en un Worker no demuestra aislamiento por tenant. Tampoco permitir que un cliente establezca por sí mismo actor o permisos de un RPC privilegiado.
3. **Cifrado:** migrar AES-GCM y su formato de claves con pruebas de compatibilidad; no perder acceso al cambiar de runtime. Configurar secretos mediante mecanismos del proveedor y definir rotación/keyring. No mover claves privadas a variables `VITE_*` ni al repositorio.
4. **Vault:** el adaptador actual es S3 SSE-KMS. Supabase Storage necesita un adaptador nuevo y verificar las garantías del plan contratado; no afirmar que tiene la misma gestión de claves que KMS. Mantener bucket privado, cuarentena/escaneo, URLs de 15 minutos y auditoría de cada apertura, no solo de su emisión.
5. **Notificaciones:** reemplazar el bucle persistente por un disparador programado/cola con lotes acotados y exclusión entre consumidores. Conservar versión de reserva, consentimiento, reintentos y deduplicación. `waitUntil` por sí solo no es una cola durable.
6. **Privacidad regional:** Workers puede procesar solicitudes en la red global de Cloudflare. Elegir una región para PostgreSQL no confina automáticamente todo el tratamiento a esa región. Revisar residencia, transferencias, logs, copias, encargados y controles disponibles en cada plan antes de datos reales.
7. **Costos y cuotas:** una demo con datos ficticios puede comenzar en planes gratuitos disponibles. Disponibilidad, cómputo, programación, correo, almacenamiento, recuperación y permisos comerciales deben contrastarse con los planes vigentes. No se promete producción médica confiable y gratuita indefinidamente.

## Secuencia

1. Guardar y compartir la base actual por GitHub y trabajar con una demo local visible.
2. Validar un prototipo pequeño del runtime Cloudflare elegido y su conexión de mínimo privilegio a un proyecto Supabase de desarrollo.
3. Migrar la reserva transaccional y ejecutar pruebas reales de concurrencia, tenant y autorización antes de cambiar el frontend.
4. Migrar notificaciones y acceso a resultados, con las mismas garantías y pruebas de cifrado/auditoría.
5. Conectar despliegues desde GitHub, revisar los contratos/controles y habilitar un piloto.

La reportería sigue el alcance de `production-reporting-plan.md`, pero debe usar la API y el backend finalmente elegidos. Los conteos de personas únicas requieren resolver primero la identidad clínica, independientemente del proveedor.
