-- Existing P0 installations only.
-- Run once before deploying code that persists the latest validated QUERY.

ALTER TABLE agent_turn
  ADD COLUMN query_context_json JSON NULL AFTER assistant_message;
