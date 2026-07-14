-- 同一 exact subject 必须允许在报告过期或 policy/fixture 更新后重新验证；幂等由 validation run 管理。
ALTER TABLE document_validation_report
  DROP INDEX uk_document_validation_report_subject,
  ADD KEY idx_document_validation_report_subject (subject_digest, policy_digest, fixture_digest, release_digest);

ALTER TABLE document_validation_index_subject
  DROP INDEX uk_document_validation_index_subject,
  ADD KEY idx_document_validation_index_subject (corpus_key_digest, target_binding_digest);
