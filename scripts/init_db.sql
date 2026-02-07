-- Initialize TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Database will be created by Docker (cousin_eddie)
-- This script runs after database creation

-- Create a test table to verify TimescaleDB is working
CREATE TABLE IF NOT EXISTS _timescale_test (
    time TIMESTAMPTZ NOT NULL,
    value DOUBLE PRECISION
);

-- Convert to hypertable (will fail silently if already exists)
SELECT create_hypertable('_timescale_test', 'time', if_not_exists => TRUE);

-- The main tables (companies, signals) will be created by SQLAlchemy
-- But we need to convert signals to a hypertable after it's created
-- This will be done in a migration script
