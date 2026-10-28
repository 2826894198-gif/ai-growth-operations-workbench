-- PART 07 §111-§113 — Row-level Security as defense in depth for tenant tables.
-- The application still enforces workspace membership; RLS is the backstop.

ALTER TABLE connected_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_publications ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_content_performance_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_promotion_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE focus_monitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE provider_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE brands ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_audits ENABLE ROW LEVEL SECURITY;

-- App read role sees only rows in workspaces granted via a session GUC.
CREATE POLICY workspace_isolation_read ON connected_accounts
  FOR SELECT TO growth_app_read
  USING (workspace_id = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation_read_assets ON content_assets
  FOR SELECT TO growth_app_read
  USING (workspace_id = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation_read_facts ON fact_content_performance_daily
  FOR SELECT TO growth_app_read
  USING (workspace_id = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation_read_intents ON execution_intents
  FOR SELECT TO growth_app_read
  USING (workspace_id = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation_read_audits ON execution_audits
  FOR SELECT TO growth_app_read
  USING (workspace_id = current_setting('app.workspace_id', true));

-- Execution role can mutate execution rows only in the session workspace.
CREATE POLICY workspace_isolation_write_jobs ON execution_jobs
  FOR ALL TO growth_execution
  USING (workspace_id = current_setting('app.workspace_id', true))
  WITH CHECK (workspace_id = current_setting('app.workspace_id', true));
