# Validación realizada

Entorno de desarrollo verificado el 23 de octubre de 2026 con Python 3.12, Node 24 y PostgreSQL 17 en Docker.

| Comprobación | Resultado |
| --- | --- |
| Esquema SQL aplicado en bases PostgreSQL nuevas | Correcto; RLS y triggers activos, rol runtime sin propiedad ni BYPASSRLS |
| Backend: `python -m pytest -q` | 23 pruebas aprobadas |
| Frontend: `npm test` | 2 pruebas aprobadas |
| Frontend: `npm run build` | TypeScript y compilación Vite aprobados |
| Python: `ruff check app tests ../scripts` | Aprobado |
| Dependencias frontend: `npm audit` | 0 vulnerabilidades reportadas en la consulta, incluyendo desarrollo |
| Reinstalación con lockfiles y bootstrap sobre base existente | Correcta; conserva datos y claves |
| HTTP real: health, catálogo, disponibilidad, reserva, reintento y conflicto | Correcto; primera reserva 201, reintento 201 con mismo ID, conflicto 409 |
| Frontend iniciado y proxy hacia API | Correcto por HTTP local |

Las pruebas incluyen dos reservas simultáneas, dos INSERT concurrentes sin pasar por el controlador (uno excluido por GiST), buffer y adyacencia, RLS sin contexto y entre tenants, confirmación seguida de modificación, límites de tiempo, aislamiento por propietario, consentimiento vigente y WhatsApp, AES-GCM con manipulación/AAD incorrecto, JWT forjado/issuer/audience/expiración inválidos, reclamación de cuenta con correo verificado, entrega OTP simulada, exportación, anonimización sujeta a retención, auditoría append-only y persistencia de lecturas tras rollback. En Vault se comprueban aperturas repetidas, enlace vencido, otro usuario y relación asistencial concedida/revocada.

Las pruebas de UI verifican aceptación explícita, transición a cuenta con los datos ya ingresados y conservación de la clave de idempotencia tras un fallo de red. Se ejecutan en jsdom; no equivalen a una revisión visual en todos los navegadores.

El proveedor Auth, la entrega real email/WhatsApp, el bucket/KMS y el escáner PDF **no se validaron contra servicios externos**. Las pruebas usan transportes simulados para los proveedores y un PDF ficticio para la lectura. No se ha publicado el entorno, desplegado a producción ni verificado restauración en una tarea nueva. La consulta de vulnerabilidades es puntual y no sustituye un pentest ni una revisión de toda la cadena de suministro.
