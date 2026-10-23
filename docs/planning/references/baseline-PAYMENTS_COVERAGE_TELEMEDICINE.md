# Pagos, coberturas y telemedicina

Especificación funcional y técnica del producto de Tresuryx SpA. **No hay cobros online, integración i-med ni videollamadas activas en el código actual.** Los siguientes flujos guían su implementación; no son una confirmación de contratos, acceso a APIs o cobertura de prestaciones.

## A. Configuración de prestación y cobro

Cada servicio puede permitir atención presencial, remota o ambas. La modalidad elegida forma parte de la reserva, junto con ubicación o sesión de telemedicina. Un servicio solo puede ofrecer modalidades, profesionales, cobertura y medios de pago válidos en esa clínica/sucursal.

Políticas de cobro configurables por clínica, con excepciones delegadas por servicio/sucursal:

- Sin cobro dentro de la plataforma.
- Pago en recepción o posterior a la prestación.
- Abono fijo o porcentual, indicando saldo pendiente y sus condiciones.
- Pago total antes de confirmar.
- Copago calculado y autorizado por cobertura/convenio.
- Revisión previa por recepción cuando el monto o la elegibilidad no puedan verificarse.

La consola muestra dependencias antes de publicar. Ejemplo: no habilitar “copago online con seguro” sin contrato, proveedor compatible, catálogo homologado, cálculo vigente y pasarela conectada. Un botón habilitado no prueba elegibilidad. Mostrar “requiere revisión” si no hay integración o respuesta concluyente; nunca cobrar silenciosamente el precio particular.

## B. Particular, Isapres, seguros, Fonasa, i-med y convenios

Representar por separado:

| Concepto | Significado |
| --- | --- |
| Precio de la prestación | Tarifa de lista o tarifa específica del convenio |
| Elegibilidad | Identidad/cobertura vigente para ese beneficiario y esa prestación |
| Autorización | Aprobación requerida para realizar o financiar la prestación |
| Bonificación/cobertura | Parte asumida por el financiador según reglas verificadas |
| Copago | Parte que corresponde al paciente |
| Bono/documento | Comprobante o instrumento de la prestación, según el sistema aplicable |
| Cobro y liquidación | Dinero recibido y posteriormente abonado/conciliado |

i-med es una posible integración del ecosistema, no una aseguradora ni una promesa de acceso universal a todas las Isapres. Fonasa, seguros complementarios, Isapres y convenios pueden requerir acuerdos, códigos, validaciones y flujos diferentes. Confirmar capacidades documentadas y contractuales de cada proveedor antes de automatizar. En otros países utilizar conectores y reglas propias, sin mapearlos artificialmente a una Isapre chilena.

El catálogo de convenios debe registrar entidad, país, prestaciones homologadas, sedes/profesionales habilitados, vigencia y versión. Las credenciales y documentos de beneficiarios requieren finalidad y minimización: el flujo simple no debe pedir RUT, número de póliza o antecedentes médicos; si la integración habilitada los exige, pedirlos solo en ese paso y protegerlos como datos personales/sensibles según corresponda.

Flujo previsto:

1. Selección de atención/modalidad/horario.
2. Elección de particular o cobertura habilitada.
3. Validación de beneficiario y prestación mediante conector o revisión humana autorizada.
4. Presupuesto vigente con precio, cobertura, copago, abono, saldo, moneda, restricciones, términos y vencimiento.
5. Aceptación explícita del presupuesto y condiciones por el paciente.
6. Autorización/bono y pago en el orden que requiera el proveedor concreto, con estados independientes y compensaciones documentadas.
7. Confirmación de la cita y envío de comprobantes mínimos, sin exponer información médica por email/WhatsApp.

Cobertura rechazada o desconocida debe ofrecer opciones claras: revisión, otra modalidad de pago autorizada o desistir. Cualquier precio particular alternativo requiere aceptación nueva. Guardar evidencia/versiones y referencias mínimas, evitando respuestas completas del proveedor con datos innecesarios.

## C. Pagos online y reserva concurrente

Proveedores candidatos para Chile incluyen Transbank/Webpay y otros que la clínica contrate. La selección exige verificar contrato, disponibilidad, modalidad de liquidación, API, sandbox, costos y obligaciones. No asumir soporte de un proveedor en un país por su nombre comercial.

Recomendación inicial: cada clínica recibe sus pagos en su propia cuenta de comercio. Tresuryx cobra la suscripción SaaS por separado. Recibir fondos de terceros, dividir pagos o liquidarlos como marketplace cambia responsabilidades regulatorias, comerciales y contables y requiere evaluación antes de implementarse.

Usar checkout alojado/tokenización del proveedor. La aplicación no almacena PAN completo ni CVV. Esto reduce el alcance de exposición, pero no constituye por sí solo certificación PCI ni elimina obligaciones de la integración.

Estados propuestos independientes:

| Entidad | Estados de ejemplo |
| --- | --- |
| Presupuesto | borrador → emitido → aceptado / vencido / reemplazado |
| Cobertura/autorización | pendiente → aprobada / rechazada / desconocida / revisión / revocada |
| Retención temporal de agenda | activa → consumida / vencida / liberada |
| Pago | creado → pendiente → autorizado → capturado / rechazado / cancelado / desconocido |
| Devolución | solicitada → pendiente → confirmada / fallida / revisión |
| Cita | pendiente de condiciones → reservada/confirmada → realizada / inasistencia / anulada |

Estos estados aún no se agregan al CHECK de la reserva actual. Antes de introducir una retención temporal o un estado pendiente de pago, ampliar GiST para que **también bloquee esos intervalos**, incluir el buffer y probar expiración concurrente, pago tardío y reintentos. Nunca crear un flujo de pago que ignore la restricción PostgreSQL existente. El vencimiento debe cambiar el estado mediante una operación de servidor; no usar `now()` en el predicado de una restricción de exclusión ni confiar en liberar el horario solo en la interfaz.

### Confirmación segura

- Crear presupuesto y retención en una transacción, con idempotencia y expiración de servidor.
- Crear el intento de pago referenciando presupuesto, tenant, clínica/comercio y retención. No mantener una transacción PostgreSQL abierta esperando que el paciente pague.
- Recibir notificaciones del proveedor; verificar firma/autenticidad, identidad de comercio, referencia, estado, monto y moneda contra valores del servidor. Deduplicar eventos y tolerar desorden.
- La vuelta del navegador con una pantalla “pago exitoso” no confirma un cobro. Confirmar mediante el mecanismo autoritativo que documente el proveedor.
- Al confirmar, bloquear filas y consumir la retención una sola vez. Si el pago llegó cuando ya venció/liberó la reserva, no desplazar a otro paciente: iniciar compensación/reembolso o revisión y comunicarlo.
- Procesar expiraciones, consultas de estado desconocido y conciliación con trabajos durables y reintentos. No depender del reloj del navegador ni de una pestaña abierta.

Representar importes con enteros en unidades menores según moneda; CLP no debe tratarse automáticamente como una moneda de dos decimales. Redondeo, porcentajes y topes de cobertura se calculan en el servidor con reglas explícitas. Los presupuestos guardan una fotografía de sus condiciones, no se recalculan retroactivamente al editar tarifas.

### Anulación, reprogramación y devolución

Definir por política qué ocurre con abonos, copagos, bonos emitidos, autorizaciones y pagos capturados. Cancelar una cita no prueba que se haya devuelto el dinero o anulado un bono. Una reprogramación puede conservar condiciones, exigir una diferencia o requerir nueva autorización. Mostrarlo y obtener aceptación antes de aplicar el cambio. El personal autorizado puede gestionar excepciones con motivo categorizado, aprobación y auditoría; no editar importes históricos sin trazabilidad.

## D. Caja, contabilidad y reportería

Dominios propuestos para la implementación:

- `price_lists`, `service_prices`, `payer_contracts`, `coverage_cases` y `coverage_authorizations`.
- `quotes`/`quote_lines`, `slot_holds`, `payment_intents`, `payment_events`, `refunds` y `settlements`.
- `cash_sessions` y movimientos de caja; conciliación y referencias a documentos tributarios emitidos por el sistema/proveedor correspondiente.
- `tenant_policy_versions` y concesiones de configuración para establecer vigencia y responsabilidad.

Todas las entidades clínicas/financieras usan `tenant_id` y relaciones compuestas; los conectores nunca deducen tenant solo de un parámetro del navegador. Configurar claves por comercio y comprobar las referencias de webhook.

Separar estados y reportes de prestaciones realizadas, cuentas por cobrar, copagos pendientes, cobros confirmados, reembolsos, liquidaciones y suscripciones de Tresuryx. Definir fecha contable, fecha de atención, moneda y alcance. Registrar devoluciones como movimientos compensatorios, no borrar ventas. La emisión tributaria depende del país y requiere una integración/documentación propia; no llamar “factura” a un simple comprobante de reserva.

Permisos separados: consultar resumen, ver movimientos, cobrar, conciliar, emitir documentos, solicitar devolución y aprobar devolución. Aplicar doble aprobación según monto/riesgo y clínica. Finanzas no recibe resultados ni historia clínica por necesitar cobrar.

## E. Telemedicina

Configurar por servicio, sucursal y profesional: modalidad, duración/buffer, plataforma de video, requisitos de elegibilidad y consentimiento, país de prestación/paciente, política de acceso, ventana de ingreso, acompañantes/representantes, fallos de conexión y ausencias. Una consulta remota ocupa la misma agenda del profesional y no puede superponerse con una presencial.

Antes de habilitar un proveedor, validar contrato, ubicación/procesamiento de datos, seguridad, accesibilidad, soporte móvil, límites y obligaciones profesionales/jurisdiccionales. No asumir que toda prestación puede realizarse a distancia o que un profesional puede atender en cualquier país.

Flujo previsto:

1. Crear una sala privada asociada a la cita una vez cumplidas sus condiciones de confirmación.
2. Mostrar comprobación previa de conexión, cámara/micrófono y orientación. Prever alternativa de contacto autorizada y procedimiento ante urgencias; no presentar el servicio como una línea de emergencias.
3. Sala de espera; profesional y paciente entran con identidad verificada y permisos vinculados a la cita. URLs/tokens breves, por participante y renovables con autorización; no enlaces públicos reutilizables.
4. Permitir entrada solo en una ventana configurable; registrar accesos y eventos de sesión sin guardar contenido médico en logs.
5. Registrar inicio/fin/asistencia por fuentes confiables, con correcciones autorizadas. Finalizar el flujo de atención y adjuntar documentos/indicaciones mediante canales seguros.

Grabación y transcripción desactivadas por defecto. Habilitarlas requeriría propósito, base jurídica, consentimientos aplicables, información a participantes, proveedor y conservación definidos. Tampoco habilitar asistentes de IA sobre una llamada por defecto.

La política debe resolver médico ausente, paciente ausente, interrupción, reingreso, cambio a presencial, nueva cita y eventual devolución. Distinguir llamada conectada de prestación efectivamente realizada. Evitar incorporar diagnósticos en nombres de salas, mensajes, analítica de terceros o URLs.

Dominios propuestos: `telemedicine_sessions`, `session_participants`, `session_access_events`, referencias opacas del proveedor y consentimientos específicos versionados. Secretos y tokens nunca en JSON de configuración público ni logs. Las salas no deben aparecer en el catálogo público.

## F. Configuración simple con controles

Tresuryx habilita módulos y conectores contratados; la clínica decide sus políticas dentro de ese marco. La futura consola organiza la configuración en pasos:

1. Organización y responsables.
2. Sedes, profesionales y modalidades de atención.
3. Tarifas y reglas de cobro.
4. Convenios/coberturas y requisitos.
5. Pasarela y comercio; prueba de conexión.
6. Telemedicina; prueba de ingreso.
7. Condiciones para pacientes, cancelación/devolución y notificaciones.
8. Simulación con datos ficticios, resumen del valor efectivo y publicación versionada.

Estados de integración visibles: no configurada, borrador, requiere contrato/credenciales, prueba, activa, degradada, suspendida. Un problema de proveedor debe tener un comportamiento definido: revisión, método alternativo aceptado o suspensión de nuevas reservas dependientes; no un éxito ficticio.

## G. Criterios mínimos de aceptación antes del piloto

- Dos pacientes no obtienen la misma hora, incluso con pagos simultáneos y buffers.
- Reintentar un checkout/webhook no duplica cobro, cita, bono ni devolución.
- Cobertura desconocida no dispara un cobro particular sin aceptación.
- Precio, copago y moneda se verifican en servidor; el navegador no puede alterarlos.
- Pago recibido después de la expiración tiene compensación y seguimiento; una redirección falsa no confirma nada.
- Un tenant no puede usar claves, pagos, bonos, sesiones o reportes de otro.
- Un cajero no puede consultar resultados ni aprobar sus propias devoluciones cuando se requiera doble control.
- Una modificación de políticas no altera retroactivamente presupuestos aceptados.
- Solo participantes autorizados pueden entrar a una sesión remota; un enlace vencido/filtrado no concede acceso.
- Ausencias y fallos técnicos siguen políticas y dejan evidencia; grabación desactivada por defecto.
- Se prueban recuperación de colas, conciliación, restauración, sandbox y al menos un flujo real autorizado por proveedor antes de anunciar la integración como activa.
