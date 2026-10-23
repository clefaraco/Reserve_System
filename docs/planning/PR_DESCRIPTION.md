# S00/S01: planificación persistente y accesos seguros del equipo

Abrir como **borrador**, base `main`, rama `feature/s00-s01-team-access`. No merge ni despliegue.

Permite administrar el equipo de cada clínica mediante invitaciones temporales verificadas, un perfil principal, alcances por sucursal/agenda, versiones, baja/reactivación, MFA comprobado en servidor y protección concurrente del último administrador. No concede acceso clínico a operadores SaaS ni agenda nominal a finanzas.

S00 incorpora la guía íntegra, 581 registros trazables, backlog/Gantt generados desde JSON, línea base/previsión separadas, decisiones y evidencia. La migración 005 conserva las anteriores, datos, RLS y auditoría. Se actualiza cryptography a 50.0.2 por avisos detectados, con comprobación de lectura de cifrado anterior. Pagos solo documentales: Transbank/Mercado Pago primeras opciones, conservando los demás candidatos.

Validación local: 64 pruebas backend en PostgreSQL temporal, 11 frontend, build, ruff, smoke HTTP, planificación y Chromium a 360/1280 px. Auditorías de dependencias de producción sin avisos conocidos después de la actualización. Ver docs/planning/VALIDATION_S00_S01.md y docs/demos/README.md.

S01 permanece bloqueada en su cierre externo: Auth/OTP/MFA, dominio y correo reales no conectados ni probados. La demo UI intercepta API y los proveedores de pruebas son ficticios; no hay bypass de identidad en runtime, invitaciones reales, cobros, merge ni despliegue. Incluye procedimiento administrativo del primer admin y actualización Windows conservando claves/datos.

Código funcional validado: `397de0d9cfd90c724880b95502efb6218d591e5c`.
