-- PART 07 §76-§78 — database roles with least privilege.
-- Execution write credentials are isolated from read/analytics and migrations.

\set ON_ERROR_STOP on

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'growth_app_read') THEN
    CREATE ROLE growth_app_read;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'growth_execution') THEN
    CREATE ROLE growth_execution;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'growth_migration') THEN
    CREATE ROLE growth_migration;
  END IF;
END $$;

GRANT CONNECT ON DATABASE growth TO growth_app_read, growth_execution;
GRANT USAGE ON SCHEMA public TO growth_app_read, growth_execution;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO growth_app_read;
GRANT SELECT, INSERT, UPDATE ON execution_intents, execution_jobs, execution_approvals,
      execution_events, execution_audits, execution_compensations, execution_outcomes,
      job_runs, job_attempts, job_events, outbox_messages TO growth_execution;
GRANT ALL PRIVILEGES ON DATABASE growth TO growth_migration;
