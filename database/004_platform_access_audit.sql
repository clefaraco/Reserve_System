BEGIN;
CREATE TABLE platform.operator_events (
  tenant_id uuid NOT NULL DEFAULT '00000000-0000-4000-8000-000000000001'
    CHECK (tenant_id='00000000-0000-4000-8000-000000000001'),
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  actor_id uuid NOT NULL,
  action text NOT NULL,
  request_id uuid NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  ip_ciphertext bytea NOT NULL,
  key_id text NOT NULL,
  PRIMARY KEY (tenant_id,id),
  FOREIGN KEY (tenant_id,actor_id) REFERENCES platform.operators (tenant_id,auth_user_id)
);
ALTER TABLE platform.operator_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.operator_events FORCE ROW LEVEL SECURITY;
CREATE POLICY own_operator_events ON platform.operator_events FOR ALL TO healthsync_app
  USING (actor_id=nullif(current_setting('app.actor_id',true),'')::uuid AND EXISTS (SELECT 1 FROM platform.operators))
  WITH CHECK (actor_id=nullif(current_setting('app.actor_id',true),'')::uuid AND EXISTS (SELECT 1 FROM platform.operators));
GRANT SELECT,INSERT ON platform.operator_events TO healthsync_app;
CREATE TRIGGER operator_events_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON platform.operator_events
  FOR EACH STATEMENT EXECUTE FUNCTION healthsync.reject_mutation();
COMMIT;
