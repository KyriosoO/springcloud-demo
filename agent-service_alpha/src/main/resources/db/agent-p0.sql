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

CREATE TABLE IF NOT EXISTS document_validation_run (
  run_id VARCHAR(64) PRIMARY KEY, idempotency_digest CHAR(64) NOT NULL, request_digest CHAR(64) NOT NULL,
  subject_type VARCHAR(32) NOT NULL, subject_digest CHAR(64) NOT NULL, policy_digest CHAR(64) NOT NULL,
  fixture_digest CHAR(64) NOT NULL, release_digest CHAR(64) NOT NULL, status VARCHAR(16) NOT NULL,
  lease_owner VARCHAR(128), lease_expires_at DATETIME(3), failure_code VARCHAR(64), diagnostic_id VARCHAR(128),
  row_version BIGINT NOT NULL DEFAULT 0, created_at DATETIME(3) NOT NULL, updated_at DATETIME(3) NOT NULL,
  UNIQUE INDEX uk_document_validation_run_idempotency (idempotency_digest, request_digest),
  INDEX idx_document_validation_run_recovery (status, lease_expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_validation_report (
  report_id VARCHAR(64) PRIMARY KEY, subject_type VARCHAR(32) NOT NULL, subject_digest CHAR(64) NOT NULL,
  policy_digest CHAR(64) NOT NULL, fixture_digest CHAR(64) NOT NULL, release_digest CHAR(64) NOT NULL,
  status VARCHAR(16) NOT NULL, completed_at DATETIME(3) NOT NULL, expires_at DATETIME(3) NOT NULL,
  integrity_evidence_ref VARCHAR(255) NOT NULL, canonical_digest CHAR(64) NOT NULL, created_by_run_id VARCHAR(64) NOT NULL,
  INDEX idx_document_validation_report_subject (subject_digest, policy_digest, fixture_digest, release_digest)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_validation_provider_subject (
  report_id VARCHAR(64) PRIMARY KEY, operation_type VARCHAR(64) NOT NULL,
  provider_safe_identity VARCHAR(255) NOT NULL, provider_model_identity VARCHAR(255),
  adapter_service_identity_ref VARCHAR(255) NOT NULL, adapter_deployment_ref VARCHAR(255) NOT NULL,
  vendor_contract_version VARCHAR(64) NOT NULL, template_model_digest CHAR(64) NOT NULL,
  provider_binding_digest CHAR(64) NOT NULL, validated_corpus_set_digest CHAR(64) NOT NULL,
  active_profile_coverage_digest CHAR(64) NOT NULL,
  INDEX idx_document_validation_provider_subject (operation_type, provider_binding_digest)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_validation_p1_subject (
  report_id VARCHAR(64) PRIMARY KEY, activation_candidate_digest CHAR(64) NOT NULL,
  java_contract_baseline_digest CHAR(64) NOT NULL, config_candidate_digest CHAR(64) NOT NULL,
  ddl_candidate_digest CHAR(64) NOT NULL,
  INDEX idx_document_validation_p1_subject (activation_candidate_digest)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_validation_gate_result (
  report_id VARCHAR(64) NOT NULL, gate_code VARCHAR(64) NOT NULL, status VARCHAR(16) NOT NULL,
  evidence_digest CHAR(64) NOT NULL, safe_reason_code VARCHAR(64), PRIMARY KEY (report_id, gate_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_validation_metric (
  report_id VARCHAR(64) NOT NULL, metric_code VARCHAR(64) NOT NULL, scope_code VARCHAR(64) NOT NULL,
  metric_value DECIMAL(30,9) NOT NULL, metric_unit VARCHAR(32) NOT NULL, evidence_digest CHAR(64) NOT NULL,
  PRIMARY KEY (report_id, metric_code, scope_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_governance_change (
  change_id VARCHAR(64) PRIMARY KEY, unit_type VARCHAR(32) NOT NULL, unit_key_digest CHAR(64) NOT NULL,
  idempotency_digest CHAR(64) NOT NULL, request_digest CHAR(64) NOT NULL, change_kind VARCHAR(32) NOT NULL,
  expected_state_digest CHAR(64) NOT NULL, target_state_digest CHAR(64) NOT NULL, current_state_digest CHAR(64),
  gate_evidence_ref VARCHAR(255) NOT NULL, actor_safe_ref VARCHAR(255) NOT NULL, approval_safe_ref VARCHAR(255) NOT NULL,
  authentication_evidence_digest CHAR(64),
  emergency_evidence_id CHAR(64), emergency_evidence_digest CHAR(64),
  emergency_evidence_key_id VARCHAR(64), emergency_evidence_key_version VARCHAR(64),
  emergency_evidence_verification_code VARCHAR(32),
  status VARCHAR(20) NOT NULL, related_change_id VARCHAR(64), deadline DATETIME(3) NOT NULL,
  lease_owner VARCHAR(128), lease_expires_at DATETIME(3), row_version BIGINT NOT NULL DEFAULT 0,
  created_at DATETIME(3) NOT NULL, updated_at DATETIME(3) NOT NULL,
  UNIQUE INDEX uk_document_governance_change_idempotency (unit_type, unit_key_digest, idempotency_digest),
  INDEX idx_document_governance_change_reconcile (status, lease_expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_provider_activation (
  operation_type VARCHAR(64) PRIMARY KEY, state VARCHAR(16) NOT NULL,
  provider_safe_identity VARCHAR(255), provider_model_identity VARCHAR(255), adapter_service_identity_ref VARCHAR(255), adapter_deployment_ref VARCHAR(255),
  vendor_contract_version VARCHAR(64), template_model_digest CHAR(64), provider_binding_digest CHAR(64),
  wire_contract_version VARCHAR(32) NOT NULL, rollout_version VARCHAR(64) NOT NULL, valid_until DATETIME(3) NOT NULL,
  snapshot_digest CHAR(64) NOT NULL, emergency_cause_ref VARCHAR(255), row_version BIGINT NOT NULL DEFAULT 0,
  updated_at DATETIME(3) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_provider_activation_ack (
  consumer_id VARCHAR(128) NOT NULL,
  operation_type VARCHAR(64) NOT NULL,
  deployment_digest CHAR(64) NOT NULL,
  activation_digest CHAR(64) NOT NULL,
  observed_at DATETIME(3) NOT NULL,
  PRIMARY KEY (consumer_id, operation_type),
  INDEX idx_document_provider_activation_ack_digest (activation_digest, observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_provider_activation_history (
  history_id VARCHAR(64) PRIMARY KEY, operation_type VARCHAR(64) NOT NULL, state VARCHAR(16) NOT NULL,
  provider_binding_digest CHAR(64), rollout_version VARCHAR(64) NOT NULL, snapshot_digest CHAR(64) NOT NULL,
  change_id VARCHAR(64) NOT NULL, reason_code VARCHAR(64) NOT NULL, created_at DATETIME(3) NOT NULL,
  INDEX idx_document_provider_activation_history (operation_type, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_emergency_control (
  target_type VARCHAR(32) NOT NULL, target_key_digest CHAR(64) NOT NULL, target_canonical VARCHAR(512) NOT NULL,
  state VARCHAR(16) NOT NULL, reason_code VARCHAR(64) NOT NULL, active_change_id VARCHAR(64), cleared_change_id VARCHAR(64),
  effective_at DATETIME(3) NOT NULL, row_version BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (target_type, target_key_digest), INDEX idx_document_emergency_state (state, target_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_governance_event (
  event_id VARCHAR(64) PRIMARY KEY, change_id VARCHAR(64) NOT NULL, event_type VARCHAR(64) NOT NULL,
  status VARCHAR(20) NOT NULL, safe_refs VARCHAR(1024) NOT NULL, reason_code VARCHAR(64), digest_prefixes VARCHAR(255),
  occurred_at DATETIME(3) NOT NULL, delivery_status VARCHAR(16) NOT NULL, delivery_attempt INT NOT NULL DEFAULT 0,
  next_delivery_at DATETIME(3), row_version BIGINT NOT NULL DEFAULT 0,
  INDEX idx_document_governance_event_delivery (delivery_status, next_delivery_at)
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
  capability_id VARCHAR(128),
  plan_kind VARCHAR(32),
  registration_identity VARCHAR(256),
  authorization_snapshot_ref VARCHAR(256),
  context_snapshot_set_digest VARCHAR(128),
  metadata_version VARCHAR(128),
  planning_artifact_binding_digest VARCHAR(128),
  checkpoint_json JSON,
  checkpoint_hash VARCHAR(128),
  checkpoint_sequence BIGINT NOT NULL DEFAULT 0,
  error_code VARCHAR(64),
  safe_message TEXT,
  diagnostic_id VARCHAR(128),
  deadline_at DATETIME(3) NOT NULL,
  created_at DATETIME(3) NOT NULL,
  checkpointed_at DATETIME(3),
  completed_at DATETIME(3),
  row_version BIGINT NOT NULL DEFAULT 0,
  UNIQUE INDEX uk_agent_invocation_turn (turn_id),
  UNIQUE INDEX uk_agent_invocation_correlation (request_correlation_id),
  INDEX idx_agent_invocation_state_deadline (state, deadline_at),
  INDEX idx_agent_invocation_subject_created (subject_id, created_at),
  CHECK (invocation_type = 'CHAT' AND origin_type = 'CHAT' AND scope_type = 'CONVERSATION'),
  CHECK ((state = 'PROCESSING' AND response_type IS NULL AND completed_at IS NULL)
      OR (state <> 'PROCESSING' AND response_type IS NOT NULL AND completed_at IS NOT NULL)),
  CHECK ((checkpoint_sequence = 0 AND checkpoint_hash IS NULL
          AND planning_artifact_binding_digest IS NULL)
      OR (checkpoint_sequence = 1 AND checkpoint_hash IS NOT NULL
          AND planning_artifact_binding_digest IS NOT NULL)),
  CONSTRAINT fk_agent_invocation_turn
    FOREIGN KEY (turn_id) REFERENCES agent_turn(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS agent_invocation_result (
  id VARCHAR(64) PRIMARY KEY,
  invocation_id VARCHAR(64) NOT NULL,
  output_contract_namespace VARCHAR(128) NOT NULL,
  output_contract_name VARCHAR(128) NOT NULL,
  output_contract_version VARCHAR(64) NOT NULL,
  payload_json JSON NOT NULL,
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
  contract_namespace VARCHAR(128) NOT NULL,
  contract_name VARCHAR(128) NOT NULL,
  contract_version VARCHAR(64) NOT NULL,
  record_version BIGINT NOT NULL,
  protected_payload_json JSON NOT NULL,
  source_capability_id VARCHAR(128) NOT NULL,
  source_invocation_id VARCHAR(64) NOT NULL,
  source_domain VARCHAR(128),
  readable TINYINT(1) NOT NULL DEFAULT 1,
  expires_at DATETIME(3) NOT NULL,
  created_at DATETIME(3) NOT NULL,
  updated_at DATETIME(3) NOT NULL,
  UNIQUE INDEX uk_agent_context_key (owner_type, owner_id, scope_type, scope_id, context_type),
  INDEX idx_agent_context_expiry (expires_at, readable),
  INDEX idx_agent_context_source_invocation (source_invocation_id),
  CHECK (scope_type = 'CONVERSATION'),
  CHECK (record_version >= 0),
  CHECK (readable IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
