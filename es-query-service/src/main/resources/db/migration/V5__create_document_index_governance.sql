CREATE TABLE document_validation_run (
  run_id VARCHAR(64) PRIMARY KEY, idempotency_digest CHAR(64) NOT NULL, request_digest CHAR(64) NOT NULL,
  subject_digest CHAR(64) NOT NULL, policy_digest CHAR(64) NOT NULL, fixture_digest CHAR(64) NOT NULL,
  release_digest CHAR(64) NOT NULL, status VARCHAR(16) NOT NULL, lease_owner VARCHAR(128), lease_expires_at TIMESTAMP(6),
  failure_code VARCHAR(64), diagnostic_id VARCHAR(128), row_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMP(6) NOT NULL, updated_at TIMESTAMP(6) NOT NULL,
  UNIQUE KEY uk_document_validation_run_idempotency (idempotency_digest, request_digest),
  KEY idx_document_validation_run_recovery (status, lease_expires_at)
);
CREATE TABLE document_validation_report (
  report_id VARCHAR(64) PRIMARY KEY, subject_type VARCHAR(32) NOT NULL, subject_digest CHAR(64) NOT NULL, policy_digest CHAR(64) NOT NULL,
  fixture_digest CHAR(64) NOT NULL, release_digest CHAR(64) NOT NULL, status VARCHAR(16) NOT NULL,
  completed_at TIMESTAMP(6) NOT NULL, expires_at TIMESTAMP(6) NOT NULL, integrity_evidence_ref VARCHAR(255) NOT NULL,
  canonical_digest CHAR(64) NOT NULL, created_by_run_id VARCHAR(64) NOT NULL,
  UNIQUE KEY uk_document_validation_report_subject (subject_digest, policy_digest, fixture_digest, release_digest)
);
CREATE TABLE document_validation_index_subject (
  report_id VARCHAR(64) PRIMARY KEY, corpus_key_digest CHAR(64) NOT NULL,
  target_physical_index_safe_ref VARCHAR(255) NOT NULL, schema_version VARCHAR(64) NOT NULL,
  content_digest CHAR(64) NOT NULL, manifest_digest CHAR(64) NOT NULL,
  attestation_digest CHAR(64) NOT NULL, target_binding_digest CHAR(64) NOT NULL,
  profile_coverage_digest CHAR(64) NOT NULL, embedding_binding_digest CHAR(64),
  UNIQUE KEY uk_document_validation_index_subject(corpus_key_digest,target_binding_digest)
);
CREATE TABLE document_validation_gate_result (
  report_id VARCHAR(64) NOT NULL, gate_code VARCHAR(64) NOT NULL, status VARCHAR(16) NOT NULL,
  evidence_digest CHAR(64) NOT NULL, safe_reason_code VARCHAR(64), PRIMARY KEY(report_id,gate_code)
);
CREATE TABLE document_validation_metric (
  report_id VARCHAR(64) NOT NULL, metric_code VARCHAR(64) NOT NULL, scope_code VARCHAR(64) NOT NULL,
  metric_value DECIMAL(30,9) NOT NULL, metric_unit VARCHAR(32) NOT NULL, evidence_digest CHAR(64) NOT NULL,
  PRIMARY KEY(report_id,metric_code,scope_code)
);
CREATE TABLE document_governance_change (
  change_id VARCHAR(64) PRIMARY KEY, unit_type VARCHAR(32) NOT NULL, unit_key_digest CHAR(64) NOT NULL,
  idempotency_digest CHAR(64) NOT NULL, request_digest CHAR(64) NOT NULL, change_kind VARCHAR(32) NOT NULL,
  expected_state_digest CHAR(64) NOT NULL, target_state_digest CHAR(64) NOT NULL, current_state_digest CHAR(64),
  gate_evidence_ref VARCHAR(255) NOT NULL, actor_safe_ref VARCHAR(255) NOT NULL, approval_safe_ref VARCHAR(255) NOT NULL,
  authentication_evidence_digest CHAR(64) NOT NULL,
  emergency_evidence_id CHAR(64) NOT NULL, emergency_evidence_digest CHAR(64) NOT NULL,
  emergency_evidence_key_id VARCHAR(64) NOT NULL, emergency_evidence_key_version VARCHAR(64) NOT NULL,
  emergency_evidence_verification_code VARCHAR(32) NOT NULL,
  status VARCHAR(20) NOT NULL, related_change_id VARCHAR(64), deadline TIMESTAMP(6) NOT NULL,
  lease_owner VARCHAR(128), lease_expires_at TIMESTAMP(6), row_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMP(6) NOT NULL, updated_at TIMESTAMP(6) NOT NULL,
  UNIQUE KEY uk_document_index_change_idempotency(unit_type,unit_key_digest,idempotency_digest),
  KEY idx_document_index_change_reconcile(status,lease_expires_at)
);
CREATE TABLE document_governance_event (
  event_id VARCHAR(64) PRIMARY KEY, change_id VARCHAR(64) NOT NULL, event_type VARCHAR(64) NOT NULL,
  status VARCHAR(20) NOT NULL, safe_refs VARCHAR(1024) NOT NULL, reason_code VARCHAR(64), digest_prefixes VARCHAR(255),
  occurred_at TIMESTAMP(6) NOT NULL, delivery_status VARCHAR(16) NOT NULL, delivery_attempt INT NOT NULL DEFAULT 0,
  next_delivery_at TIMESTAMP(6), row_version BIGINT NOT NULL DEFAULT 0,
  KEY idx_document_index_event_delivery(delivery_status,next_delivery_at)
);
