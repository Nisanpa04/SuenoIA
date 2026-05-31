-- =============================================================================
-- SueñoIA — Inicialización de TimescaleDB
-- Se ejecuta automáticamente la primera vez que arranca el contenedor.
-- =============================================================================

-- Habilitamos la extensión TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Base de datos separada para MLflow tracking
CREATE DATABASE mlflow;

-- =============================================================================
-- TABLAS DE USUARIOS Y SESIONES
-- =============================================================================
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    email       VARCHAR(255) UNIQUE NOT NULL,
    name        VARCHAR(255),
    chronotype  VARCHAR(50),                  -- 'morning', 'evening', 'intermediate'
    timezone    VARCHAR(64) DEFAULT 'Europe/Madrid',
    telegram_chat_id VARCHAR(64),             -- para notificaciones Telegram
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Usuario demo para el desarrollo
INSERT INTO users (email, name, chronotype) VALUES
    ('demo@suenoia.local', 'Demo User', 'intermediate');

-- =============================================================================
-- SERIES TEMPORALES BIOMÉTRICAS (hypertable de TimescaleDB)
-- =============================================================================
-- Cada lectura del wearable (HR, HRV, movimiento, SpO2, temp...)
CREATE TABLE biometrics (
    time        TIMESTAMPTZ NOT NULL,
    user_id     INT NOT NULL REFERENCES users(id),
    metric      VARCHAR(64) NOT NULL,         -- 'heart_rate', 'hrv_sdnn', etc.
    value       DOUBLE PRECISION,
    source      VARCHAR(32),                  -- 'apple_watch', 'simulator', 'rpi'
    metadata    JSONB
);

SELECT create_hypertable('biometrics', 'time');
CREATE INDEX idx_biometrics_user_metric ON biometrics (user_id, metric, time DESC);

-- =============================================================================
-- EVENTOS DE SUEÑO (start/end, fases detectadas)
-- =============================================================================
CREATE TABLE sleep_events (
    id          BIGSERIAL PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES users(id),
    start_time  TIMESTAMPTZ NOT NULL,
    end_time    TIMESTAMPTZ,
    phase       VARCHAR(16),                  -- 'awake', 'light', 'deep', 'rem'
    quality_score DOUBLE PRECISION
);

-- =============================================================================
-- PREDICCIONES DE IA
-- =============================================================================
CREATE TABLE predictions (
    id              BIGSERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(id),
    predicted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    target_date     DATE NOT NULL,
    quality_raw     DOUBLE PRECISION,
    score_100       DOUBLE PRECISION,
    category        VARCHAR(32),
    recommended_wake TIME,
    model_version   VARCHAR(64),
    inputs          JSONB,
    explanation     JSONB                     -- SHAP values + features
);

-- =============================================================================
-- ALERTAS Y NOTIFICACIONES
-- =============================================================================
CREATE TABLE alerts (
    id          BIGSERIAL PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    severity    VARCHAR(16),                  -- 'critical', 'warning', 'info'
    category    VARCHAR(64),
    title       VARCHAR(255),
    text        TEXT,
    sent_telegram   BOOLEAN DEFAULT FALSE,
    sent_websocket  BOOLEAN DEFAULT FALSE,
    metadata    JSONB
);

-- =============================================================================
-- CONVERSACIONES (chat con la IA)
-- =============================================================================
CREATE TABLE chat_messages (
    id          BIGSERIAL PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    role        VARCHAR(16) NOT NULL,         -- 'user', 'assistant', 'system'
    content     TEXT NOT NULL,
    session_id  UUID
);

CREATE INDEX idx_chat_user_time ON chat_messages (user_id, created_at DESC);

-- =============================================================================
-- DIARIO DE SUEÑO (respuestas a las preguntas pre/post sueño)
-- =============================================================================
CREATE TABLE sleep_journal (
    id              BIGSERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(id),
    entry_date      DATE NOT NULL,
    mood            INT,                      -- 1-10
    stress_level    INT,                      -- 1-10
    caffeine_after_17 BOOLEAN,
    alcohol         BOOLEAN,
    screens_min_before_bed INT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, entry_date)
);

COMMENT ON SCHEMA public IS 'SueñoIA v2 — esquema de plataforma de salud del sueño';
