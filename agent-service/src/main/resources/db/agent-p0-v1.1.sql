-- Existing P0 installations only.
-- Run once before deploying code that orders recent turns by turn_seq.

ALTER TABLE agent_turn
  ADD COLUMN turn_seq BIGINT NOT NULL AUTO_INCREMENT,
  ADD UNIQUE INDEX uk_agent_turn_seq (turn_seq),
  ADD INDEX idx_agent_turn_conversation_status_seq (conversation_id, status, turn_seq);

ALTER TABLE agent_turn
  DROP INDEX idx_agent_turn_conversation_status_created;
