-- Run once as a migration owner, NEVER as the API role. PostgreSQL 15+ / Supabase.
BEGIN;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE SCHEMA healthsync;
REVOKE ALL ON SCHEMA healthsync FROM PUBLIC;
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'healthsync_app') THEN
    CREATE ROLE healthsync_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
  END IF;
END $$;
GRANT USAGE ON SCHEMA healthsync TO healthsync_app;

CREATE FUNCTION healthsync.current_tenant() RETURNS uuid
LANGUAGE sql STABLE SET search_path = pg_catalog AS $$
  SELECT nullif(current_setting('app.tenant_id', true), '')::uuid
$$;

CREATE TABLE healthsync.tenants (
  tenant_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  country char(2) NOT NULL CHECK (country IN ('CL','BR','AR')),
  cancel_cutoff_minutes integer NOT NULL DEFAULT 120 CHECK (cancel_cutoff_minutes >= 0),
  reschedule_cutoff_minutes integer NOT NULL DEFAULT 120 CHECK (reschedule_cutoff_minutes >= 0),
  active boolean NOT NULL DEFAULT true
);
CREATE TABLE healthsync.tenant_modules (
  tenant_id uuid NOT NULL REFERENCES healthsync.tenants,
  code text NOT NULL CHECK (code IN ('medical','dental','laboratory','physiotherapy','vault')),
  enabled boolean NOT NULL DEFAULT false,
  PRIMARY KEY (tenant_id, code)
);
CREATE TABLE healthsync.memberships (
  tenant_id uuid NOT NULL REFERENCES healthsync.tenants,
  auth_user_id uuid NOT NULL, -- Supabase Auth sub; deliberately not a globally exposed user table
  role text NOT NULL CHECK (role IN ('admin','scheduler','clinician','privacy')),
  active boolean NOT NULL DEFAULT true,
  PRIMARY KEY (tenant_id, auth_user_id)
);
CREATE TABLE healthsync.branches (
  tenant_id uuid NOT NULL REFERENCES healthsync.tenants,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL,
  timezone text NOT NULL, -- API validates via zoneinfo; e.g. America/Santiago
  PRIMARY KEY (tenant_id, id)
);
CREATE TABLE healthsync.specialties (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  branch_id uuid NOT NULL,
  module_code text NOT NULL,
  name text NOT NULL,
  PRIMARY KEY (tenant_id, id),
  UNIQUE (tenant_id, branch_id, id),
  FOREIGN KEY (tenant_id, branch_id) REFERENCES healthsync.branches,
  FOREIGN KEY (tenant_id, module_code) REFERENCES healthsync.tenant_modules
);
CREATE TABLE healthsync.resources (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  branch_id uuid NOT NULL,
  specialty_id uuid NOT NULL,
  public_name text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  PRIMARY KEY (tenant_id, id),
  UNIQUE (tenant_id, id, branch_id, specialty_id),
  FOREIGN KEY (tenant_id, branch_id, specialty_id)
    REFERENCES healthsync.specialties (tenant_id, branch_id, id)
);
CREATE TABLE healthsync.services (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  branch_id uuid NOT NULL,
  specialty_id uuid NOT NULL,
  name text NOT NULL,
  duration_minutes integer NOT NULL CHECK (duration_minutes BETWEEN 5 AND 480),
  buffer_minutes integer NOT NULL DEFAULT 0 CHECK (buffer_minutes BETWEEN 0 AND 240),
  active boolean NOT NULL DEFAULT true,
  PRIMARY KEY (tenant_id, id),
  UNIQUE (tenant_id, id, branch_id, specialty_id),
  FOREIGN KEY (tenant_id, branch_id, specialty_id)
    REFERENCES healthsync.specialties (tenant_id, branch_id, id)
);
CREATE TABLE healthsync.resource_services (
  tenant_id uuid NOT NULL,
  resource_id uuid NOT NULL,
  service_id uuid NOT NULL,
  branch_id uuid NOT NULL,
  specialty_id uuid NOT NULL,
  PRIMARY KEY (tenant_id, resource_id, service_id),
  FOREIGN KEY (tenant_id, resource_id, branch_id, specialty_id)
    REFERENCES healthsync.resources (tenant_id, id, branch_id, specialty_id),
  FOREIGN KEY (tenant_id, service_id, branch_id, specialty_id)
    REFERENCES healthsync.services (tenant_id, id, branch_id, specialty_id)
);
CREATE TABLE healthsync.availability_rules (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  resource_id uuid NOT NULL,
  iso_weekday integer NOT NULL CHECK (iso_weekday BETWEEN 1 AND 7),
  opens_at time NOT NULL,
  closes_at time NOT NULL,
  CHECK (closes_at > opens_at), -- overnight shifts use two rules
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, resource_id) REFERENCES healthsync.resources
);
CREATE TABLE healthsync.resource_blocks (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  resource_id uuid NOT NULL,
  starts_at timestamptz NOT NULL,
  ends_at timestamptz NOT NULL CHECK (ends_at > starts_at),
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, resource_id) REFERENCES healthsync.resources
);

CREATE TABLE healthsync.patients (
  tenant_id uuid NOT NULL REFERENCES healthsync.tenants,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  auth_user_id uuid,
  pii_ciphertext bytea, -- AES-256-GCM JSON: name, email; phone only for opted-in WhatsApp
  pii_key_id text,
  email_hmac bytea, -- tenant-scoped keyed index; never a plain email hash
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  deleted_at timestamptz,
  anonymized_at timestamptz,
  retention_until timestamptz,
  legal_hold boolean NOT NULL DEFAULT false,
  PRIMARY KEY (tenant_id, id),
  CHECK ((anonymized_at IS NULL AND pii_ciphertext IS NOT NULL AND pii_key_id IS NOT NULL)
    OR (anonymized_at IS NOT NULL AND pii_ciphertext IS NULL AND pii_key_id IS NULL
      AND email_hmac IS NULL AND auth_user_id IS NULL AND deleted_at IS NOT NULL))
);
CREATE INDEX patients_subject ON healthsync.patients (tenant_id, auth_user_id)
  WHERE deleted_at IS NULL;

CREATE TABLE healthsync.care_relationships (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL,
  clinician_id uuid NOT NULL,
  granted_by uuid NOT NULL,
  valid_until timestamptz NOT NULL,
  revoked_at timestamptz,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, patient_id) REFERENCES healthsync.patients,
  FOREIGN KEY (tenant_id, clinician_id) REFERENCES healthsync.memberships (tenant_id, auth_user_id)
);

CREATE TABLE healthsync.legal_documents (
  tenant_id uuid NOT NULL REFERENCES healthsync.tenants,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  kind text NOT NULL CHECK (kind IN ('terms','sensitive_data','whatsapp')),
  version text NOT NULL,
  locale text NOT NULL DEFAULT 'es-CL',
  body text NOT NULL,
  body_sha256 bytea NOT NULL CHECK (octet_length(body_sha256) = 32),
  published_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  active boolean NOT NULL DEFAULT true,
  PRIMARY KEY (tenant_id, id),
  UNIQUE (tenant_id, kind, version, locale)
);
CREATE TABLE healthsync.consents (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL,
  document_id uuid NOT NULL,
  accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  withdrawn_at timestamptz,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, patient_id) REFERENCES healthsync.patients,
  FOREIGN KEY (tenant_id, document_id) REFERENCES healthsync.legal_documents
  -- IP evidence is in the immutable acceptance audit event's privacy_context.
);
CREATE TABLE healthsync.appointments (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL,
  resource_id uuid NOT NULL,
  service_id uuid NOT NULL,
  starts_at timestamptz NOT NULL,
  ends_at timestamptz NOT NULL,
  occupied_until timestamptz NOT NULL,
  duration_minutes integer NOT NULL CHECK (duration_minutes > 0),
  buffer_minutes integer NOT NULL CHECK (buffer_minutes >= 0),
  status text NOT NULL DEFAULT 'booked' CHECK (status IN ('booked','confirmed','cancelled','completed','no_show')),
  version integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, patient_id) REFERENCES healthsync.patients,
  FOREIGN KEY (tenant_id, resource_id, service_id) REFERENCES healthsync.resource_services,
  CHECK (ends_at = starts_at + duration_minutes * interval '1 minute'),
  CHECK (occupied_until = ends_at + buffer_minutes * interval '1 minute'),
  -- tsrange stores canonical UTC wall times. API only accepts offset-aware timestamps.
  slot tsrange GENERATED ALWAYS AS
    (tsrange(starts_at AT TIME ZONE 'UTC', occupied_until AT TIME ZONE 'UTC', '[)')) STORED,
  CONSTRAINT appointments_no_overlap EXCLUDE USING gist
    (tenant_id WITH =, resource_id WITH =, slot WITH &&)
    WHERE (status IN ('booked','confirmed','completed','no_show'))
);
CREATE INDEX appointments_patient ON healthsync.appointments (tenant_id, patient_id, starts_at);

CREATE TABLE healthsync.booking_commands (
  tenant_id uuid NOT NULL REFERENCES healthsync.tenants,
  idempotency_key uuid NOT NULL,
  request_hmac bytea NOT NULL,
  appointment_id uuid NOT NULL,
  PRIMARY KEY (tenant_id, idempotency_key),
  FOREIGN KEY (tenant_id, appointment_id) REFERENCES healthsync.appointments
);
CREATE TABLE healthsync.account_enrollments (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL,
  expires_at timestamptz NOT NULL DEFAULT (clock_timestamp() + interval '24 hours'),
  claimed_at timestamptz,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, patient_id) REFERENCES healthsync.patients
);
CREATE TABLE healthsync.outbox (
  tenant_id uuid NOT NULL REFERENCES healthsync.tenants,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL,
  appointment_id uuid,
  appointment_version integer,
  kind text NOT NULL CHECK (kind IN ('booking_created','booking_changed','booking_cancelled','reminder_24h','reminder_2h','account_magic_link')),
  channel text NOT NULL CHECK (channel IN ('email','whatsapp')),
  due_at timestamptz NOT NULL,
  delivered_at timestamptz,
  cancelled_at timestamptz,
  attempts integer NOT NULL DEFAULT 0,
  last_error_code text,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, patient_id) REFERENCES healthsync.patients,
  FOREIGN KEY (tenant_id, appointment_id) REFERENCES healthsync.appointments,
  UNIQUE (tenant_id, appointment_id, appointment_version, kind, channel)
);
CREATE INDEX outbox_due ON healthsync.outbox (tenant_id, due_at)
  WHERE delivered_at IS NULL AND cancelled_at IS NULL;
CREATE TABLE healthsync.privacy_requests (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL,
  requested_by uuid NOT NULL,
  kind text NOT NULL CHECK (kind IN ('anonymize','rectify','oppose','withdraw_consent')),
  state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','approved','rejected','completed')),
  requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  decided_by uuid,
  completed_at timestamptz,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, patient_id) REFERENCES healthsync.patients
);
CREATE UNIQUE INDEX privacy_request_pending ON healthsync.privacy_requests (tenant_id, patient_id, kind)
  WHERE state IN ('pending','approved');
CREATE TABLE healthsync.exam_results (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL,
  object_key text NOT NULL, -- random opaque key, never a patient name or public URL
  uploaded_by uuid NOT NULL,
  content_sha256 bytea NOT NULL CHECK (octet_length(content_sha256) = 32),
  byte_size bigint NOT NULL CHECK (byte_size BETWEEN 1 AND 20971520),
  scan_status text NOT NULL DEFAULT 'quarantine' CHECK (scan_status IN ('quarantine','clean','rejected')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  deleted_at timestamptz,
  PRIMARY KEY (tenant_id, id),
  UNIQUE (tenant_id, object_key),
  FOREIGN KEY (tenant_id, patient_id) REFERENCES healthsync.patients
);

-- IPs are PII: separable, encrypted evidence. Erasure clears these bytes without
-- altering audit events. Preserve evidence under documented legal retention/hold.
CREATE TABLE healthsync.privacy_contexts (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL,
  ip_ciphertext bytea,
  key_id text,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, patient_id) REFERENCES healthsync.patients
);
CREATE TABLE healthsync.audit_events (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL,
  actor_id uuid,
  actor_type text NOT NULL CHECK (actor_type IN ('guest','user','worker')),
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  request_id uuid NOT NULL,
  action text NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  privacy_context_id uuid NOT NULL,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, patient_id) REFERENCES healthsync.patients,
  FOREIGN KEY (tenant_id, privacy_context_id) REFERENCES healthsync.privacy_contexts
);
CREATE INDEX audit_patient ON healthsync.audit_events (tenant_id, patient_id, occurred_at);

CREATE FUNCTION healthsync.append_audit(
  p_patient uuid, p_action text, p_entity text, p_id uuid
) RETURNS void LANGUAGE plpgsql SET search_path = pg_catalog, healthsync AS $$
DECLARE c uuid := gen_random_uuid(); t uuid := healthsync.current_tenant();
BEGIN
  IF nullif(current_setting('app.request_id', true), '') IS NULL THEN
    RAISE EXCEPTION 'Audit context is required';
  END IF;
  INSERT INTO healthsync.privacy_contexts(tenant_id,id,patient_id,ip_ciphertext,key_id)
    VALUES (t,c,p_patient,decode(nullif(current_setting('app.ip_ciphertext',true),''),'hex'),
      nullif(current_setting('app.ip_key_id',true),''));
  INSERT INTO healthsync.audit_events
    (tenant_id,patient_id,actor_id,actor_type,request_id,action,entity_type,entity_id,privacy_context_id)
    VALUES (t,p_patient,nullif(current_setting('app.actor_id',true),'')::uuid,
      coalesce(nullif(current_setting('app.actor_type',true),''),'guest'),
      current_setting('app.request_id')::uuid,p_action,p_entity,p_id,c);
END $$;
CREATE FUNCTION healthsync.audit_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, healthsync AS $$
DECLARE p uuid;
BEGIN
  IF TG_TABLE_NAME = 'patients' THEN p := NEW.id;
  ELSE p := NEW.patient_id; END IF;
  PERFORM healthsync.append_audit(p, TG_OP, TG_TABLE_NAME, NEW.id);
  RETURN NEW;
END $$;
CREATE FUNCTION healthsync.reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Append-only evidence cannot be changed'; END $$;

DO $$ DECLARE n text; BEGIN
  -- RLS is enforced even for ordinary table owners. Never run API as owner/postgres/service_role.
  FOR n IN SELECT tablename FROM pg_tables WHERE schemaname = 'healthsync' LOOP
    EXECUTE format('ALTER TABLE healthsync.%I ENABLE ROW LEVEL SECURITY',n);
    EXECUTE format('ALTER TABLE healthsync.%I FORCE ROW LEVEL SECURITY',n);
    EXECUTE format('CREATE POLICY tenant_boundary ON healthsync.%I FOR ALL TO healthsync_app USING (tenant_id = healthsync.current_tenant()) WITH CHECK (tenant_id = healthsync.current_tenant())',n);
  END LOOP;
  FOREACH n IN ARRAY ARRAY['patients','care_relationships','consents','appointments','account_enrollments','outbox','privacy_requests','exam_results'] LOOP
    EXECUTE format('CREATE TRIGGER audit_write AFTER INSERT OR UPDATE ON healthsync.%I FOR EACH ROW EXECUTE FUNCTION healthsync.audit_mutation()',n);
  END LOOP;
END $$;
CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON healthsync.audit_events
  FOR EACH STATEMENT EXECUTE FUNCTION healthsync.reject_mutation();
CREATE TRIGGER documents_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON healthsync.legal_documents
  FOR EACH STATEMENT EXECUTE FUNCTION healthsync.reject_mutation();

-- Least privilege. No browser (anon/authenticated) grants; FastAPI is the only data gateway.
GRANT SELECT ON ALL TABLES IN SCHEMA healthsync TO healthsync_app;
GRANT INSERT, UPDATE ON healthsync.patients, healthsync.consents, healthsync.appointments,
  healthsync.account_enrollments, healthsync.outbox, healthsync.privacy_requests,
  healthsync.exam_results, healthsync.privacy_contexts TO healthsync_app;
GRANT INSERT ON healthsync.audit_events, healthsync.booking_commands TO healthsync_app;
GRANT UPDATE (revoked_at) ON healthsync.care_relationships TO healthsync_app;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA healthsync FROM PUBLIC;
GRANT EXECUTE ON FUNCTION healthsync.current_tenant(),
  healthsync.append_audit(uuid,text,text,uuid) TO healthsync_app;
-- No DELETE/TRUNCATE, DDL, role membership, or BYPASSRLS for the runtime role.
COMMIT;
