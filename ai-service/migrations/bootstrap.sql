-- One-off provisioning for the `ai` schema. Delivered by C05.
--
-- Run this ONCE per environment, with administrator privileges, BEFORE the
-- first `alembic upgrade head`. Migrations do not do this, and deliberately so:
--
--   * Roles are CLUSTER-level objects, not database-level ones. Creating one
--     from a migration would require role-creation privilege for whoever
--     migrates, and reverting would have to DROP a role that by then owns
--     objects -- an operation that fails. A migration that cannot be reverted
--     cleanly contradicts test_upgrade_downgrade_is_reversible.
--
--   * On RDS the extension is installed by the master user (C05 does not touch
--     production; that is C17). Because the migration declares the extension
--     with IF NOT EXISTS, the same DATABASE_URL works in both worlds: locally
--     this script installs it, on RDS the migration finds it already there.
--
-- Usage (local Compose):
--   docker exec -i jpv-pv-postgres psql -U postgres -d joiabagur_pv \
--     -v ai_password=<password> < migrations/bootstrap.sql
--
-- Pass the password RAW, without quoting it yourself: psql's :'var' already
-- renders it as a quoted literal, so pre-quoting produces a password that
-- literally contains apostrophes and then fails to authenticate.
--
-- The password is passed as a psql variable so it never lives in this file.
-- In production it comes from SSM /jpv/prod/* (C17).
--
-- An existing role keeps its password on purpose: re-running this script must
-- never silently rotate a production credential. Change it deliberately with
-- ALTER ROLE jbg_ai PASSWORD '...'.

\set ON_ERROR_STOP on

-- 1. The extension. Installed in the default schema (`public`) on purpose.
--    Installing it into `ai` would force every column type to be qualified as
--    ai.vector(1536) and every connection to carry a search_path -- forever,
--    including external tooling. The ownership boundary of design section 6.3
--    is about DATA, not about where an extension's types are registered.
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. The schema Python owns.
CREATE SCHEMA IF NOT EXISTS ai;

-- 3. The dedicated role. Distinct from the one the .NET API uses.
--
--    Written with psql's own conditional rather than a DO block: psql does NOT
--    substitute :'variables' inside dollar-quoted strings, so the password
--    would arrive at the server as the literal text ":'ai_password'".
SELECT NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'jbg_ai') AS role_missing \gset

\if :role_missing
CREATE ROLE jbg_ai LOGIN PASSWORD :'ai_password';
\echo 'role jbg_ai created'
\else
\echo 'role jbg_ai already exists, password left untouched'
\endif

-- 4. Least privilege.
--
--    On `ai`: USAGE and CREATE, because this same role runs the migrations.
GRANT USAGE, CREATE ON SCHEMA ai TO jbg_ai;
ALTER DEFAULT PRIVILEGES IN SCHEMA ai
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO jbg_ai;
ALTER DEFAULT PRIVILEGES IN SCHEMA ai
    GRANT USAGE, SELECT ON SEQUENCES TO jbg_ai;

--    On `public`: USAGE only, and only so the `vector` type resolves. No SELECT
--    on any table. Python never reads the business schema by SQL -- it reads it
--    over HTTP through the paginated feeds of C12.
GRANT USAGE ON SCHEMA public TO jbg_ai;
REVOKE CREATE ON SCHEMA public FROM jbg_ai;

-- 5. Make the boundary the default rather than a convention: new objects the
--    .NET side creates in `public` must not become readable by this role.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM jbg_ai;

DO $$
BEGIN
    RAISE NOTICE 'ai schema provisioned; run `alembic upgrade head` next';
END
$$;
