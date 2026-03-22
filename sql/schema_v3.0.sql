-- ============================================================
-- Memecoin Agent v3.0-lite - Schema SQL
-- Arquitectura de 4 capas independientes comunicadas via SQLite
-- Optimizado para MacBook Pro 7,1 (8GB RAM)
-- Research Engine ejecutado en WS (32GB RAM + 8GB VRAM)
-- ============================================================

-- ============================================================
-- TABLAS BASE (heredadas de v2.2, con extensiones)
-- ============================================================

-- 1. Tabla tokens (extendida con features v3.0)
-- SQLite compatible (sin SERIAL, usar INTEGER PRIMARY KEY AUTOINCREMENT)
CREATE TABLE tokens (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  address             VARCHAR(255) UNIQUE NOT NULL,
  name                VARCHAR(255),
  symbol              VARCHAR(50),
  chain               VARCHAR(50) DEFAULT 'solana',
  creator_address     VARCHAR(255),
  created_at          TIMESTAMP NOT NULL,

  -- Datos iniciales del lanzamiento
  initial_liquidity   BIGINT,
  initial_market_cap  BIGINT,
  initial_holders     INTEGER,
  initial_price_usd   FLOAT,

  -- Origen del dato
  data_source         VARCHAR(50),
  -- valores: 'backfill_historical' | 'live_rpc' | 'live_grpc' | 'live_ws'

  -- Targets (rellenados por label_targets.py)
  pump_100pc_24h      BOOLEAN,
  rug_pull_48h        BOOLEAN,
  still_active_7d     BOOLEAN,

  -- Historial del creador (NUEVO v3.0)
  creator_rug_history_count    INTEGER DEFAULT 0,
  creator_total_tokens_launched INTEGER DEFAULT 0,
  creator_graduation_rate      FLOAT,

  -- Bonding curve (NUEVO v3.0)
  bonding_curve_progress_pct   FLOAT,
  pumpswap_pool_address        VARCHAR(255),
  migrated_to_pumpswap         BOOLEAN DEFAULT FALSE,

  -- RugCheck score (NUEVO v3.0)
  rugcheck_score               INTEGER,
  rugcheck_risks               JSONB,

  -- Predicciones actuales de los modelos
  prob_pump_24h       FLOAT,
  prob_rug_48h        FLOAT,
  prob_survival_7d    FLOAT,

  -- Versiones de modelo usadas en la última predicción
  model_A_version     VARCHAR(50),
  model_B_version     VARCHAR(50),
  model_C_version     VARCHAR(50),

  -- Control
  label_completed     BOOLEAN DEFAULT FALSE,
  features_computed   BOOLEAN DEFAULT FALSE,
  predicted_at        TIMESTAMP
);

CREATE INDEX idx_tokens_created_at  ON tokens (created_at DESC);
CREATE INDEX idx_tokens_source      ON tokens (data_source);
CREATE INDEX idx_tokens_probs       ON tokens (prob_pump_24h DESC, prob_rug_48h ASC);
CREATE INDEX idx_tokens_unlabeled   ON tokens (label_completed) WHERE label_completed = FALSE;
CREATE INDEX idx_tokens_creator     ON tokens(creator_address);

-- 2. Tabla launches (con micro-ventanas v3.0)
-- SQLite compatible (sin create_hypertable)
CREATE TABLE launches (
  time                        TIMESTAMP NOT NULL,
  token_id                    INTEGER   NOT NULL REFERENCES tokens(id),

  -- Precio en el momento de la muestra
  price_usd                   FLOAT,

  -- Volumen acumulado desde lanzamiento hasta t
  volume_5m                   BIGINT,
  volume_15m                  BIGINT,
  volume_60m                  BIGINT,
  volume_240m                 BIGINT,

  -- Micro-ventanas (NUEVO v3.0 para Sniper Engine)
  volume_10s                  BIGINT,
  volume_30s                  BIGINT,
  volume_60s                  BIGINT,

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
  liquidity_pool_before       BIGINT,
  liquidity_pool_after        BIGINT,
  is_liquidity_removed        BOOLEAN DEFAULT FALSE,

  -- Concentración de holders
  top_10_wallets_pct_0_1h     FLOAT,
  gini_concentration_0_1h     FLOAT,

  -- Bonding curve progress (NUEVO v3.0)
  bonding_curve_progress_pct  FLOAT,
  rugcheck_fetched            BOOLEAN DEFAULT FALSE,

  PRIMARY KEY (time, token_id)
);

-- SQLite no requiere create_hypertable

CREATE INDEX idx_launches_token ON launches (token_id, time DESC);

-- 3. Tabla btc_context
-- SQLite compatible
CREATE TABLE btc_context (
  time                TIMESTAMP PRIMARY KEY,
  price_usd           FLOAT,
  volume_24h          BIGINT,
  change_pct_1h       FLOAT,
  change_pct_6h       FLOAT,
  change_pct_24h      FLOAT,
  dominance_pct       FLOAT
);

-- SQLite no requiere create_hypertable

-- 4. Tabla token_features (extendida con micro-features v3.0)
-- SQLite compatible
CREATE TABLE token_features (
  id                          SERIAL PRIMARY KEY,
  token_id                    INTEGER NOT NULL REFERENCES tokens(id),

  -- Versionado obligatorio
  feature_version             VARCHAR(50) NOT NULL,
  -- valores: 'v1-onchain-minimal' | 'v1-onchain-v73' | 'v1-micro-sniper'
  model_version               VARCHAR(50),

  -- Ventana máxima usada (para detectar leakage)
  max_feature_window_minutes  INTEGER,

  -- 1. Velocidad de transacciones
  tx_velocity_0_5m            FLOAT,
  tx_velocity_5_60m           FLOAT,
  tx_velocity_60_240m         FLOAT,

  -- Micro-ventanas (NUEVO v3.0)
  tx_velocity_0_10s           FLOAT,
  tx_velocity_10_30s          FLOAT,
  tx_velocity_30_60s          FLOAT,

  -- 2. Wallets únicas
  unique_wallets_0_10m        INTEGER,
  unique_wallets_0_60m        INTEGER,

  -- 3. Ratio compra/venta
  buy_tx_ratio_0_30m          FLOAT,

  -- 4. Liquidez
  liquidity_add_0_10m         BOOLEAN,
  liquidity_remove_0_2h       BOOLEAN,
  liquidity_drop_1_2h_pct     FLOAT,

  -- 5. Concentración de holders
  top_10_wallets_pct_0_1h     FLOAT,
  gini_concentration_0_1h     FLOAT,

  -- 6. Contexto BTC
  btc_change_pct_6h           FLOAT,
  btc_dominance_pct           FLOAT,

  -- 7. Timing del lanzamiento
  launch_hour_utc             INTEGER,
  launch_day_of_week          INTEGER,

  -- 8. Features de creador (NUEVO v3.0)
  creator_rug_history_count   INTEGER,
  creator_graduation_rate     FLOAT,

  -- 9. Bonding curve progress (NUEVO v3.0)
  bonding_curve_progress_pct  FLOAT,

  -- 10. RugCheck score (NUEVO v3.0)
  rugcheck_score              INTEGER,

  -- 11. Feature creator_bundled_buy (NUEVO v3.0)
  creator_bundled_buy         BOOLEAN,

  -- 12. Microestructura (v2 en adelante)
  avg_trade_size_0_30m        FLOAT,
  slippage_0_30m              FLOAT,

  created_at                  TIMESTAMP DEFAULT NOW(),
  updated_at                  TIMESTAMP DEFAULT NOW(),

  UNIQUE (token_id, feature_version)
);

CREATE INDEX idx_tf_version ON token_features (feature_version);
CREATE INDEX idx_tf_core    ON token_features (
  feature_version,
  tx_velocity_0_5m DESC,
  unique_wallets_0_10m DESC
);

-- 5. Tabla token_hypotheses
-- SQLite compatible
CREATE TABLE token_hypotheses (
  id                      SERIAL PRIMARY KEY,
  hypothesis_text         TEXT NOT NULL,
  conditions_json         JSONB,
  target_model            VARCHAR(20),
  feature_version         VARCHAR(50),
  model_version           VARCHAR(50),
  estimated_probability   FLOAT,
  confidence_interval     FLOAT,
  prior_probability       FLOAT DEFAULT 0.5,
  posterior_probability   FLOAT DEFAULT 0.5,
  bayes_factor            FLOAT,
  total_tested            INTEGER DEFAULT 0,
  validated_count         INTEGER DEFAULT 0,
  refuted_count           INTEGER DEFAULT 0,
  generated_by            VARCHAR(50),
  generated_on_data       VARCHAR(50),
  active                  BOOLEAN DEFAULT TRUE,
  created_at              TIMESTAMP DEFAULT NOW(),
  last_updated            TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_hyp_prob     ON token_hypotheses (posterior_probability DESC);
CREATE INDEX idx_hyp_model    ON token_hypotheses (target_model);
CREATE INDEX idx_hyp_active   ON token_hypotheses (active) WHERE active = TRUE;
CREATE INDEX idx_hyp_versions ON token_hypotheses (feature_version, model_version);

-- 6. Tabla model_performance
-- SQLite compatible
CREATE TABLE model_performance (
  id                  SERIAL PRIMARY KEY,
  model_name          VARCHAR(50) NOT NULL,
  feature_version     VARCHAR(50),
  model_version       VARCHAR(50),
  train_start         DATE,
  train_end           DATE,
  test_start          DATE,
  test_end            DATE,
  n_tokens_train      INTEGER,
  n_tokens_test       INTEGER,
  pct_positive        FLOAT,
  precision_at_10     FLOAT,
  precision_at_20     FLOAT,
  recall_at_10        FLOAT,
  auc_roc             FLOAT,
  f1_score            FLOAT,
  log_loss            FLOAT,
  model_file_path     VARCHAR(500),
  experiment_notes    TEXT,
  created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_mp_model   ON model_performance (model_name, model_version);
CREATE INDEX idx_mp_created ON model_performance (created_at DESC);

-- 7. Tabla backfill_log
-- SQLite compatible
CREATE TABLE backfill_log (
  id                  SERIAL PRIMARY KEY,
  source              VARCHAR(50),
  date_range_from     DATE,
  date_range_to       DATE,
  tokens_discovered   INTEGER DEFAULT 0,
  tokens_stored       INTEGER DEFAULT 0,
  tokens_skipped      INTEGER DEFAULT 0,
  launches_stored     INTEGER DEFAULT 0,
  last_checkpoint     VARCHAR(255),
  status              VARCHAR(20) DEFAULT 'running',
  error_message       TEXT,
  started_at          TIMESTAMP DEFAULT NOW(),
  ended_at            TIMESTAMP
);

-- 8. Tabla agent_execution_log
-- SQLite compatible
CREATE TABLE agent_execution_log (
  id                    SERIAL PRIMARY KEY,
  task_name             VARCHAR(255),
  status                VARCHAR(50),
  error_message         TEXT,
  started_at            TIMESTAMP,
  ended_at              TIMESTAMP,
  tokens_processed      INTEGER DEFAULT 0,
  data_points_collected INTEGER DEFAULT 0,
  extra_json            JSONB
);

CREATE INDEX idx_ael_task    ON agent_execution_log (task_name, started_at DESC);
CREATE INDEX idx_ael_status  ON agent_execution_log (status);

-- ============================================================
-- TABLAS NUEVAS v3.0
-- ============================================================

-- 9. Tabla trades (historial de compras/ventas con PnL)
-- SQLite compatible
CREATE TABLE trades (
  id                    SERIAL PRIMARY KEY,
  token_id              INTEGER REFERENCES tokens(id),
  mint_address          VARCHAR(255) NOT NULL,
  wallet_address        VARCHAR(255) NOT NULL,
  action                VARCHAR(20) NOT NULL, -- 'buy' | 'sell' | 'rug_pull'
  amount_sol            FLOAT,
  amount_usd            FLOAT,
  price_per_token       FLOAT,
  jito_bundle_id        VARCHAR(255),
  tx_hash               VARCHAR(255),
  block_slot            BIGINT,
  timestamp             TIMESTAMP NOT NULL,
  pnl_sol               FLOAT,
  pnl_pct               FLOAT,
  status                VARCHAR(20) DEFAULT 'pending', -- 'pending' | 'confirmed' | 'failed' | 'stop_loss' | 'take_profit'
  stop_loss_triggered   BOOLEAN DEFAULT FALSE,
  take_profit_triggered BOOLEAN DEFAULT FALSE,
  created_at            TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_trades_token    ON trades (token_id);
CREATE INDEX idx_trades_wallet   ON trades (wallet_address);
CREATE INDEX idx_trades_status   ON trades (status);
CREATE INDEX idx_trades_timestamp ON trades (timestamp DESC);

-- 10. Tabla risk_events (eventos del risk filter)
-- SQLite compatible
CREATE TABLE risk_events (
  id                    SERIAL PRIMARY KEY,
  token_id              INTEGER REFERENCES tokens(id),
  mint_address          VARCHAR(255) NOT NULL,
  risk_score            FLOAT NOT NULL,
  risk_threshold        FLOAT NOT NULL,
  blocked_reasons       TEXT[],
  creator_address       VARCHAR(255),
  creator_rug_history   INTEGER,
  top_10_concentration  FLOAT,
  liquidity_status      VARCHAR(50),
  timestamp             TIMESTAMP NOT NULL DEFAULT NOW(),
  decision              VARCHAR(20) NOT NULL, -- 'block' | 'warn' | 'allow'
  created_at            TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_risk_token    ON risk_events (token_id);
CREATE INDEX idx_risk_timestamp ON risk_events (timestamp DESC);
CREATE INDEX idx_risk_decision ON risk_events (decision);

-- 11. Tabla circuit_breaker_log (registro de pausas automáticas)
-- SQLite compatible
CREATE TABLE circuit_breaker_log (
  id                    SERIAL PRIMARY KEY,
  trigger_type          VARCHAR(50) NOT NULL, -- 'loss_threshold' | 'drawdown' | 'rapid_rug'
  trigger_value         FLOAT NOT NULL,
  threshold_value       FLOAT NOT NULL,
  action_taken          VARCHAR(50) NOT NULL, -- 'pause' | 'alert' | 'kill'
  total_losses          FLOAT,
  active_trades_count   INTEGER,
  paused_at             TIMESTAMP NOT NULL DEFAULT NOW(),
  resumed_at            TIMESTAMP,
  duration_minutes      INTEGER,
  notes                 TEXT
);

CREATE INDEX idx_cb_trigger ON circuit_breaker_log (trigger_type);
CREATE INDEX idx_cb_paused  ON circuit_breaker_log (paused_at DESC);

-- 12. Tabla tracked_wallets (whales, bundlers, creators históricos)
-- SQLite compatible
CREATE TABLE tracked_wallets (
  id                    SERIAL PRIMARY KEY,
  address               VARCHAR(255) UNIQUE NOT NULL,
  wallet_type           VARCHAR(50) NOT NULL, -- 'whale' | 'bundler' | 'creator' | 'rugger'
  name                  VARCHAR(255),
  total_tokens          INTEGER DEFAULT 0,
  rug_count             INTEGER DEFAULT 0,
  graduation_rate       FLOAT,
  avg_return_pct        FLOAT,
  first_seen            TIMESTAMP,
  last_seen             TIMESTAMP,
  is_whale_qualifying   BOOLEAN DEFAULT FALSE,
  created_at            TIMESTAMP DEFAULT NOW(),
  updated_at            TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tw_type    ON tracked_wallets (wallet_type);
CREATE INDEX idx_tw_qualifying ON tracked_wallets (is_whale_qualifying) WHERE is_whale_qualifying = TRUE;

-- 13. Tabla spray_targets (copy-trading tracking)
-- SQLite compatible
CREATE TABLE spray_targets (
  id                    SERIAL PRIMARY KEY,
  whale_address         VARCHAR(255) NOT NULL,
  token_id              INTEGER REFERENCES tokens(id),
  whale_action          VARCHAR(20) NOT NULL, -- 'buy' | 'sell'
  whale_timestamp       TIMESTAMP NOT NULL,
  our_action            VARCHAR(20),
  our_timestamp         TIMESTAMP,
  our_delay_ms          INTEGER,
  whale_amount_sol      FLOAT,
  our_amount_sol        FLOAT,
  outcome               VARCHAR(50), -- 'profit' | 'loss' | 'rug' | 'pending'
  profit_sol            FLOAT,
  profit_pct            FLOAT,
  created_at            TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_st_whale   ON spray_targets (whale_address);
CREATE INDEX idx_st_token   ON spray_targets (token_id);
CREATE INDEX idx_st_outcome ON spray_targets (outcome);

-- 14. Tabla agent_config (parámetros de runtime)
-- SQLite compatible
CREATE TABLE agent_config (
  key                   VARCHAR(100) PRIMARY KEY,
  value                 TEXT NOT NULL,
  updated_at            TIMESTAMP DEFAULT NOW()
);

-- Valores por defecto seguros
INSERT INTO agent_config VALUES ('execution_mode', 'research', NOW());
INSERT INTO agent_config VALUES ('max_position_sol', '1.0', NOW());
INSERT INTO agent_config VALUES ('risk_threshold', '0.65', NOW());
INSERT INTO agent_config VALUES ('circuit_breaker_losses', '3', NOW());
INSERT INTO agent_config VALUES ('spray_enabled', 'false', NOW());
INSERT INTO agent_config VALUES ('sniper_enabled', 'false', NOW());
INSERT INTO agent_config VALUES ('stream_source', 'grpc', NOW());
INSERT INTO agent_config VALUES ('sniper_tx_velocity_threshold', '3.0', NOW());
INSERT INTO agent_config VALUES ('sniper_wallet_threshold', '10', NOW());
INSERT INTO agent_config VALUES ('sniper_buy_ratio_threshold', '0.70', NOW());

-- 15. Tabla pending_trades (señales pendientes de ejecución)
-- SQLite compatible
CREATE TABLE pending_trades (
  id                    SERIAL PRIMARY KEY,
  token_id              INTEGER REFERENCES tokens(id),
  mint_address          VARCHAR(255) NOT NULL,
  signal_type           VARCHAR(50) NOT NULL, -- 'sniper_pump' | 'sniper_rug avoidance' | 'whale_copy'
  sniper_score          FLOAT,
  risk_score            FLOAT,
  whale_address         VARCHAR(255),
  whale_delay_ms        INTEGER,
  confidence            FLOAT,
  created_at            TIMESTAMP DEFAULT NOW(),
  executed_at           TIMESTAMP,
  executed              BOOLEAN DEFAULT FALSE,
  execution_error       TEXT
);

CREATE INDEX idx_pt_token    ON pending_trades (token_id);
CREATE INDEX idx_pt_executed ON pending_trades (executed) WHERE executed = FALSE;

-- ============================================================
-- ÍNDICES ADICIONALES v3.0
-- ============================================================

CREATE INDEX idx_tokens_creator ON tokens(creator_address);
CREATE INDEX idx_tokens_migrated ON tokens(migrated_to_pumpswap) WHERE migrated_to_pumpswap = TRUE;
CREATE INDEX idx_tokens_rugcheck ON tokens(rugcheck_score) WHERE rugcheck_score IS NOT NULL;

-- ============================================================
-- VISTAS ÚTILES v3.0
-- ============================================================

-- Vista: Tokens pendientes de etiquetar
-- SQLite compatible
CREATE VIEW tokens_pending_label AS
SELECT id, address, created_at, data_source
FROM tokens
WHERE label_completed = FALSE
  AND created_at < NOW() - INTERVAL '24 hours';

-- Vista: Tokens con features calculadas
-- SQLite compatible
CREATE VIEW tokens_ready_for_training AS
SELECT t.id, t.address, t.pump_100pc_24h, t.rug_pull_48h, t.still_active_7d,
       tf.feature_version, tf.created_at as features_created_at
FROM tokens t
INNER JOIN token_features tf ON tf.token_id = t.id
WHERE t.label_completed = TRUE
  AND t.pump_100pc_24h IS NOT NULL
  AND t.rug_pull_48h IS NOT NULL;

-- Vista: Métricas de modelos por fecha
-- SQLite compatible
CREATE VIEW model_performance_daily AS
SELECT DATE(created_at) as date, model_name,
       COUNT(*) as runs,
       AVG(precision_at_10) as avg_precision_at_10,
       AVG(auc_roc) as avg_auc_roc
FROM model_performance
GROUP BY DATE(created_at), model_name
ORDER BY date DESC, model_name;

-- ============================================================
-- COMENTARIOS DE DOCUMENTACIÓN
-- ============================================================

-- SQLite no soporta COMMENT ON TABLE
-- Documentación en README.md
