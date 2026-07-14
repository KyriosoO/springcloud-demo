package com.dylan.agent.capability.document.governance.validation;

import com.dylan.agent.adapter.api.document.provider.DocumentProviderBindingReference;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;

/** DVR-1/DRG-1 的封闭治理模型；不包含查询、证据正文或 Provider payload。 */
public final class DocumentValidationModels {
    private DocumentValidationModels() {
    }

    public sealed interface SubjectRef permits ProviderOperationSubjectRef, P1ReleaseCandidateSubjectRef {
        String subjectType();
        String canonicalDigest();
    }

    public record ProviderOperationSubjectRef(
            CapabilityOperationType operationType,
            DocumentProviderBindingReference providerBinding,
            String validatedCorpusSetDigest,
            String activeProfileCoverageDigest) implements SubjectRef {
        public ProviderOperationSubjectRef {
            Objects.requireNonNull(operationType);
            Objects.requireNonNull(providerBinding);
            requireDigest(validatedCorpusSetDigest, "validatedCorpusSetDigest");
            requireDigest(activeProfileCoverageDigest, "activeProfileCoverageDigest");
        }
        @Override public String subjectType() { return "PROVIDER_OPERATION"; }
        @Override public String canonicalDigest() {
            return canonical("DVS-PROVIDER-1", operationType.value(), providerBinding.canonicalDigest(),
                    validatedCorpusSetDigest, activeProfileCoverageDigest);
        }
    }

    public record P1ReleaseCandidateSubjectRef(
            String activationCandidateDigest,
            String javaContractBaselineDigest,
            String configCandidateDigest,
            String ddlCandidateDigest) implements SubjectRef {
        public P1ReleaseCandidateSubjectRef {
            requireDigest(activationCandidateDigest, "activationCandidateDigest");
            requireDigest(javaContractBaselineDigest, "javaContractBaselineDigest");
            requireDigest(configCandidateDigest, "configCandidateDigest");
            requireDigest(ddlCandidateDigest, "ddlCandidateDigest");
        }
        @Override public String subjectType() { return "P1_RELEASE_CANDIDATE"; }
        @Override public String canonicalDigest() {
            return canonical("DVS-P1-1", activationCandidateDigest, javaContractBaselineDigest,
                    configCandidateDigest, ddlCandidateDigest);
        }
    }

    public record PolicyRef(String policyVersion, String validatorSuiteVersion, String canonicalDigest) {
        public PolicyRef {
            requireText(policyVersion, "policyVersion");
            requireText(validatorSuiteVersion, "validatorSuiteVersion");
            requireDigest(canonicalDigest, "canonicalDigest");
            if(!canonical("DVP-1",policyVersion,validatorSuiteVersion).equals(canonicalDigest))
                throw new IllegalArgumentException("validation policy canonical mismatch");
        }
    }

    public enum ReportStatus { PASSED, BLOCKED, FAILED }
    public enum GateStatus { PASSED, FAILED, NOT_EVALUATED }
    public enum GateCode {
        INDEX_TECHNICAL, CORPUS_PROFILE_BINDING, ACL_ALLOW, ACL_DENY_REVOKED,
        PROTECTED_FILTER_ALL_CHANNELS, RETRIEVAL_CONTRACT, RETRIEVAL_QUALITY,
        PROVIDER_CONTRACT_SECURITY, PROVIDER_ATTEMPT_DEADLINE_CANCEL,
        EMBEDDING_INDEX_COMPATIBILITY, GENERATION_CITATION, GENERATION_FACTUALITY,
        RESULT_SECURITY_CANDIDATE_LEAK, CAPACITY_BULKHEAD, OBSERVABILITY_AUDIT,
        ROLLBACK_DRY_RUN, CONTRACT_MIGRATION_CLEANUP
    }
    public enum MetricUnit { COUNT, RATIO, MILLISECONDS, BYTES, REQUESTS_PER_SECOND }

    public record GateResult(GateCode gateCode, GateStatus status, String evidenceDigest, String safeReasonCode) {
        public GateResult {
            Objects.requireNonNull(gateCode);
            Objects.requireNonNull(status);
            requireDigest(evidenceDigest, "evidenceDigest");
            if (status != GateStatus.PASSED) requireText(safeReasonCode, "safeReasonCode");
        }
    }

    public record Metric(
            String metricCode,
            String scopeCode,
            BigDecimal value,
            MetricUnit unit,
            String evidenceDigest) {
        public Metric {
            requireText(metricCode, "metricCode");
            requireText(scopeCode, "scopeCode");
            Objects.requireNonNull(value);
            value = value.setScale(9, java.math.RoundingMode.UNNECESSARY);
            Objects.requireNonNull(unit);
            requireDigest(evidenceDigest, "evidenceDigest");
        }
    }

    public record Report(
            String reportId,
            SubjectRef subject,
            PolicyRef policy,
            String fixtureDigest,
            String releaseDigest,
            ReportStatus status,
            List<GateResult> gates,
            List<Metric> metrics,
            Instant completedAt,
            Instant expiresAt,
            String integrityEvidenceRef,
            String canonicalDigest,
            String createdByRunId) {
        public Report {
            requireText(reportId, "reportId");
            Objects.requireNonNull(subject);
            Objects.requireNonNull(policy);
            requireDigest(fixtureDigest, "fixtureDigest");
            requireDigest(releaseDigest, "releaseDigest");
            Objects.requireNonNull(status);
            gates = List.copyOf(gates).stream().sorted(Comparator.comparing(GateResult::gateCode)).toList();
            metrics = List.copyOf(metrics).stream()
                    .sorted(Comparator.comparing(Metric::metricCode).thenComparing(Metric::scopeCode)).toList();
            if (new java.util.HashSet<>(gates.stream().map(GateResult::gateCode).toList()).size() != gates.size()) {
                throw new IllegalArgumentException("validation report contains duplicate gates");
            }
            if (new java.util.HashSet<>(metrics.stream().map(value -> value.metricCode()+"\u001f"+value.scopeCode()).toList()).size() != metrics.size()) {
                throw new IllegalArgumentException("validation report contains duplicate metrics");
            }
            if (status == ReportStatus.PASSED && (gates.isEmpty()
                    || gates.stream().anyMatch(g -> g.status() != GateStatus.PASSED))) {
                throw new IllegalArgumentException("PASSED report requires every gate PASSED");
            }
            Objects.requireNonNull(completedAt);
            Objects.requireNonNull(expiresAt);
            if (!completedAt.isBefore(expiresAt)) throw new IllegalArgumentException("report expiry must be after completion");
            requireText(integrityEvidenceRef, "integrityEvidenceRef");
            requireDigest(canonicalDigest, "canonicalDigest");
            requireText(createdByRunId, "createdByRunId");
            String expected=reportCanonical(subject.canonicalDigest(),policy.canonicalDigest(),fixtureDigest,releaseDigest,
                    status,gates,metrics,completedAt,expiresAt,integrityEvidenceRef);
            if(!expected.equals(canonicalDigest)||!reportId.equals(canonicalDigest))
                throw new IllegalArgumentException("DVR-1 canonical/reportId mismatch");
        }
    }

    public record ReleaseGateEvidence(
            String evidenceId,
            String unitType,
            String unitKeyDigest,
            String exactTargetStateDigest,
            String reportCanonicalDigest,
            String approvalSafeRef,
            Instant issuedAt,
            Instant expiresAt,
            String canonicalDigest) {
        public ReleaseGateEvidence {
            requireText(evidenceId, "evidenceId");
            requireText(unitType, "unitType");
            requireDigest(unitKeyDigest, "unitKeyDigest");
            requireDigest(exactTargetStateDigest, "exactTargetStateDigest");
            requireDigest(reportCanonicalDigest, "reportCanonicalDigest");
            requireText(approvalSafeRef, "approvalSafeRef");
            Objects.requireNonNull(issuedAt);
            Objects.requireNonNull(expiresAt);
            if (!issuedAt.isBefore(expiresAt)) throw new IllegalArgumentException("gate evidence must expire after issue");
            requireDigest(canonicalDigest, "canonicalDigest");
        }
    }

    static void requireDigest(String value, String name) {
        if (value == null || !value.matches("[0-9a-f]{64}")) throw new IllegalArgumentException(name + " must be SHA-256 hex");
    }

    static void requireText(String value, String name) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " must not be blank");
    }

    public static String policyDigest(String policyVersion,String validatorSuiteVersion){return canonical("DVP-1",policyVersion,validatorSuiteVersion);}
    public static String reportCanonical(String subjectDigest,String policyDigest,String fixtureDigest,String releaseDigest,
            ReportStatus status,List<GateResult> gates,List<Metric> metrics,Instant completedAt,Instant expiresAt,String integrityRef){
        java.util.ArrayList<String> values=new java.util.ArrayList<>(List.of("DVR-1",subjectDigest,policyDigest,fixtureDigest,
                releaseDigest,status.name(),completedAt.toString(),expiresAt.toString(),integrityRef));
        for(GateResult gate:gates.stream().sorted(Comparator.comparing(GateResult::gateCode)).toList()){
            values.add(gate.gateCode().name());values.add(gate.status().name());values.add(gate.evidenceDigest());
            values.add(gate.safeReasonCode()==null?"":gate.safeReasonCode());
        }
        for(Metric metric:metrics.stream().sorted(Comparator.comparing(Metric::metricCode).thenComparing(Metric::scopeCode)).toList()){
            values.add(metric.metricCode());values.add(metric.scopeCode());values.add(metric.value().toPlainString());
            values.add(metric.unit().name());values.add(metric.evidenceDigest());
        }
        return canonical(values.toArray(String[]::new));
    }
    static String canonical(String... values){
        try{MessageDigest digest=MessageDigest.getInstance("SHA-256");for(String value:values){byte[] bytes=value.getBytes(StandardCharsets.UTF_8);digest.update(ByteBuffer.allocate(4).putInt(bytes.length).array());digest.update(bytes);}return HexFormat.of().formatHex(digest.digest());}
        catch(Exception ex){throw new IllegalStateException(ex);}
    }
}
