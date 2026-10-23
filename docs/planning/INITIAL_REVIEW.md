# Revisión inicial S00/S01 · 23 de octubre de 2026

Rama inicial `work`, árbol limpio, commit `2a9144bda99fb565ca157c7c42cf536c16f83deb`. `git ls-remote origin refs/heads/main` confirmó el mismo commit. Rama de entrega: `feature/s00-s01-team-access`. No había AGENTS.md aplicable ni una fuente estructurada de planificación. Se leyó el adjunto completo (639 líneas), los nueve documentos del repositorio, SQL 001–004, instalación/migraciones, Auth, contexto SQL, reservas, espacios de trabajo, UI y sus pruebas. Copias íntegras en `references/`; hashes en su manifest.

| Área | Estado al comenzar | Evidencia y límite |
|---|---|---|
| Reservas | Existente, integración local PostgreSQL | `booking.py`, `main.py`, 001: transacción, GiST UTC/buffer, versiones e idempotencia. Pruebas reejecutadas en esta entrega; no bloqueo canónico entre agendas del mismo médico (S02). |
| Permisos | Parcial | `db.staff_role`, `workspaces.py`, 003: consulta viva de membresías, sucursales/recursos. Sin gestión del equipo ni MFA aplicado. |
| Auth | Código existente, proveedor pendiente | JWT asimétrico/JWKS y correo verificado. La configuración externa no se ha autorizado/conectado; no se declara integrado. |
| Equipo | Pendiente | Membresías existentes, sin invitaciones/contactos administrativos/pantallas. No hay usuarios demo privilegiados. |
| Auditoría/cifrado | Existente con límites operativos | AES-GCM/HMAC y eventos append-only locales. Rotación multiclave, backup restaurado y archivo externo inmutable pendientes. |
| Reportes | Parcial | Conteos por estado y alcance; no personas únicas, ingresos ni duración real. |
| Resultados | Parcial; adaptador no integrado | Lectura autorizada y auditada; carga, escaneo y proveedor real pendientes. |
| Notificaciones | Parcial; externas simuladas en pruebas | Outbox durable. Hallazgo: worker de pacientes trata aceptación HTTP como entrega y hace llamadas dentro de transacción; registrados S08.DELIVERY/S08.LEASE. |
| SaaS | Parcial | Directorio metadata separado, no privilegio clínico. Contratación, planes y suscripciones pendientes. |
| Pagos/telemedicina/hosting | Especificado, no integrado | S13/S14/S05; mantener FastAPI/PostgreSQL/React en esta entrega. Ningún cobro ni despliegue autorizado. |

Las pruebas anteriores se conservaron y volvieron a ejecutar; sus resultados vigentes están en [VALIDATION_S00_S01.md](VALIDATION_S00_S01.md). Un documento o test escrito no se considera comprobación ejecutada. La demostración de interfaz intercepta API en el navegador y está identificada como simulada; las pruebas de servidor utilizan PostgreSQL real temporal, con identidad/proveedor ficticios aislados de producción.

S01 requiere cambios compatibles en membresías, nuevas tablas con RLS/FKs compuestas y auditoría propia sin inventar pacientes. No se modifica SQL aplicado, archivos de claves ni volúmenes. El primer administrador requiere identidad verificada, MFA y procedimiento explícito de operador propietario; no existe registro público que otorgue roles.

Hallazgos durante la ejecución: (1) foco no regresaba al invocador al desmontar el modal; corregido y comprobado en Chromium (S07.FOCUS). (2) Auditoría de dependencias identificó avisos en cryptography 46.0.7; actualización compatible a 50.0.2 y repetición del análisis sin avisos conocidos (S03.CRYPTO). No se cambian claves ni datos cifrados. (3) API GitHub GraphQL devuelve Forbidden, aunque lectura Git nativa funciona; publicación/PR se registra por separado en S00.PUBLICATION.
