-- Additive migration: no clinical rows, history, keys or prior grants removed.
BEGIN;
CREATE TABLE healthsync.staff_contacts (
 tenant_id uuid NOT NULL REFERENCES healthsync.tenants,
 id uuid NOT NULL DEFAULT gen_random_uuid(),
 email_hmac bytea NOT NULL,
 email_ciphertext bytea NOT NULL,
 key_id text NOT NULL,
 PRIMARY KEY (tenant_id,id), UNIQUE (tenant_id,email_hmac)
);
ALTER TABLE healthsync.memberships ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK(version>0);
ALTER TABLE healthsync.memberships ADD COLUMN contact_id uuid;
ALTER TABLE healthsync.memberships ADD FOREIGN KEY(tenant_id,contact_id) REFERENCES healthsync.staff_contacts;
CREATE UNIQUE INDEX one_staff_contact_membership ON healthsync.memberships(tenant_id,contact_id) WHERE contact_id IS NOT NULL;
CREATE TABLE healthsync.staff_invitations (
 tenant_id uuid NOT NULL REFERENCES healthsync.tenants,
 id uuid NOT NULL DEFAULT gen_random_uuid(),
 contact_id uuid NOT NULL,
 role text NOT NULL CHECK(role IN ('admin','scheduler','reception','clinician','finance','privacy')),
 token_hash bytea NOT NULL CHECK(octet_length(token_hash)=32),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL DEFAULT clock_timestamp()+interval '48 hours',
 revoked_at timestamptz,
 accepted_at timestamptz,
 accepted_by uuid,
 version integer NOT NULL DEFAULT 1 CHECK(version>0),
 PRIMARY KEY (tenant_id,id), UNIQUE(tenant_id,token_hash),
 FOREIGN KEY(tenant_id,contact_id) REFERENCES healthsync.staff_contacts,
 CHECK(expires_at>created_at), CHECK((accepted_at IS NULL)=(accepted_by IS NULL)),
 CHECK(accepted_at IS NULL OR revoked_at IS NULL)
);
CREATE UNIQUE INDEX one_pending_staff_invitation ON healthsync.staff_invitations(tenant_id,contact_id)
 WHERE revoked_at IS NULL AND accepted_at IS NULL;
CREATE TABLE healthsync.invitation_branches (
 tenant_id uuid NOT NULL, invitation_id uuid NOT NULL, branch_id uuid NOT NULL,
 PRIMARY KEY(tenant_id,invitation_id,branch_id),
 FOREIGN KEY(tenant_id,invitation_id) REFERENCES healthsync.staff_invitations,
 FOREIGN KEY(tenant_id,branch_id) REFERENCES healthsync.branches
);
CREATE TABLE healthsync.invitation_resources (
 tenant_id uuid NOT NULL, invitation_id uuid NOT NULL, resource_id uuid NOT NULL,
 PRIMARY KEY(tenant_id,invitation_id,resource_id),
 FOREIGN KEY(tenant_id,invitation_id) REFERENCES healthsync.staff_invitations,
 FOREIGN KEY(tenant_id,resource_id) REFERENCES healthsync.resources
);
-- Durable invitations are independent of patient outbox; provider acceptance is NOT delivery.
CREATE TABLE healthsync.staff_deliveries (
 tenant_id uuid NOT NULL, id uuid NOT NULL DEFAULT gen_random_uuid(), invitation_id uuid NOT NULL,
 token_ciphertext bytea NOT NULL, key_id text NOT NULL,
 state text NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','accepted','delivered','failed','unknown','superseded')),
 provider_id text, attempts integer NOT NULL DEFAULT 0,
 due_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 accepted_at timestamptz, delivered_at timestamptz, error_code text,
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,invitation_id),
 FOREIGN KEY(tenant_id,invitation_id) REFERENCES healthsync.staff_invitations,
 CHECK(state<>'delivered' OR delivered_at IS NOT NULL)
);
CREATE UNIQUE INDEX staff_provider_message ON healthsync.staff_deliveries(tenant_id,provider_id) WHERE provider_id IS NOT NULL;
CREATE TABLE healthsync.staff_events (
 tenant_id uuid NOT NULL REFERENCES healthsync.tenants, id uuid NOT NULL DEFAULT gen_random_uuid(),
 actor_id uuid, action text NOT NULL, entity text NOT NULL, entity_id text NOT NULL,
 request_id uuid NOT NULL, occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 changes jsonb NOT NULL DEFAULT '{}', ip_ciphertext bytea, key_id text,
 PRIMARY KEY(tenant_id,id)
);
CREATE FUNCTION healthsync.record_staff_event() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,healthsync AS $$
DECLARE v jsonb; oldv jsonb; changes jsonb := '{}';
BEGIN
 v := CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
 IF TG_OP='UPDATE' THEN oldv:=to_jsonb(OLD); END IF;
 -- Explicit allowlist: no contact ciphertext, hashes, token, destination or provider content.
 SELECT coalesce(jsonb_object_agg(key,value),'{}') INTO changes FROM jsonb_each(v)
 WHERE key IN ('role','active','version','branch_id','resource_id','state','accepted_by','revoked_at','accepted_at');
 INSERT INTO healthsync.staff_events(tenant_id,actor_id,action,entity,entity_id,request_id,changes,ip_ciphertext,key_id)
 VALUES ((v->>'tenant_id')::uuid,nullif(current_setting('app.actor_id',true),'')::uuid,TG_OP,TG_TABLE_NAME,
 coalesce(v->>'id',v->>'auth_user_id',v->>'invitation_id'),current_setting('app.request_id')::uuid,
 jsonb_build_object('after',changes,'previous_role',oldv->>'role','previous_active',oldv->'active'),
 decode(nullif(current_setting('app.ip_ciphertext',true),''),'hex'),nullif(current_setting('app.ip_key_id',true),''));
 RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$;
CREATE FUNCTION healthsync.protect_last_admin() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,healthsync AS $$
BEGIN
 IF OLD.active AND OLD.role='admin' AND (TG_OP='DELETE' OR NOT NEW.active OR NEW.role<>'admin') THEN
   PERFORM pg_advisory_xact_lock(hashtextextended('staff-access:'||OLD.tenant_id::text,0));
   IF NOT EXISTS(SELECT 1 FROM healthsync.memberships WHERE tenant_id=OLD.tenant_id AND active AND role='admin'
      AND auth_user_id<>OLD.auth_user_id) THEN
     RAISE EXCEPTION 'LAST_ACTIVE_ADMIN' USING ERRCODE='23514';
   END IF;
 END IF;
 RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$;
CREATE TRIGGER last_admin BEFORE UPDATE OR DELETE ON healthsync.memberships
 FOR EACH ROW EXECUTE FUNCTION healthsync.protect_last_admin();
CREATE TRIGGER staff_events_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON healthsync.staff_events
 FOR EACH STATEMENT EXECUTE FUNCTION healthsync.reject_mutation();
DO $$ DECLARE n text; BEGIN
 FOREACH n IN ARRAY ARRAY['staff_contacts','staff_invitations','invitation_branches','invitation_resources','staff_deliveries','staff_events'] LOOP
  EXECUTE format('ALTER TABLE healthsync.%I ENABLE ROW LEVEL SECURITY',n);
  EXECUTE format('ALTER TABLE healthsync.%I FORCE ROW LEVEL SECURITY',n);
  EXECUTE format('CREATE POLICY tenant_boundary ON healthsync.%I FOR ALL TO healthsync_app USING(tenant_id=healthsync.current_tenant()) WITH CHECK(tenant_id=healthsync.current_tenant())',n);
  EXECUTE format('GRANT SELECT,INSERT ON healthsync.%I TO healthsync_app',n);
 END LOOP;
 FOREACH n IN ARRAY ARRAY['memberships','membership_branches','clinician_resources','staff_contacts','staff_invitations','invitation_branches','invitation_resources','staff_deliveries'] LOOP
  EXECUTE format('CREATE TRIGGER staff_audit AFTER INSERT OR UPDATE OR DELETE ON healthsync.%I FOR EACH ROW EXECUTE FUNCTION healthsync.record_staff_event()',n);
 END LOOP;
END $$;
GRANT INSERT,UPDATE ON healthsync.memberships TO healthsync_app;
GRANT INSERT,DELETE ON healthsync.membership_branches,healthsync.clinician_resources TO healthsync_app;
GRANT UPDATE ON healthsync.staff_invitations,healthsync.staff_deliveries TO healthsync_app;
REVOKE ALL ON FUNCTION healthsync.record_staff_event(),healthsync.protect_last_admin() FROM PUBLIC;
COMMIT;
