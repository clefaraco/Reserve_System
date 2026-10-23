-- Incremental, transactional migration. Preserve existing appointments and identities.
BEGIN;
ALTER TABLE healthsync.memberships DROP CONSTRAINT memberships_role_check;
ALTER TABLE healthsync.memberships ADD CONSTRAINT memberships_role_check
  CHECK (role IN ('admin','scheduler','reception','clinician','finance','privacy'));
ALTER TABLE healthsync.appointments ADD CONSTRAINT appointment_patient_identity
  UNIQUE (tenant_id,id,patient_id);

CREATE TABLE healthsync.organization_units (
  tenant_id uuid NOT NULL REFERENCES healthsync.tenants,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  parent_id uuid,
  kind text NOT NULL CHECK (kind IN ('network','country','region','state','province','commune','agency','unit')),
  name text NOT NULL CHECK (length(name) BETWEEN 1 AND 160),
  PRIMARY KEY (tenant_id,id),
  FOREIGN KEY (tenant_id,parent_id) REFERENCES healthsync.organization_units,
  CHECK (parent_id IS DISTINCT FROM id)
);
CREATE TABLE healthsync.branch_locations (
  tenant_id uuid NOT NULL,
  branch_id uuid NOT NULL,
  organization_unit_id uuid NOT NULL,
  PRIMARY KEY (tenant_id,branch_id),
  FOREIGN KEY (tenant_id,branch_id) REFERENCES healthsync.branches,
  FOREIGN KEY (tenant_id,organization_unit_id) REFERENCES healthsync.organization_units
);
CREATE TABLE healthsync.membership_branches (
  tenant_id uuid NOT NULL,
  auth_user_id uuid NOT NULL,
  branch_id uuid NOT NULL,
  PRIMARY KEY (tenant_id,auth_user_id,branch_id),
  FOREIGN KEY (tenant_id,auth_user_id) REFERENCES healthsync.memberships,
  FOREIGN KEY (tenant_id,branch_id) REFERENCES healthsync.branches
);
CREATE TABLE healthsync.clinician_resources (
  tenant_id uuid NOT NULL,
  auth_user_id uuid NOT NULL,
  resource_id uuid NOT NULL,
  PRIMARY KEY (tenant_id,auth_user_id,resource_id),
  FOREIGN KEY (tenant_id,auth_user_id) REFERENCES healthsync.memberships,
  FOREIGN KEY (tenant_id,resource_id) REFERENCES healthsync.resources
);
CREATE TABLE healthsync.attendance_records (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  appointment_id uuid NOT NULL,
  patient_id uuid NOT NULL,
  checked_in_at timestamptz,
  completed_at timestamptz,
  outcome text CHECK (outcome IN ('completed','no_show')),
  recorded_by uuid NOT NULL,
  PRIMARY KEY (tenant_id,id),
  UNIQUE (tenant_id,appointment_id),
  FOREIGN KEY (tenant_id,appointment_id,patient_id) REFERENCES healthsync.appointments (tenant_id,id,patient_id),
  FOREIGN KEY (tenant_id,patient_id) REFERENCES healthsync.patients,
  CHECK ((outcome='completed' AND completed_at IS NOT NULL) OR (outcome IS DISTINCT FROM 'completed' AND completed_at IS NULL))
);
CREATE TABLE healthsync.appointment_events (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  appointment_id uuid NOT NULL,
  patient_id uuid NOT NULL,
  actor_id uuid,
  request_id uuid NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  previous_status text,
  status text NOT NULL,
  previous_starts_at timestamptz,
  starts_at timestamptz NOT NULL,
  version integer NOT NULL,
  PRIMARY KEY (tenant_id,id),
  FOREIGN KEY (tenant_id,appointment_id,patient_id) REFERENCES healthsync.appointments (tenant_id,id,patient_id),
  FOREIGN KEY (tenant_id,patient_id) REFERENCES healthsync.patients
);
CREATE TABLE healthsync.workspace_events (
  tenant_id uuid NOT NULL REFERENCES healthsync.tenants,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  actor_id uuid NOT NULL,
  action text NOT NULL,
  request_id uuid NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  ip_ciphertext bytea NOT NULL,
  key_id text NOT NULL,
  PRIMARY KEY (tenant_id,id)
);

CREATE FUNCTION healthsync.guard_organization_tree() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,healthsync AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended('organization:'||NEW.tenant_id::text,0));
  IF EXISTS (
    WITH RECURSIVE ancestors AS (
      SELECT id,parent_id FROM healthsync.organization_units WHERE tenant_id=NEW.tenant_id AND id=NEW.parent_id
      UNION
      SELECT u.id,u.parent_id FROM healthsync.organization_units u JOIN ancestors a ON u.id=a.parent_id
        WHERE u.tenant_id=NEW.tenant_id
    ) SELECT 1 FROM ancestors WHERE id=NEW.id
  ) THEN RAISE EXCEPTION 'Organization hierarchy cannot contain cycles'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER organization_tree BEFORE INSERT OR UPDATE ON healthsync.organization_units
  FOR EACH ROW EXECUTE FUNCTION healthsync.guard_organization_tree();

CREATE FUNCTION healthsync.record_appointment_event() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,healthsync AS $$
BEGIN
  INSERT INTO healthsync.appointment_events
    (tenant_id,appointment_id,patient_id,actor_id,request_id,previous_status,status,previous_starts_at,starts_at,version)
  VALUES (NEW.tenant_id,NEW.id,NEW.patient_id,nullif(current_setting('app.actor_id',true),'')::uuid,
    current_setting('app.request_id')::uuid,
    CASE WHEN TG_OP='UPDATE' THEN OLD.status END,NEW.status,
    CASE WHEN TG_OP='UPDATE' THEN OLD.starts_at END,NEW.starts_at,NEW.version);
  RETURN NEW;
END $$;
CREATE TRIGGER appointment_history AFTER INSERT OR UPDATE ON healthsync.appointments
  FOR EACH ROW EXECUTE FUNCTION healthsync.record_appointment_event();
CREATE TRIGGER attendance_audit AFTER INSERT OR UPDATE ON healthsync.attendance_records
  FOR EACH ROW EXECUTE FUNCTION healthsync.audit_mutation();
CREATE TRIGGER appointment_events_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON healthsync.appointment_events
  FOR EACH STATEMENT EXECUTE FUNCTION healthsync.reject_mutation();
CREATE TRIGGER workspace_events_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON healthsync.workspace_events
  FOR EACH STATEMENT EXECUTE FUNCTION healthsync.reject_mutation();

DO $$ DECLARE n text; BEGIN
  FOREACH n IN ARRAY ARRAY['organization_units','branch_locations','membership_branches','clinician_resources','attendance_records','appointment_events','workspace_events'] LOOP
    EXECUTE format('ALTER TABLE healthsync.%I ENABLE ROW LEVEL SECURITY',n);
    EXECUTE format('ALTER TABLE healthsync.%I FORCE ROW LEVEL SECURITY',n);
    EXECUTE format('CREATE POLICY tenant_boundary ON healthsync.%I FOR ALL TO healthsync_app USING (tenant_id=healthsync.current_tenant()) WITH CHECK (tenant_id=healthsync.current_tenant())',n);
    EXECUTE format('GRANT SELECT ON healthsync.%I TO healthsync_app',n);
  END LOOP;
END $$;
GRANT INSERT,UPDATE ON healthsync.attendance_records TO healthsync_app;
GRANT INSERT ON healthsync.appointment_events,healthsync.workspace_events TO healthsync_app;
REVOKE ALL ON FUNCTION healthsync.guard_organization_tree(),healthsync.record_appointment_event() FROM PUBLIC;

-- Separate SaaS control plane. Operators receive metadata access, never clinical
-- cross-tenant access. Granting this identity is an administrative operation only.
CREATE SCHEMA platform;
REVOKE ALL ON SCHEMA platform FROM PUBLIC;
GRANT USAGE ON SCHEMA platform TO healthsync_app;
CREATE TABLE platform.operators (
  tenant_id uuid NOT NULL DEFAULT '00000000-0000-4000-8000-000000000001'
    CHECK (tenant_id='00000000-0000-4000-8000-000000000001'),
  auth_user_id uuid NOT NULL,
  role text NOT NULL CHECK (role IN ('owner','support','billing')),
  active boolean NOT NULL DEFAULT true,
  PRIMARY KEY (tenant_id,auth_user_id)
);
CREATE TABLE platform.tenant_directory (
  tenant_id uuid PRIMARY KEY REFERENCES healthsync.tenants,
  name text NOT NULL,
  country char(2) NOT NULL,
  active boolean NOT NULL
);
ALTER TABLE platform.operators ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.operators FORCE ROW LEVEL SECURITY;
ALTER TABLE platform.tenant_directory ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.tenant_directory FORCE ROW LEVEL SECURITY;
CREATE POLICY own_operator_identity ON platform.operators FOR SELECT TO healthsync_app
  USING (active AND auth_user_id=nullif(current_setting('app.actor_id',true),'')::uuid);
CREATE POLICY operator_metadata_only ON platform.tenant_directory FOR SELECT TO healthsync_app
  USING (EXISTS (SELECT 1 FROM platform.operators));
GRANT SELECT ON ALL TABLES IN SCHEMA platform TO healthsync_app;

CREATE FUNCTION platform.sync_tenant_directory() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,platform AS $$
BEGIN
  INSERT INTO platform.tenant_directory VALUES (NEW.tenant_id,NEW.name,NEW.country,NEW.active)
  ON CONFLICT (tenant_id) DO UPDATE SET name=EXCLUDED.name,country=EXCLUDED.country,active=EXCLUDED.active;
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION platform.sync_tenant_directory() FROM PUBLIC;
CREATE TRIGGER tenant_directory_sync AFTER INSERT OR UPDATE ON healthsync.tenants
  FOR EACH ROW EXECUTE FUNCTION platform.sync_tenant_directory();
INSERT INTO platform.tenant_directory SELECT tenant_id,name,country,active FROM healthsync.tenants;

UPDATE healthsync.tenants SET name='Clínica de demostración'
WHERE tenant_id='10000000-0000-4000-8000-000000000001' AND name='Clínica HealthSync · Demo';
COMMIT;
