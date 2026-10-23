-- Synthetic catalog only. DO NOT publish these placeholder legal texts to patients.
BEGIN;
INSERT INTO healthsync.tenants (tenant_id,name,country)
VALUES ('10000000-0000-4000-8000-000000000001','Clínica HealthSync · Demo','CL');
INSERT INTO healthsync.tenant_modules VALUES
('10000000-0000-4000-8000-000000000001','medical',true),
('10000000-0000-4000-8000-000000000001','vault',false);
INSERT INTO healthsync.branches VALUES
('10000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000001','Santiago Centro','America/Santiago');
INSERT INTO healthsync.specialties VALUES
('10000000-0000-4000-8000-000000000001','30000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000001','medical','Medicina general');
INSERT INTO healthsync.resources VALUES
('10000000-0000-4000-8000-000000000001','40000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000001','30000000-0000-4000-8000-000000000001','Dra. Andrea Demo',true);
INSERT INTO healthsync.services VALUES
('10000000-0000-4000-8000-000000000001','50000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000001','30000000-0000-4000-8000-000000000001','Consulta de medicina general',30,15,true);
INSERT INTO healthsync.resource_services VALUES
('10000000-0000-4000-8000-000000000001','40000000-0000-4000-8000-000000000001','50000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000001','30000000-0000-4000-8000-000000000001');
INSERT INTO healthsync.availability_rules (tenant_id,resource_id,iso_weekday,opens_at,closes_at)
SELECT '10000000-0000-4000-8000-000000000001','40000000-0000-4000-8000-000000000001',d,'08:00','20:00' FROM generate_series(1,7) d;
-- sha256() is a built-in bytea hash. Each version is an immutable document snapshot.
INSERT INTO healthsync.legal_documents (tenant_id,kind,version,body,body_sha256)
SELECT '10000000-0000-4000-8000-000000000001',kind,'demo-1',body,sha256(convert_to(body,'UTF8'))
FROM (VALUES
('terms','DEMOSTRACIÓN: condiciones de reserva. Este texto requiere revisión jurídica antes de producción.'),
('sensitive_data','DEMOSTRACIÓN: autorizo el tratamiento de mis datos para gestionar esta reserva. Deben detallarse responsable, finalidad, base jurídica, conservación, transferencias y derechos antes de producción.'),
('whatsapp','DEMOSTRACIÓN: acepto recordatorios por WhatsApp, con proveedor y transferencias por definir.')) AS docs(kind,body);
COMMIT;
