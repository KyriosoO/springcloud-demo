CREATE TABLE IF NOT EXISTS agent_conversation (
  id VARCHAR(64) PRIMARY KEY,
  user_id VARCHAR(128) NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at DATETIME(3) NOT NULL,
  updated_at DATETIME(3) NOT NULL,
  INDEX idx_agent_conversation_user_updated (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS agent_turn (
  id VARCHAR(64) PRIMARY KEY,
  turn_seq BIGINT NOT NULL AUTO_INCREMENT,
  conversation_id VARCHAR(64) NOT NULL,
  invocation_id VARCHAR(64),
  user_id VARCHAR(128) NOT NULL,
  user_message TEXT NOT NULL,
  intent VARCHAR(32),
  response_type VARCHAR(32),
  assistant_message TEXT,
  query_context_json JSON,
  status VARCHAR(32) NOT NULL,
  error_code VARCHAR(64),
  created_at DATETIME(3) NOT NULL,
  completed_at DATETIME(3),
  UNIQUE INDEX uk_agent_turn_seq (turn_seq),
  UNIQUE INDEX uk_agent_turn_invocation (invocation_id),
  INDEX idx_agent_turn_conversation_status_seq (conversation_id, status, turn_seq),
  INDEX idx_agent_turn_user_created (user_id, created_at),
  CONSTRAINT fk_agent_turn_conversation
    FOREIGN KEY (conversation_id) REFERENCES agent_conversation(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS agent_invocation_record (
  id VARCHAR(64) PRIMARY KEY,
  invocation_type VARCHAR(32) NOT NULL,
  origin_type VARCHAR(32) NOT NULL,
  conversation_id VARCHAR(64) NOT NULL,
  turn_id VARCHAR(64) NOT NULL,
  subject_type VARCHAR(32) NOT NULL,
  subject_id VARCHAR(128) NOT NULL,
  owner_type VARCHAR(32) NOT NULL,
  owner_id VARCHAR(128) NOT NULL,
  scope_type VARCHAR(32) NOT NULL,
  scope_id VARCHAR(128) NOT NULL,
  agent_id VARCHAR(128) NOT NULL,
  profile_version VARCHAR(128) NOT NULL,
  request_correlation_id VARCHAR(64) NOT NULL,
  state VARCHAR(32) NOT NULL,
  response_type VARCHAR(32),
  checkpoint_json JSON,
  checkpoint_hash VARCHAR(128),
  error_code VARCHAR(64),
  safe_message TEXT,
  diagnostic_id VARCHAR(128),
  deadline_at DATETIME(3) NOT NULL,
  created_at DATETIME(3) NOT NULL,
  checkpointed_at DATETIME(3),
  completed_at DATETIME(3),
  UNIQUE INDEX uk_agent_invocation_turn (turn_id),
  UNIQUE INDEX uk_agent_invocation_correlation (request_correlation_id),
  INDEX idx_agent_invocation_state_deadline (state, deadline_at),
  INDEX idx_agent_invocation_subject_created (subject_id, created_at),
  CONSTRAINT fk_agent_invocation_turn
    FOREIGN KEY (turn_id) REFERENCES agent_turn(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS agent_invocation_result (
  id VARCHAR(64) PRIMARY KEY,
  invocation_id VARCHAR(64) NOT NULL,
  output_contract_schema VARCHAR(128),
  output_contract_version VARCHAR(64),
  payload_json JSON,
  safe_message TEXT NOT NULL,
  safe_summary TEXT NOT NULL,
  created_at DATETIME(3) NOT NULL,
  UNIQUE INDEX uk_agent_invocation_result_invocation (invocation_id),
  CONSTRAINT fk_agent_invocation_result
    FOREIGN KEY (invocation_id) REFERENCES agent_invocation_record(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS agent_context_record (
  context_id VARCHAR(128) PRIMARY KEY,
  owner_type VARCHAR(32) NOT NULL,
  owner_id VARCHAR(128) NOT NULL,
  scope_type VARCHAR(32) NOT NULL,
  scope_id VARCHAR(128) NOT NULL,
  context_type VARCHAR(64) NOT NULL,
  contract_schema VARCHAR(128) NOT NULL,
  contract_version VARCHAR(64) NOT NULL,
  record_version BIGINT NOT NULL,
  protected_payload_json JSON NOT NULL,
  source_capability_id VARCHAR(128) NOT NULL,
  source_invocation_id VARCHAR(64) NOT NULL,
  source_domain VARCHAR(128),
  readable TINYINT(1) NOT NULL DEFAULT 1,
  expires_at DATETIME(3) NOT NULL,
  updated_at DATETIME(3) NOT NULL,
  UNIQUE INDEX uk_agent_context_key (owner_type, owner_id, scope_type, scope_id, context_type),
  INDEX idx_agent_context_expiry (expires_at),
  INDEX idx_agent_context_source_invocation (source_invocation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
