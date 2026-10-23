-- Uptime Desk schema for Aurora PostgreSQL (also used by the local Postgres test container).
-- Deterministic code owns every status change; the LLM only fills draft text fields that the
-- diagnosis policy has already verified.

CREATE TABLE IF NOT EXISTS sites (
    site_id            text PRIMARY KEY,
    name               text NOT NULL,
    town               text NOT NULL,
    lat                double precision NOT NULL,
    lon                double precision NOT NULL,
    criticality        text NOT NULL CHECK (criticality IN ('critical', 'high', 'standard')),
    sla_response_hours integer NOT NULL CHECK (sla_response_hours > 0),
    badge_required     boolean NOT NULL,
    escort_required    boolean NOT NULL,
    allowed_hours      text NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    asset_id         text PRIMARY KEY,
    site_id          text NOT NULL REFERENCES sites(site_id),
    equipment_class  text NOT NULL,
    description      text NOT NULL,
    lbnl_unit        text NOT NULL,
    brick_model      text
);

CREATE TABLE IF NOT EXISTS technicians (
    technician_id    text PRIMARY KEY,
    cognito_sub      text UNIQUE,                 -- set when the technician signs in
    name             text NOT NULL,
    home             text NOT NULL,
    lat              double precision NOT NULL,
    lon              double precision NOT NULL,
    certs            text[] NOT NULL,
    shift            text NOT NULL,               -- "HH:MM-HH:MM", local time
    days             text[] NOT NULL,
    site_access      text[] NOT NULL,
    escort_cleared   boolean NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_history (
    history_id       bigserial PRIMARY KEY,
    asset_id         text NOT NULL REFERENCES assets(asset_id),
    occurred_at      timestamptz NOT NULL,
    kind             text NOT NULL CHECK (kind IN ('detection', 'diagnosis', 'work_order', 'dispatch', 'note')),
    summary          text NOT NULL,
    source_ref       text NOT NULL                -- report file, case id, or work order id this row came from
);
CREATE INDEX IF NOT EXISTS asset_history_asset_time ON asset_history (asset_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS work_orders (
    work_order_id    text PRIMARY KEY,
    asset_id         text NOT NULL REFERENCES assets(asset_id),
    case_id          text NOT NULL,
    created_at       timestamptz NOT NULL,
    status           text NOT NULL CHECK (status IN ('draft', 'blocked', 'approved', 'rejected', 'escalated',
                                                     'assigned', 'escalated_unassigned', 'reschedule_requested')),
    status_reason    text,
    priority         text NOT NULL CHECK (priority IN ('P1', 'P2', 'P3')),
    sla_due_at       timestamptz NOT NULL,
    fault_type       text NOT NULL,
    route            text NOT NULL CHECK (route IN ('technician', 'operations_review', 'manual_review')),
    required_certs   text[] NOT NULL,
    est_minutes      integer NOT NULL,
    compatibility_uncertain boolean NOT NULL,
    detection_disagreement  boolean NOT NULL,
    approval_deadline_at timestamptz,
    approved_by      text,
    approved_at      timestamptz,
    edited           boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS work_orders_status ON work_orders (status);

-- Every instruction on a work order is a verbatim manual quote with its source. No free text.
CREATE TABLE IF NOT EXISTS work_order_steps (
    step_id          bigserial PRIMARY KEY,
    work_order_id    text NOT NULL REFERENCES work_orders(work_order_id) ON DELETE CASCADE,
    kind             text NOT NULL CHECK (kind IN ('safety', 'check', 'citation')),
    seq              integer NOT NULL,
    quote            text NOT NULL,
    manual_id        text NOT NULL,
    page             integer NOT NULL CHECK (page > 0),
    verified         boolean NOT NULL CHECK (verified),   -- only verified quotes may be stored
    UNIQUE (work_order_id, kind, seq)
);

CREATE TABLE IF NOT EXISTS dispatch_decisions (
    decision_id      bigserial PRIMARY KEY,
    work_order_id    text NOT NULL REFERENCES work_orders(work_order_id),
    decided_at       timestamptz NOT NULL,
    method           text NOT NULL CHECK (method IN ('ortools', 'nearest_qualified', 'earliest_available')),
    technician_id    text REFERENCES technicians(technician_id),
    runner_up_id     text REFERENCES technicians(technician_id),
    start_at         timestamptz,
    travel_minutes   double precision,
    lateness_minutes double precision,
    reason           text NOT NULL,
    scenario_id      text                         -- set for scenario model runs; null for live dispatch
);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id         bigserial PRIMARY KEY,
    occurred_at      timestamptz NOT NULL DEFAULT now(),
    actor            text NOT NULL,               -- cognito sub, technician id, or 'system'
    actor_role       text NOT NULL CHECK (actor_role IN ('manager', 'technician', 'system')),
    action           text NOT NULL,
    resource         text NOT NULL,
    allowed          boolean NOT NULL,
    detail           jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS audit_denied ON audit_log (allowed, occurred_at DESC);

-- Live pipeline state (Gate 5). Replay runs, per-window detection results, and cases.
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id           text PRIMARY KEY,
    episode_id       text NOT NULL,
    source_type      text NOT NULL CHECK (source_type IN ('lab', 'field', 'simulated')),
    started_at       timestamptz NOT NULL DEFAULT now(),
    started_by       text NOT NULL,
    replay_execution_arn text,
    note             text NOT NULL DEFAULT 'replay of recorded data'
);

CREATE TABLE IF NOT EXISTS detection_windows (
    run_id           text NOT NULL REFERENCES pipeline_runs(run_id),
    window_start     timestamp NOT NULL,          -- original recorded timestamp
    rule_alarm       boolean NOT NULL,
    rules_fired      text NOT NULL DEFAULT '',
    rule_hint        text,
    model_prob       double precision,
    model_alarm      boolean NOT NULL,
    features         jsonb NOT NULL DEFAULT '{}'::jsonb,
    received_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, window_start)
);

CREATE TABLE IF NOT EXISTS cases (
    case_id          text PRIMARY KEY,
    run_id           text NOT NULL UNIQUE REFERENCES pipeline_runs(run_id),
    asset_id         text NOT NULL REFERENCES assets(asset_id),
    opened_at        timestamptz NOT NULL DEFAULT now(),
    detection        jsonb NOT NULL,
    route            text NOT NULL,
    diagnosis        jsonb,
    execution_arn    text
);

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS approval_task_token text;
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS run_id text;
