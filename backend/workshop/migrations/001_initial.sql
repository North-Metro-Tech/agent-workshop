-- SPDX-License-Identifier: Apache-2.0
-- Workshop-owned historian ONLY. Never run against an actor/native database.
BEGIN IMMEDIATE;
CREATE TABLE metadata (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE roles (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE feeds (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE executions (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE correlations (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE ambiguities (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE alarm_rules (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE alarm_controls (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE alarm_occurrences (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE alarm_audit (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE ingests (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
-- Atomic bounded anchor/delta projection checkpoint + redacted replay.
CREATE TABLE revisions (
    revision INTEGER PRIMARY KEY,
    state TEXT NOT NULL,
    event TEXT NOT NULL
);
CREATE TABLE snapshot_jobs (
    source TEXT PRIMARY KEY,
    token TEXT UNIQUE NOT NULL,
    payload TEXT NOT NULL
);
PRAGMA application_id = 1096239921;
PRAGMA user_version = 2;
COMMIT;
