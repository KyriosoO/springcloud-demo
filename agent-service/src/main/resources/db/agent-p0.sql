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
  INDEX idx_agent_turn_conversation_status_seq (conversation_id, status, turn_seq),
  INDEX idx_agent_turn_user_created (user_id, created_at),
  CONSTRAINT fk_agent_turn_conversation
    FOREIGN KEY (conversation_id) REFERENCES agent_conversation(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
