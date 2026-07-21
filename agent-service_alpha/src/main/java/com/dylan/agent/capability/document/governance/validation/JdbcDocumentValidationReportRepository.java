package com.dylan.agent.capability.document.governance.validation;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Optional;

/** append-only DVR-1 repository；没有 update/delete 能力。 */
public final class JdbcDocumentValidationReportRepository {
    private final JdbcTemplate jdbc;
    private final com.dylan.agent.adapter.api.document.provider.DocumentProviderCanonicalizer providerCanonicalizer;

    public JdbcDocumentValidationReportRepository(JdbcTemplate jdbc,
            com.dylan.agent.adapter.api.document.provider.DocumentProviderCanonicalizer providerCanonicalizer) {
        this.jdbc = jdbc; this.providerCanonicalizer = providerCanonicalizer;
    }

    @Transactional
    public void append(DocumentValidationModels.Report report) {
        int inserted = jdbc.update("INSERT INTO document_validation_report(report_id,subject_type,subject_digest,policy_digest,fixture_digest,release_digest,status,completed_at,expires_at,integrity_evidence_ref,canonical_digest,created_by_run_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                report.reportId(), report.subject().subjectType(), report.subject().canonicalDigest(),
                report.policy().canonicalDigest(), report.fixtureDigest(), report.releaseDigest(), report.status().name(),
                Timestamp.from(report.completedAt()), Timestamp.from(report.expiresAt()), report.integrityEvidenceRef(),
                report.canonicalDigest(), report.createdByRunId());
        if (inserted != 1) throw new IllegalStateException("validation report append failed");
        appendSubjectProjection(report);
        for (var gate : report.gates()) {
            jdbc.update("INSERT INTO document_validation_gate_result(report_id,gate_code,status,evidence_digest,safe_reason_code) VALUES(?,?,?,?,?)",
                    report.reportId(), gate.gateCode().name(), gate.status().name(), gate.evidenceDigest(), gate.safeReasonCode());
        }
        for (var metric : report.metrics()) {
            jdbc.update("INSERT INTO document_validation_metric(report_id,metric_code,scope_code,metric_value,metric_unit,evidence_digest) VALUES(?,?,?,?,?,?)",
                    report.reportId(), metric.metricCode(), metric.scopeCode(), metric.value(), metric.unit().name(), metric.evidenceDigest());
        }
    }

    private void appendSubjectProjection(DocumentValidationModels.Report report) {
        switch (report.subject()) {
            case DocumentValidationModels.ProviderOperationSubjectRef subject -> {
                var binding = subject.providerBinding();
                if(!binding.canonicalDigest().equals(providerCanonicalizer.providerBindingDigest(binding))){
                    throw new IllegalArgumentException("provider validation subject binding canonical mismatch");
                }
                int inserted = jdbc.update("INSERT INTO document_validation_provider_subject(report_id,operation_type,provider_safe_identity,provider_model_identity,adapter_service_identity_ref,adapter_deployment_ref,vendor_contract_version,template_model_digest,provider_binding_digest,validated_corpus_set_digest,active_profile_coverage_digest) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        report.reportId(), subject.operationType().value(), binding.provider().providerId(),
                        binding.provider().modelRef().orElse(null), binding.adapterServiceIdentityRef(),
                        binding.adapterDeploymentRef(), binding.vendorContractVersion(),
                        binding.templateOrModelBindingDigest(), binding.canonicalDigest(),
                        subject.validatedCorpusSetDigest(), subject.activeProfileCoverageDigest());
                if (inserted != 1) throw new IllegalStateException("provider validation subject projection append failed");
            }
            case DocumentValidationModels.P1ReleaseCandidateSubjectRef subject -> {
                int inserted = jdbc.update("INSERT INTO document_validation_p1_subject(report_id,activation_candidate_digest,java_contract_baseline_digest,config_candidate_digest,ddl_candidate_digest) VALUES(?,?,?,?,?)",
                        report.reportId(), subject.activationCandidateDigest(), subject.javaContractBaselineDigest(),
                        subject.configCandidateDigest(), subject.ddlCandidateDigest());
                if (inserted != 1) throw new IllegalStateException("P1 validation subject projection append failed");
            }
        }
    }

    public Optional<ReportAuthorityView> findPassedCurrent(String reportDigest, Instant now) {
        return jdbc.query("SELECT report_id,subject_type,subject_digest,policy_digest,release_digest,expires_at,canonical_digest FROM document_validation_report WHERE canonical_digest=? AND status='PASSED' AND expires_at>?",
                (rs, row) -> new ReportAuthorityView(rs.getString(1), rs.getString(2), rs.getString(3),
                        rs.getString(4), rs.getString(5), rs.getTimestamp(6).toInstant(), rs.getString(7)),
                reportDigest, Timestamp.from(now)).stream().findFirst();
    }

    public Optional<ProviderReportAuthorityView> findPassedProviderById(
            String reportId,com.dylan.agent.adapter.api.operation.CapabilityOperationType operationType,Instant now){
        var rows=jdbc.query("SELECT r.report_id,r.subject_digest,r.canonical_digest,r.expires_at,s.provider_safe_identity,s.provider_model_identity,s.adapter_service_identity_ref,s.adapter_deployment_ref,s.vendor_contract_version,s.template_model_digest,s.provider_binding_digest,s.validated_corpus_set_digest,s.active_profile_coverage_digest FROM document_validation_report r JOIN document_validation_provider_subject s ON s.report_id=r.report_id WHERE r.report_id=? AND r.subject_type='PROVIDER_OPERATION' AND s.operation_type=? AND r.status='PASSED' AND r.expires_at>?",
                (rs,row)->{
                    var provider=new com.dylan.agent.adapter.api.operation.ProviderSafeIdentity(rs.getString(5),Optional.ofNullable(rs.getString(6)));
                    var binding=new com.dylan.agent.adapter.api.document.provider.DocumentProviderBindingReference(
                            operationType,provider,rs.getString(7),rs.getString(8),rs.getString(9),rs.getString(10),rs.getString(11));
                    if(!binding.canonicalDigest().equals(providerCanonicalizer.providerBindingDigest(binding)))throw new IllegalStateException("stored provider binding canonical mismatch");
                    var subject=new DocumentValidationModels.ProviderOperationSubjectRef(
                            operationType,binding,rs.getString(12),rs.getString(13));
                    if(!subject.canonicalDigest().equals(rs.getString(2)))throw new IllegalStateException("stored provider validation subject canonical mismatch");
                    return new ProviderReportAuthorityView(rs.getString(1),rs.getString(2),rs.getString(3),rs.getTimestamp(4).toInstant(),
                            binding,rs.getString(12),rs.getString(13));
                },reportId,operationType.value(),Timestamp.from(now));
        if(rows.size()!=1)return Optional.empty();
        assertRequiredProviderGates(reportId,operationType,rows.getFirst());
        return Optional.of(rows.getFirst());
    }

    private void assertRequiredProviderGates(
            String reportId,
            com.dylan.agent.adapter.api.operation.CapabilityOperationType operationType,
            ProviderReportAuthorityView report) {
        var subject=new DocumentValidationModels.ProviderOperationSubjectRef(
                operationType,report.binding(),report.validatedCorpusSetDigest(),report.activeProfileCoverageDigest());
        java.util.Map<DocumentValidationModels.GateCode,DocumentValidationModels.GateStatus> gates=
                new java.util.EnumMap<>(DocumentValidationModels.GateCode.class);
        jdbc.query("SELECT gate_code,status FROM document_validation_gate_result WHERE report_id=?", rs -> {
            var code=DocumentValidationModels.GateCode.valueOf(rs.getString(1));
            var status=DocumentValidationModels.GateStatus.valueOf(rs.getString(2));
            if(gates.putIfAbsent(code,status)!=null)throw new IllegalStateException("duplicate stored provider validation gate");
        },reportId);
        if(!gates.keySet().containsAll(DocumentValidationModels.requiredGates(subject))
                ||DocumentValidationModels.requiredGates(subject).stream()
                .anyMatch(code->gates.get(code)!=DocumentValidationModels.GateStatus.PASSED)){
            throw new IllegalStateException("stored provider PASSED report gate set incomplete");
        }
    }

    public record ReportAuthorityView(String reportId, String subjectType, String subjectDigest,
                                      String policyDigest, String releaseDigest, Instant expiresAt,
                                      String canonicalDigest) {}
    public record ProviderReportAuthorityView(String reportId,String subjectDigest,String reportCanonicalDigest,
                                              Instant expiresAt,
                                              com.dylan.agent.adapter.api.document.provider.DocumentProviderBindingReference binding,
                                              String validatedCorpusSetDigest,String activeProfileCoverageDigest) {}
}
