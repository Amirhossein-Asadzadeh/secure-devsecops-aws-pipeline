-- Migration: 001_initial_schema
-- Description: Create the initial items table
-- Applied by: app/migrations/migrate.py

-- ---------------------------------------------------------------------------
-- Schema migrations tracking table
--
-- Records every migration that has been applied so the runner can skip files
-- that are already present in the database (idempotent, safe to re-run).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(255) PRIMARY KEY,          -- filename without .sql, e.g. "001_initial_schema"
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()  -- wall-clock time the migration ran
);

-- ---------------------------------------------------------------------------
-- Items table
--
-- Stores the application items managed via the REST API.
--
-- Columns:
--   id         - auto-incrementing surrogate key
--   name       - human-readable label (required, max 255 chars)
--   status     - lifecycle state; defaults to 'active'
--   created_at - immutable creation timestamp, stored in UTC
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS items (
    id         SERIAL       PRIMARY KEY,
    name       VARCHAR(255) NOT NULL,
    status     VARCHAR(50)  NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Index to support common query patterns
CREATE INDEX IF NOT EXISTS idx_items_status     ON items (status);
CREATE INDEX IF NOT EXISTS idx_items_created_at ON items (created_at DESC);
