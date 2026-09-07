-- ============================================================
-- Memecoin Agent v3.0-ultralite - Schema SQL
-- 100% PostgreSQL compatible
-- Optimizado para MacBook Pro 7,1 (8GB RAM) + IM (fallback)
-- SAA v7.2 compliant - PostgreSQL 15
-- ============================================================

-- ============================================================
-- TABLAS BASE
-- ============================================================

-- 1. Tabla tokens (metadatos de tokens y predicciones)
CREATE TABLE IF NOT EXISTS tokens (
  id                  SERIAL PRIMARY KEY,
  mint                VARCHAR(44) UNIQUE NOT NULL,
  name                TEXT,
  symbol              TEXT,
  chain               TEXT DEFAULT 'solana',
  creator_address     VARCHAR(44),
  created_at          TIMESTAMPTZ NOT NULL,

  -- Datos iniciales del lanzamiento
  initial_liquidity   NUMERIC(18,6),
  initial_market_cap  NUMERIC(18,6),
  initial_holders     INTEGER,
  initial_price_usd   NUMERIC(18,6),

  -- Origen del dato
  source              TEXT,
  -- valores: 'backfill_historical' | 'live_rpc' | 'live_polling'

  -- Targets (rellenados por label_targets.py)
  pump_100pc_24h      BOOLEAN,
  rug_pull_48h        BOOLEAN,
  still_active_7d     BOOLEAN,

  -- Historial del creador (NUEVO v3.0)
  creator_rug_history_count    INTEGER DEFAULT 0,
  creator_total_tokens_launched INTEGER DEFAULT 0,
  creator_graduation_rate      REAL,

  -- Bonding curve (NUEVO v3.0)
  bonding_curve_progress_pct   REAL,
  pumpswap_pool_address        VARCHAR(44),
  migrated_to_pumpswap         BOOLEAN DEFAULT FALSE,

  -- RugCheck score (NUEVO v3.0)
  rugcheck_score               INTEGER,
  rugcheck_risks               TEXT,

  -- Predicciones actuales de los modelos
  prob_pump_24h       REAL,
  prob_rug_48h        REAL,
  prob_survival_7d    REAL,

  -- Versiones de modelo usadas en la última predicción
  model_A_version     VARCHAR(64),
  model_B_version     VARCHAR(64),
  model_C_version     VARCHAR(64),

  -- Control
  label_completed     INTEGER DEFAULT 0,
  features_computed   INTEGER DEFAULT 0,
  predicted_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tokens_created_at ON tokens (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tokens_source ON tokens (source);
CREATE INDEX IF NOT EXISTS idx_tokens_probs ON tokens (prob_pump_24h DESC, prob_rug_48h ASC);
CREATE INDEX IF NOT EXISTS idx_tokens_unlabeled ON tokens (label_completed) WHERE label_completed = 0;
CREATE INDEX IF NOT EXISTS idx_tokens_creator ON tokens(creator_address);

-- 2. Tabla launches (series temporales de micro-ventanas)
CREATE TABLE IF NOT EXISTS launches (
  time                        TIMESTAMPTZ NOT NULL,
  token_id                    INTEGER   NOT NULL,

  -- Precio en el momento de la muestra
  price_usd                   NUMERIC(18,6),

  -- Volumen acumulado desde lanzamiento hasta t
  volume_5m                   NUMERIC(18,6),
  volume_15m                  NUMERIC(18,6),
  volume_60m                  NUMERIC(18,6),
  volume_240m                 NUMERIC(18,6),

  -- Micro-ventanas (NUEVO v3.0 para Sniper Engine)
  volume_30s                  NUMERIC(18,6),
  volume_60s                  NUMERIC(18,6),

  -- Transacciones por ventana
  txs_0_5m                    INTEGER,
  txs_5_60m                   INTEGER,
  txs_60_240m                 INTEGER,

  -- Micro-ventanas txs (NUEVO v3.0)
  txs_0_30s                   INTEGER,
  txs_30_60s                  INTEGER,

  -- Wallets únicas acumuladas
  unique_wallets_0_10m        INTEGER,
  unique_wallets_0_60m        INTEGER,

  -- Dirección del flujo
  buy_tx_0_30m                INTEGER,
  sell_tx_0_30m               INTEGER,

  -- Estado de liquidez
  liquidity_pool_before       NUMERIC(18,6),
  liquidity_pool_after        NUMERIC(18,6),
  liquidity_remove_0_2h       BOOLEAN DEFAULT FALSE,

  -- Concentración de holders
  top_10_wallets_pct_0_1h     REAL,
  gini_concentration_0_1h     REAL,

  -- Bonding curve progress (NUEVO v3.0)
  bonding_curve_progress_pct  REAL,
  rugcheck_fetched            BOOLEAN DEFAULT FALSE,

  PRIMARY KEY (time, token_id)
);

CREATE INDEX IF NOT EXISTS idx_launches_token ON launches (token_id, time DESC);

-- 3. Tabla btc_context (contexto de BTC)
CREATE TABLE IF NOT EXISTS btc_context (
  time                TIMESTAMPTZ PRIMARY KEY,
  price_usd           NUMERIC(18,6),
  volume_24h          NUMERIC(18,6),
  change_pct_1h       REAL,
  change_pct_6h       REAL,
  change_pct_24h      REAL,
  dominance_pct       REAL
);

-- 4. Tabla token_features (features calculadas por token)
CREATE TABLE IF NOT EXISTS token_features (
  id                          SERIAL PRIMARY KEY,
  token_id                    INTEGER NOT NULL,
  feature_version             VARCHAR(32) NOT NULL,
  model_version               VARCHAR(64),
  max_feature_window_minutes  INTEGER,
  tx_velocity_0_5m            REAL,
  tx_velocity_5_60m           REAL,
  tx_velocity_60_240m         REAL,
  tx_velocity_0_10s           REAL,
  tx_velocity_10_30s          REAL,
  tx_velocity_30_60s          REAL,
  unique_wallets_0_10m        INTEGER,
  unique_wallets_0_60m        INTEGER,
  buy_tx_ratio_0_30m          REAL,
  liquidity_add_0_10m         BOOLEAN,
  liquidity_remove_0_2h       BOOLEAN,
  liquidity_drop_1_2h_pct     REAL,
  top_10_wallets_pct_0_1h     REAL,
  gini_concentration_0_1h     REAL,
  btc_change_pct_6h           REAL,
  btc_dominance_pct           REAL,
  launch_hour_utc             INTEGER,
  launch_day_of_week          INTEGER,
  creator_rug_history_count   INTEGER,
  creator_graduation_rate     REAL,
  bonding_curve_progress_pct  REAL,
  rugcheck_score              INTEGER,
  creator_bundled_buy         BOOLEAN,
  avg_trade_size_0_30m        REAL,
  slippage_0_30m              REAL,
  created_at                  TIMESTAMPTZ DEFAULT NOW(),
  updated_at                  TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (token_id) REFERENCES tokens(id)
);

CREATE INDEX IF NOT EXISTS idx_tf_version ON token_features (feature_version);
CREATE INDEX IF NOT EXISTS idx_tf_core ON token_features (feature_version, tx_velocity_0_5m DESC, unique_wallets_0_10m DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tf_token_version ON token_features (token_id, feature_version);

-- 5. Tabla token_hypotheses (hipótesis falsables)
CREATE TABLE IF NOT EXISTS token_hypotheses (
  id                      SERIAL PRIMARY KEY,
  hypothesis_text         TEXT NOT NULL,
  conditions_json         TEXT,
  target_model            VARCHAR(32),
  feature_version         VARCHAR(32),
  model_version           VARCHAR(64),
  estimated_probability   REAL,
  confidence_interval     REAL,
  prior_probability       REAL DEFAULT 0.5,
  posterior_probability   REAL DEFAULT 0.5,
  bayes_factor            REAL,
  total_tested            INTEGER DEFAULT 0,
  validated_count         INTEGER DEFAULT 0,
  refuted_count           INTEGER DEFAULT 0,
  generated_by            VARCHAR(64),
  generated_on_data       VARCHAR(64),
  active                  BOOLEAN DEFAULT TRUE,
  created_at              TIMESTAMPTZ DEFAULT NOW(),
  last_updated            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hyp_prob ON token_hypotheses (posterior_probability DESC);
CREATE INDEX IF NOT EXISTS idx_hyp_model ON token_hypotheses (target_model);
CREATE INDEX IF NOT EXISTS idx_hyp_active ON token_hypotheses (active) WHERE active = TRUE;

-- 6. Tabla model_performance (métricas de modelos)
CREATE TABLE IF NOT EXISTS model_performance (
  id                  SERIAL PRIMARY KEY,
  model_name          VARCHAR(64) NOT NULL,
  feature_version     VARCHAR(32),
  model_version       VARCHAR(128),
  train_start         TIMESTAMPTZ,
  train_end           TIMESTAMPTZ,
  test_start          TIMESTAMPTZ,
  test_end            TIMESTAMPTZ,
  n_tokens_train      INTEGER,
  n_tokens_test       INTEGER,
  pct_positive        REAL,
  precision_at_10     REAL,
  precision_at_20     REAL,
  recall_at_10        REAL,
  auc_roc             REAL,
  f1_score            REAL,
  log_loss            REAL,
  model_file_path     TEXT,
  experiment_notes    TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mp_model ON model_performance (model_name, model_version);
CREATE INDEX IF NOT EXISTS idx_mp_created ON model_performance (created_at DESC);

-- 7. Tabla backfill_log (log de backfill histórico)
CREATE TABLE IF NOT EXISTS backfill_log (
  id                  SERIAL PRIMARY KEY,
  source              VARCHAR(64),
  date_range_from     TIMESTAMPTZ,
  date_range_to       TIMESTAMPTZ,
  tokens_discovered   INTEGER DEFAULT 0,
  tokens_stored       INTEGER DEFAULT 0,
  tokens_skipped      INTEGER DEFAULT 0,
  launches_stored     INTEGER DEFAULT 0,
  last_checkpoint     TIMESTAMPTZ,
  status              VARCHAR(32) DEFAULT 'running',
  error_message       TEXT,
  started_at          TIMESTAMPTZ DEFAULT NOW(),
  ended_at            TIMESTAMPTZ
);

-- 8. Tabla agent_execution_log (log de ejecución de agentes)
CREATE TABLE IF NOT EXISTS agent_execution_log (
  id                    SERIAL PRIMARY KEY,
  task_name             VARCHAR(64),
  status                VARCHAR(32),
  error_message         TEXT,
  started_at            TIMESTAMPTZ,
  ended_at              TIMESTAMPTZ,
  tokens_processed      INTEGER DEFAULT 0,
  data_points_collected INTEGER DEFAULT 0,
  extra_json            TEXT
);

CREATE INDEX IF NOT EXISTS idx_ael_task ON agent_execution_log (task_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_ael_status ON agent_execution_log (status);

-- 9. Tabla trades (historial de compras/ventas con PnL)
CREATE TABLE IF NOT EXISTS trades (
  id                    SERIAL PRIMARY KEY,
  token_id              INTEGER REFERENCES tokens(id),
  mint_address          VARCHAR(44) NOT NULL,
  wallet_address        VARCHAR(44) NOT NULL,
  action                VARCHAR(16) NOT NULL,
  amount_sol            NUMERIC(18,6),
  amount_usd            NUMERIC(18,6),
  price_per_token       NUMERIC(18,6),
  jito_bundle_id        VARCHAR(88),
  tx_hash               VARCHAR(88),
  block_slot            BIGINT,
  timestamp             TIMESTAMPTZ NOT NULL,
  pnl_sol               NUMERIC(18,6),
  pnl_pct               REAL,
  status                VARCHAR(32) DEFAULT 'pending',
  stop_loss_triggered   BOOLEAN DEFAULT FALSE,
  take_profit_triggered BOOLEAN DEFAULT FALSE,
  created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_token ON trades (token_id);
CREATE INDEX IF NOT EXISTS idx_trades_wallet ON trades (wallet_address);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades (status);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades (timestamp DESC);

-- 10. Tabla risk_events (eventos del risk filter)
CREATE TABLE IF NOT EXISTS risk_events (
  id                    SERIAL PRIMARY KEY,
  token_id              INTEGER REFERENCES tokens(id),
  mint_address          VARCHAR(44) NOT NULL,
  risk_score            REAL NOT NULL,
  risk_threshold        REAL NOT NULL,
  blocked_reasons       TEXT,
  creator_address       VARCHAR(44),
  creator_rug_history   INTEGER,
  top_10_concentration  REAL,
  liquidity_status      VARCHAR(32),
  timestamp             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  decision              VARCHAR(16) NOT NULL,
  created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_token ON risk_events (token_id);
CREATE INDEX IF NOT EXISTS idx_risk_timestamp ON risk_events (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_risk_decision ON risk_events (decision);

-- 11. Tabla circuit_breaker_log (registro de pausas automáticas)
CREATE TABLE IF NOT EXISTS circuit_breaker_log (
  id                    SERIAL PRIMARY KEY,
  trigger_type          VARCHAR(64) NOT NULL,
  trigger_value         REAL NOT NULL,
  threshold_value       REAL NOT NULL,
  action_taken          VARCHAR(64) NOT NULL,
  total_losses          NUMERIC(18,6),
  active_trades_count   INTEGER,
  paused_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resumed_at            TIMESTAMPTZ,
  duration_minutes      INTEGER,
  notes                 TEXT
);

CREATE INDEX IF NOT EXISTS idx_cb_trigger ON circuit_breaker_log (trigger_type);
CREATE INDEX IF NOT EXISTS idx_cb_paused ON circuit_breaker_log (paused_at DESC);

-- 12. Tabla whales (whales, bundlers, creators)
CREATE TABLE IF NOT EXISTS whales (
  id                    SERIAL PRIMARY KEY,
  wallet                VARCHAR(64) UNIQUE NOT NULL,
  label                 VARCHAR(32) NOT NULL,
  name                  TEXT,
  total_trades          INTEGER DEFAULT 0,
  rug_count             INTEGER DEFAULT 0,
  win_rate              REAL,
  avg_return_pct        REAL,
  first_seen            TIMESTAMPTZ,
  last_seen             TIMESTAMPTZ,
  is_whale_qualifying   BOOLEAN DEFAULT FALSE,
  added_at              TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_whale_label ON whales (label);
CREATE INDEX IF NOT EXISTS idx_whale_qualifying ON whales (is_whale_qualifying) WHERE is_whale_qualifying = TRUE;

-- 13. Tabla spray_targets (copy-trading tracking)
CREATE TABLE IF NOT EXISTS spray_targets (
  id                    SERIAL PRIMARY KEY,
  whale_address         VARCHAR(64) NOT NULL,
  token_id              INTEGER REFERENCES tokens(id),
  whale_action          VARCHAR(16) NOT NULL,
  whale_timestamp       TIMESTAMPTZ NOT NULL,
  our_action            VARCHAR(16),
  our_timestamp         TIMESTAMPTZ,
  our_delay_ms          INTEGER,
  whale_amount_sol      NUMERIC(18,6),
  our_amount_sol        NUMERIC(18,6),
  outcome               VARCHAR(32),
  profit_sol            NUMERIC(18,6),
  profit_pct            REAL,
  created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_st_whale ON spray_targets (whale_address);
CREATE INDEX IF NOT EXISTS idx_st_token ON spray_targets (token_id);
CREATE INDEX IF NOT EXISTS idx_st_outcome ON spray_targets (outcome);

-- 14. Tabla agent_config (parámetros de runtime)
CREATE TABLE IF NOT EXISTS agent_config (
  key                   VARCHAR(64) PRIMARY KEY,
  value                 TEXT NOT NULL,
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);

-- Valores por defecto seguros
INSERT INTO agent_config (key, value) VALUES ('execution_mode', 'research') ON CONFLICT (key) DO NOTHING;
INSERT INTO agent_config (key, value) VALUES ('max_position_sol', '1.0') ON CONFLICT (key) DO NOTHING;
INSERT INTO agent_config (key, value) VALUES ('risk_threshold', '0.65') ON CONFLICT (key) DO NOTHING;
INSERT INTO agent_config (key, value) VALUES ('circuit_breaker_losses', '3') ON CONFLICT (key) DO NOTHING;
INSERT INTO agent_config (key, value) VALUES ('spray_enabled', 'false') ON CONFLICT (key) DO NOTHING;
INSERT INTO agent_config (key, value) VALUES ('sniper_enabled', 'false') ON CONFLICT (key) DO NOTHING;
INSERT INTO agent_config (key, value) VALUES ('stream_source', 'polling') ON CONFLICT (key) DO NOTHING;
INSERT INTO agent_config (key, value) VALUES ('sniper_tx_velocity_threshold', '3.0') ON CONFLICT (key) DO NOTHING;
INSERT INTO agent_config (key, value) VALUES ('sniper_wallet_threshold', '10') ON CONFLICT (key) DO NOTHING;
INSERT INTO agent_config (key, value) VALUES ('sniper_buy_ratio_threshold', '0.70') ON CONFLICT (key) DO NOTHING;
INSERT INTO agent_config (key, value) VALUES ('research_mode', 'heuristic_only') ON CONFLICT (key) DO NOTHING;
INSERT INTO agent_config (key, value) VALUES ('retention_days', '1') ON CONFLICT (key) DO NOTHING;

-- 15. Tabla pending_trades (señales pendientes de ejecución)
CREATE TABLE IF NOT EXISTS pending_trades (
  id                    SERIAL PRIMARY KEY,
  token_id              INTEGER REFERENCES tokens(id),
  mint_address          VARCHAR(44) NOT NULL,
  signal_type           VARCHAR(32) NOT NULL,
  sniper_score          REAL,
  risk_score            REAL,
  whale_address         VARCHAR(64),
  whale_delay_ms        INTEGER,
  confidence            REAL,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  executed_at           TIMESTAMPTZ,
  executed              BOOLEAN DEFAULT FALSE,
  execution_error       TEXT
);

CREATE INDEX IF NOT EXISTS idx_pt_token ON pending_trades (token_id);
CREATE INDEX IF NOT EXISTS idx_pt_executed ON pending_trades (executed) WHERE executed = FALSE;

-- ============================================================
-- VISTAS ÚTILES
-- ============================================================

-- Vista: Tokens pendientes de etiquetar
CREATE OR REPLACE VIEW tokens_pending_label AS
SELECT id, mint, created_at, source
FROM tokens
WHERE label_completed = 0
  AND created_at < NOW() - INTERVAL '24 hours';

-- Vista: Tokens con features calculadas
CREATE OR REPLACE VIEW tokens_ready_for_training AS
SELECT t.id, t.mint, t.pump_100pc_24h, t.rug_pull_48h, t.still_active_7d,
       tf.feature_version, tf.created_at as features_created_at
FROM tokens t
INNER JOIN token_features tf ON tf.token_id = t.id
WHERE t.label_completed = 1
  AND t.pump_100pc_24h IS NOT NULL
  AND t.rug_pull_48h IS NOT NULL;

-- Vista: Métricas de modelos por fecha
CREATE OR REPLACE VIEW model_performance_daily AS
SELECT DATE(created_at) as date, model_name,
       COUNT(*) as runs,
       AVG(precision_at_10) as avg_precision_at_10,
       AVG(auc_roc) as avg_auc_roc
FROM model_performance
GROUP BY DATE(created_at), model_name
ORDER BY date DESC, model_name;

-- Vista: Resumen de trades por día
CREATE OR REPLACE VIEW trades_daily_summary AS
SELECT DATE(timestamp) as date,
       COUNT(*) as total_trades,
       SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END) as winning_trades,
       SUM(CASE WHEN pnl_sol <= 0 THEN 1 ELSE 0 END) as losing_trades,
       SUM(pnl_sol) as total_pnl_sol
FROM trades
GROUP BY DATE(timestamp)
ORDER BY date DESC;

-- Vista: Tokens recientes (últimos 24h)
CREATE OR REPLACE VIEW tokens_recent_24h AS
SELECT *
FROM tokens
WHERE created_at >= NOW() - INTERVAL '24 hours';

-- Vista: Tokens con alta probabilidad de pump (últimos 24h)
CREATE OR REPLACE VIEW tokens_high_pump_prob AS
SELECT *
FROM tokens
WHERE prob_pump_24h > 0.70
  AND created_at >= NOW() - INTERVAL '24 hours'
ORDER BY prob_pump_24h DESC;

-- Vista: Tokens con bajo riesgo de rug (últimos 24h)
CREATE OR REPLACE VIEW tokens_low_rug_prob AS
SELECT *
FROM tokens
WHERE prob_rug_48h < 0.30
  AND created_at >= NOW() - INTERVAL '24 hours'
ORDER BY prob_rug_48h ASC;