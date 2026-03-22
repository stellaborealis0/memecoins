-- ============================================================
-- Memecoin Agent v3.0-ultralite - Schema SQL
-- 100% SQLite compatible - WAL mode obligatorio
-- Optimizado para MacBook Pro 7,1 (8GB RAM) + IM (fallback)
-- SAA v7.2 compliant - Sin Docker, sin PostgreSQL, sin TimescaleDB
-- ============================================================

-- ============================================================
-- INICIALIZACIÓN OBLIGATORIA (ejecutar al conectar)
-- ============================================================
-- PRAGMA journal_mode=WAL;
-- PRAGMA busy_timeout=5000;
-- PRAGMA synchronous=NORMAL;
-- PRAGMA cache_size=-100000;
-- ============================================================

-- ============================================================
-- TABLAS BASE
-- ============================================================

-- 1. Tabla tokens (metadatos de tokens y predicciones)
CREATE TABLE IF NOT EXISTS tokens (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  address             TEXT UNIQUE NOT NULL,
  name                TEXT,
  symbol              TEXT,
  chain               TEXT DEFAULT 'solana',
  creator_address     TEXT,
  created_at          TEXT NOT NULL,

  -- Datos iniciales del lanzamiento
  initial_liquidity   INTEGER,
  initial_market_cap  INTEGER,
  initial_holders     INTEGER,
  initial_price_usd   REAL,

  -- Origen del dato
  data_source         TEXT,
  -- valores: 'backfill_historical' | 'live_rpc' | 'live_polling'

  -- Targets (rellenados por label_targets.py)
  pump_100pc_24h      INTEGER,
  rug_pull_48h        INTEGER,
  still_active_7d     INTEGER,

  -- Historial del creador (NUEVO v3.0)
  creator_rug_history_count    INTEGER DEFAULT 0,
  creator_total_tokens_launched INTEGER DEFAULT 0,
  creator_graduation_rate      REAL,

  -- Bonding curve (NUEVO v3.0)
  bonding_curve_progress_pct   REAL,
  pumpswap_pool_address        TEXT,
  migrated_to_pumpswap         INTEGER DEFAULT 0,

  -- RugCheck score (NUEVO v3.0)
  rugcheck_score               INTEGER,
  rugcheck_risks               TEXT,

  -- Predicciones actuales de los modelos
  prob_pump_24h       REAL,
  prob_rug_48h        REAL,
  prob_survival_7d    REAL,

  -- Versiones de modelo usadas en la última predicción
  model_A_version     TEXT,
  model_B_version     TEXT,
  model_C_version     TEXT,

  -- Control
  label_completed     INTEGER DEFAULT 0,
  features_computed   INTEGER DEFAULT 0,
  predicted_at        TEXT
);

CREATE INDEX IF NOT EXISTS idx_tokens_created_at ON tokens (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tokens_source ON tokens (data_source);
CREATE INDEX IF NOT EXISTS idx_tokens_probs ON tokens (prob_pump_24h DESC, prob_rug_48h ASC);
CREATE INDEX IF NOT EXISTS idx_tokens_unlabeled ON tokens (label_completed) WHERE label_completed = 0;
CREATE INDEX IF NOT EXISTS idx_tokens_creator ON tokens(creator_address);

-- 2. Tabla launches (series temporales de micro-ventanas)
CREATE TABLE IF NOT EXISTS launches (
  time                        TEXT NOT NULL,
  token_id                    INTEGER   NOT NULL,

  -- Precio en el momento de la muestra
  price_usd                   REAL,

  -- Volumen acumulado desde lanzamiento hasta t
  volume_5m                   INTEGER,
  volume_15m                  INTEGER,
  volume_60m                  INTEGER,
  volume_240m                 INTEGER,

  -- Micro-ventanas (NUEVO v3.0 para Sniper Engine)
  volume_10s                  INTEGER,
  volume_30s                  INTEGER,
  volume_60s                  INTEGER,

  -- Transacciones por ventana
  txs_0_5m                    INTEGER,
  txs_5_60m                   INTEGER,
  txs_60_240m                 INTEGER,

  -- Micro-ventanas txs (NUEVO v3.0)
  txs_0_10s                   INTEGER,
  txs_10_30s                  INTEGER,
  txs_30_60s                  INTEGER,

  -- Wallets únicas acumuladas
  unique_wallets_0_10m        INTEGER,
  unique_wallets_0_60m        INTEGER,

  -- Dirección del flujo
  buy_tx_0_30m                INTEGER,
  sell_tx_0_30m               INTEGER,

  -- Estado de liquidez
  liquidity_pool_before       INTEGER,
  liquidity_pool_after        INTEGER,
  is_liquidity_removed        INTEGER DEFAULT 0,

  -- Concentración de holders
  top_10_wallets_pct_0_1h     REAL,
  gini_concentration_0_1h     REAL,

  -- Bonding curve progress (NUEVO v3.0)
  bonding_curve_progress_pct  REAL,
  rugcheck_fetched            INTEGER DEFAULT 0,

  PRIMARY KEY (time, token_id)
);

CREATE INDEX IF NOT EXISTS idx_launches_token ON launches (token_id, time DESC);

-- 3. Tabla btc_context (contexto de BTC)
CREATE TABLE IF NOT EXISTS btc_context (
  time                TEXT PRIMARY KEY,
  price_usd           REAL,
  volume_24h          INTEGER,
  change_pct_1h       REAL,
  change_pct_6h       REAL,
  change_pct_24h      REAL,
  dominance_pct       REAL
);

-- 4. Tabla token_features (features calculadas por token)
CREATE TABLE IF NOT EXISTS token_features (
  id                          INTEGER PRIMARY KEY AUTOINCREMENT,
  token_id                    INTEGER NOT NULL,
  feature_version             TEXT NOT NULL,
  model_version               TEXT,
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
  liquidity_add_0_10m         INTEGER,
  liquidity_remove_0_2h       INTEGER,
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
  creator_bundled_buy         INTEGER,
  avg_trade_size_0_30m        REAL,
  slippage_0_30m              REAL,
  created_at                  TEXT DEFAULT (datetime('now')),
  updated_at                  TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (token_id) REFERENCES tokens(id)
);

CREATE INDEX IF NOT EXISTS idx_tf_version ON token_features (feature_version);
CREATE INDEX IF NOT EXISTS idx_tf_core ON token_features (feature_version, tx_velocity_0_5m DESC, unique_wallets_0_10m DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tf_token_version ON token_features (token_id, feature_version);

-- 5. Tabla token_hypotheses (hipótesis falsables)
CREATE TABLE IF NOT EXISTS token_hypotheses (
  id                      INTEGER PRIMARY KEY AUTOINCREMENT,
  hypothesis_text         TEXT NOT NULL,
  conditions_json         TEXT,
  target_model            TEXT,
  feature_version         TEXT,
  model_version           TEXT,
  estimated_probability   REAL,
  confidence_interval     REAL,
  prior_probability       REAL DEFAULT 0.5,
  posterior_probability   REAL DEFAULT 0.5,
  bayes_factor            REAL,
  total_tested            INTEGER DEFAULT 0,
  validated_count         INTEGER DEFAULT 0,
  refuted_count           INTEGER DEFAULT 0,
  generated_by            TEXT,
  generated_on_data       TEXT,
  active                  INTEGER DEFAULT 1,
  created_at              TEXT DEFAULT (datetime('now')),
  last_updated            TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_hyp_prob ON token_hypotheses (posterior_probability DESC);
CREATE INDEX IF NOT EXISTS idx_hyp_model ON token_hypotheses (target_model);
CREATE INDEX IF NOT EXISTS idx_hyp_active ON token_hypotheses (active) WHERE active = 1;

-- 6. Tabla model_performance (métricas de modelos)
CREATE TABLE IF NOT EXISTS model_performance (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  model_name          TEXT NOT NULL,
  feature_version     TEXT,
  model_version       TEXT,
  train_start         TEXT,
  train_end           TEXT,
  test_start          TEXT,
  test_end            TEXT,
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
  created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_mp_model ON model_performance (model_name, model_version);
CREATE INDEX IF NOT EXISTS idx_mp_created ON model_performance (created_at DESC);

-- 7. Tabla backfill_log (log de backfill histórico)
CREATE TABLE IF NOT EXISTS backfill_log (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  source              TEXT,
  date_range_from     TEXT,
  date_range_to       TEXT,
  tokens_discovered   INTEGER DEFAULT 0,
  tokens_stored       INTEGER DEFAULT 0,
  tokens_skipped      INTEGER DEFAULT 0,
  launches_stored     INTEGER DEFAULT 0,
  last_checkpoint     TEXT,
  status              TEXT DEFAULT 'running',
  error_message       TEXT,
  started_at          TEXT DEFAULT (datetime('now')),
  ended_at            TEXT
);

-- 8. Tabla agent_execution_log (log de ejecución de agentes)
CREATE TABLE IF NOT EXISTS agent_execution_log (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  task_name             TEXT,
  status                TEXT,
  error_message         TEXT,
  started_at            TEXT,
  ended_at              TEXT,
  tokens_processed      INTEGER DEFAULT 0,
  data_points_collected INTEGER DEFAULT 0,
  extra_json            TEXT
);

CREATE INDEX IF NOT EXISTS idx_ael_task ON agent_execution_log (task_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_ael_status ON agent_execution_log (status);

-- 9. Tabla trades (historial de compras/ventas con PnL)
CREATE TABLE IF NOT EXISTS trades (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  token_id              INTEGER REFERENCES tokens(id),
  mint_address          TEXT NOT NULL,
  wallet_address        TEXT NOT NULL,
  action                TEXT NOT NULL,
  amount_sol            REAL,
  amount_usd            REAL,
  price_per_token       REAL,
  jito_bundle_id        TEXT,
  tx_hash               TEXT,
  block_slot            INTEGER,
  timestamp             TEXT NOT NULL,
  pnl_sol               REAL,
  pnl_pct               REAL,
  status                TEXT DEFAULT 'pending',
  stop_loss_triggered   INTEGER DEFAULT 0,
  take_profit_triggered INTEGER DEFAULT 0,
  created_at            TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_trades_token ON trades (token_id);
CREATE INDEX IF NOT EXISTS idx_trades_wallet ON trades (wallet_address);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades (status);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades (timestamp DESC);

-- 10. Tabla risk_events (eventos del risk filter)
CREATE TABLE IF NOT EXISTS risk_events (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  token_id              INTEGER REFERENCES tokens(id),
  mint_address          TEXT NOT NULL,
  risk_score            REAL NOT NULL,
  risk_threshold        REAL NOT NULL,
  blocked_reasons       TEXT,
  creator_address       TEXT,
  creator_rug_history   INTEGER,
  top_10_concentration  REAL,
  liquidity_status      TEXT,
  timestamp             TEXT NOT NULL DEFAULT (datetime('now')),
  decision              TEXT NOT NULL,
  created_at            TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_risk_token ON risk_events (token_id);
CREATE INDEX IF NOT EXISTS idx_risk_timestamp ON risk_events (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_risk_decision ON risk_events (decision);

-- 11. Tabla circuit_breaker_log (registro de pausas automáticas)
CREATE TABLE IF NOT EXISTS circuit_breaker_log (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  trigger_type          TEXT NOT NULL,
  trigger_value         REAL NOT NULL,
  threshold_value       REAL NOT NULL,
  action_taken          TEXT NOT NULL,
  total_losses          REAL,
  active_trades_count   INTEGER,
  paused_at             TEXT NOT NULL DEFAULT (datetime('now')),
  resumed_at            TEXT,
  duration_minutes      INTEGER,
  notes                 TEXT
);

CREATE INDEX IF NOT EXISTS idx_cb_trigger ON circuit_breaker_log (trigger_type);
CREATE INDEX IF NOT EXISTS idx_cb_paused ON circuit_breaker_log (paused_at DESC);

-- 12. Tabla tracked_wallets (whales, bundlers, creators)
CREATE TABLE IF NOT EXISTS tracked_wallets (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  address               TEXT UNIQUE NOT NULL,
  wallet_type           TEXT NOT NULL,
  name                  TEXT,
  total_tokens          INTEGER DEFAULT 0,
  rug_count             INTEGER DEFAULT 0,
  graduation_rate       REAL,
  avg_return_pct        REAL,
  first_seen            TEXT,
  last_seen             TEXT,
  is_whale_qualifying   INTEGER DEFAULT 0,
  created_at            TEXT DEFAULT (datetime('now')),
  updated_at            TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tw_type ON tracked_wallets (wallet_type);
CREATE INDEX IF NOT EXISTS idx_tw_qualifying ON tracked_wallets (is_whale_qualifying) WHERE is_whale_qualifying = 1;

-- 13. Tabla spray_targets (copy-trading tracking)
CREATE TABLE IF NOT EXISTS spray_targets (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  whale_address         TEXT NOT NULL,
  token_id              INTEGER REFERENCES tokens(id),
  whale_action          TEXT NOT NULL,
  whale_timestamp       TEXT NOT NULL,
  our_action            TEXT,
  our_timestamp         TEXT,
  our_delay_ms          INTEGER,
  whale_amount_sol      REAL,
  our_amount_sol        REAL,
  outcome               TEXT,
  profit_sol            REAL,
  profit_pct            REAL,
  created_at            TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_st_whale ON spray_targets (whale_address);
CREATE INDEX IF NOT EXISTS idx_st_token ON spray_targets (token_id);
CREATE INDEX IF NOT EXISTS idx_st_outcome ON spray_targets (outcome);

-- 14. Tabla agent_config (parámetros de runtime)
CREATE TABLE IF NOT EXISTS agent_config (
  key                   TEXT PRIMARY KEY,
  value                 TEXT NOT NULL,
  updated_at            TEXT DEFAULT (datetime('now'))
);

-- Valores por defecto seguros
INSERT OR IGNORE INTO agent_config VALUES ('execution_mode', 'research');
INSERT OR IGNORE INTO agent_config VALUES ('max_position_sol', '1.0');
INSERT OR IGNORE INTO agent_config VALUES ('risk_threshold', '0.65');
INSERT OR IGNORE INTO agent_config VALUES ('circuit_breaker_losses', '3');
INSERT OR IGNORE INTO agent_config VALUES ('spray_enabled', 'false');
INSERT OR IGNORE INTO agent_config VALUES ('sniper_enabled', 'false');
INSERT OR IGNORE INTO agent_config VALUES ('stream_source', 'polling');
INSERT OR IGNORE INTO agent_config VALUES ('sniper_tx_velocity_threshold', '3.0');
INSERT OR IGNORE INTO agent_config VALUES ('sniper_wallet_threshold', '10');
INSERT OR IGNORE INTO agent_config VALUES ('sniper_buy_ratio_threshold', '0.70');
INSERT OR IGNORE INTO agent_config VALUES ('research_mode', 'heuristic_only');
INSERT OR IGNORE INTO agent_config VALUES ('retention_days', '1');

-- 15. Tabla pending_trades (señales pendientes de ejecución)
CREATE TABLE IF NOT EXISTS pending_trades (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  token_id              INTEGER REFERENCES tokens(id),
  mint_address          TEXT NOT NULL,
  signal_type           TEXT NOT NULL,
  sniper_score          REAL,
  risk_score            REAL,
  whale_address         TEXT,
  whale_delay_ms        INTEGER,
  confidence            REAL,
  created_at            TEXT DEFAULT (datetime('now')),
  executed_at           TEXT,
  executed              INTEGER DEFAULT 0,
  execution_error       TEXT
);

CREATE INDEX IF NOT EXISTS idx_pt_token ON pending_trades (token_id);
CREATE INDEX IF NOT EXISTS idx_pt_executed ON pending_trades (executed) WHERE executed = 0;

-- ============================================================
-- VISTAS ÚTILES
-- ============================================================

-- Vista: Tokens pendientes de etiquetar
CREATE VIEW IF NOT EXISTS tokens_pending_label AS
SELECT id, address, created_at, data_source
FROM tokens
WHERE label_completed = 0
  AND created_at < datetime('now', '-24 hours');

-- Vista: Tokens con features calculadas
CREATE VIEW IF NOT EXISTS tokens_ready_for_training AS
SELECT t.id, t.address, t.pump_100pc_24h, t.rug_pull_48h, t.still_active_7d,
       tf.feature_version, tf.created_at as features_created_at
FROM tokens t
INNER JOIN token_features tf ON tf.token_id = t.id
WHERE t.label_completed = 1
  AND t.pump_100pc_24h IS NOT NULL
  AND t.rug_pull_48h IS NOT NULL;

-- Vista: Métricas de modelos por fecha
CREATE VIEW IF NOT EXISTS model_performance_daily AS
SELECT DATE(created_at) as date, model_name,
       COUNT(*) as runs,
       AVG(precision_at_10) as avg_precision_at_10,
       AVG(auc_roc) as avg_auc_roc
FROM model_performance
GROUP BY DATE(created_at), model_name
ORDER BY date DESC, model_name;

-- Vista: Resumen de trades por día
CREATE VIEW IF NOT EXISTS trades_daily_summary AS
SELECT DATE(timestamp) as date,
       COUNT(*) as total_trades,
       SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END) as winning_trades,
       SUM(CASE WHEN pnl_sol <= 0 THEN 1 ELSE 0 END) as losing_trades,
       SUM(pnl_sol) as total_pnl_sol
FROM trades
GROUP BY DATE(timestamp)
ORDER BY date DESC;

-- Vista: Tokens recientes (últimos 24h)
CREATE VIEW IF NOT EXISTS tokens_recent_24h AS
SELECT *
FROM tokens
WHERE created_at >= datetime('now', '-24 hours');

-- Vista: Tokens con alta probabilidad de pump (últimos 24h)
CREATE VIEW IF NOT EXISTS tokens_high_pump_prob AS
SELECT *
FROM tokens
WHERE prob_pump_24h > 0.70
  AND created_at >= datetime('now', '-24 hours')
ORDER BY prob_pump_24h DESC;

-- Vista: Tokens con bajo riesgo de rug (últimos 24h)
CREATE VIEW IF NOT EXISTS tokens_low_rug_prob AS
SELECT *
FROM tokens
WHERE prob_rug_48h < 0.30
  AND created_at >= datetime('now', '-24 hours')
ORDER BY prob_rug_48h ASC;