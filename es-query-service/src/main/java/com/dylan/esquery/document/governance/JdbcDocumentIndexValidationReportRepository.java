package com.dylan.esquery.document.governance;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;

/** INDEX_RELEASE DVR-1 append-only authority；header与typed subject projection同事务写入。 */
@Repository
public final class JdbcDocumentIndexValidationReportRepository {
    private final JdbcTemplate jdbc;

    public JdbcDocumentIndexValidationReportRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Transactional
    public void append(IndexValidationReport report) {
        IndexReportAuthority authority = authority(report.subject(), report.reportId(), report.canonicalDigest(),
                report.status(), report.expiresAt());
        if (!authority.subjectDigest().equals(report.subjectDigest())) {
            throw new IllegalArgumentException("index validation report subject canonical mismatch");
        }
        if (jdbc.update("INSERT INTO document_validation_report(report_id,subject_type,subject_digest,policy_digest,fixture_digest,release_digest,status,completed_at,expires_at,integrity_evidence_ref,canonical_digest,created_by_run_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                report.reportId(), "INDEX_RELEASE", report.subjectDigest(), report.policyDigest(),
                report.fixtureDigest(), report.releaseDigest(), report.status().name(), Timestamp.from(report.completedAt()),
                Timestamp.from(report.expiresAt()), report.integrityEvidenceRef(), report.canonicalDigest(),
                report.createdByRunId()) != 1) {
            throw new IllegalStateException("index validation report append failed");
        }
        IndexSubjectProjection subject = report.subject();
        if (jdbc.update("INSERT INTO document_validation_index_subject(report_id,corpus_key_digest,target_physical_index_safe_ref,schema_version,content_digest,manifest_digest,attestation_digest,target_binding_digest,profile_coverage_digest,embedding_binding_digest) VALUES(?,?,?,?,?,?,?,?,?,?)",
                report.reportId(), authority.corpusKeyDigest(), subject.targetPhysicalIndexSafeRef(),
                subject.schemaVersion(), subject.contentDigest(), subject.manifestDigest(), subject.attestationDigest(),
                authority.targetBinding().canonicalDigest(), subject.profileCoverageDigest(),
                subject.embeddingBindingDigest().orElse(null)) != 1) {
            throw new IllegalStateException("index validation subject projection append failed");
        }
        for (GateResult gate : report.gates().stream().sorted(Comparator.comparing(GateResult::gateCode)).toList()) {
            jdbc.update("INSERT INTO document_validation_gate_result(report_id,gate_code,status,evidence_digest,safe_reason_code) VALUES(?,?,?,?,?)",
                    report.reportId(), gate.gateCode(), gate.status().name(), gate.evidenceDigest(), gate.safeReasonCode());
        }
        for (Metric metric : report.metrics().stream()
                .sorted(Comparator.comparing(Metric::metricCode).thenComparing(Metric::scopeCode)).toList()) {
            jdbc.update("INSERT INTO document_validation_metric(report_id,metric_code,scope_code,metric_value,metric_unit,evidence_digest) VALUES(?,?,?,?,?,?)",
                    report.reportId(), metric.metricCode(), metric.scopeCode(), metric.value(), metric.unit(), metric.evidenceDigest());
        }
    }

    public IndexReportAuthority requirePassed(String reportId, DocumentCorpusKeyDto corpusKey, Instant now) {
        String corpusDigest = corpusKeyDigest(corpusKey);
        List<IndexReportAuthority> rows = jdbc.query("SELECT r.report_id,r.subject_digest,r.canonical_digest,r.status,r.expires_at,s.target_physical_index_safe_ref,s.schema_version,s.content_digest,s.manifest_digest,s.attestation_digest,s.target_binding_digest,s.profile_coverage_digest,s.embedding_binding_digest FROM document_validation_report r JOIN document_validation_index_subject s ON s.report_id=r.report_id WHERE r.report_id=? AND r.subject_type='INDEX_RELEASE' AND s.corpus_key_digest=? AND r.status='PASSED' AND r.expires_at>?",
                (rs, row) -> fromStored(corpusDigest, rs.getString(1), rs.getString(2), rs.getString(3),
                        ReportStatus.valueOf(rs.getString(4)), rs.getTimestamp(5).toInstant(), rs.getString(6),
                        rs.getString(7), rs.getString(8), rs.getString(9), rs.getString(10), rs.getString(11),
                        rs.getString(12), Optional.ofNullable(rs.getString(13))),
                reportId, corpusDigest, Timestamp.from(now));
        if (rows.size() != 1) throw new IllegalStateException("current PASSED index validation report required");
        return rows.getFirst();
    }

    public IndexReportAuthority requireByTarget(String corpusKeyDigest, String targetBindingDigest) {
        List<IndexReportAuthority> rows = jdbc.query("SELECT r.report_id,r.subject_digest,r.canonical_digest,r.status,r.expires_at,s.target_physical_index_safe_ref,s.schema_version,s.content_digest,s.manifest_digest,s.attestation_digest,s.target_binding_digest,s.profile_coverage_digest,s.embedding_binding_digest FROM document_validation_report r JOIN document_validation_index_subject s ON s.report_id=r.report_id WHERE r.subject_type='INDEX_RELEASE' AND s.corpus_key_digest=? AND s.target_binding_digest=?",
                (rs, row) -> fromStored(corpusKeyDigest, rs.getString(1), rs.getString(2), rs.getString(3),
                        ReportStatus.valueOf(rs.getString(4)), rs.getTimestamp(5).toInstant(), rs.getString(6),
                        rs.getString(7), rs.getString(8), rs.getString(9), rs.getString(10), rs.getString(11),
                        rs.getString(12), Optional.ofNullable(rs.getString(13))), corpusKeyDigest, targetBindingDigest);
        if (rows.size() != 1) throw new IllegalStateException("index validation target projection unavailable");
        return rows.getFirst();
    }

    private static IndexReportAuthority fromStored(String corpusDigest, String reportId, String subjectDigest,
            String reportDigest, ReportStatus status, Instant expiresAt, String targetSafeRef, String schemaVersion,
            String contentDigest, String manifestDigest, String attestationDigest, String storedBindingDigest,
            String profileCoverageDigest, Optional<String> embeddingBindingDigest) {
        IndexTargetBindingReference binding = targetBinding(schemaVersion, contentDigest, manifestDigest, attestationDigest);
        if (!binding.canonicalDigest().equals(storedBindingDigest)) {
            throw new IllegalStateException("stored index target binding canonical mismatch");
        }
        String recomputedSubject = indexSubjectDigest(corpusDigest, manifestDigest, storedBindingDigest,
                profileCoverageDigest, embeddingBindingDigest);
        if (!recomputedSubject.equals(subjectDigest)) {
            throw new IllegalStateException("stored index validation subject canonical mismatch");
        }
        return new IndexReportAuthority(reportId, corpusDigest, subjectDigest, reportDigest, status, expiresAt,
                targetSafeRef, binding, profileCoverageDigest, embeddingBindingDigest);
    }

    private static IndexReportAuthority authority(IndexSubjectProjection subject, String reportId,
            String reportDigest, ReportStatus status, Instant expiresAt) {
        String corpusDigest = corpusKeyDigest(subject.corpusKey());
        IndexTargetBindingReference binding = targetBinding(subject.schemaVersion(), subject.contentDigest(),
                subject.manifestDigest(), subject.attestationDigest());
        return new IndexReportAuthority(reportId, corpusDigest,
                indexSubjectDigest(corpusDigest, subject.manifestDigest(), binding.canonicalDigest(),
                        subject.profileCoverageDigest(), subject.embeddingBindingDigest()),
                reportDigest, status, expiresAt, subject.targetPhysicalIndexSafeRef(), binding,
                subject.profileCoverageDigest(), subject.embeddingBindingDigest());
    }

    public static String corpusKeyDigest(DocumentCorpusKeyDto corpusKey) {
        return sha256(corpusKey.canonicalBytes());
    }

    public static IndexTargetBindingReference targetBinding(String schemaVersion, String contentDigest,
            String manifestDigest, String attestationDigest) {
        return new IndexTargetBindingReference(schemaVersion, contentDigest, manifestDigest, attestationDigest,
                canonical("ITB-1", schemaVersion, contentDigest, manifestDigest, attestationDigest));
    }

    public static String indexSubjectDigest(String corpusKeyDigest, String manifestDigest,
            String targetBindingDigest, String profileCoverageDigest, Optional<String> embeddingBindingDigest) {
        requireDigest(corpusKeyDigest, "corpusKeyDigest");
        requireDigest(manifestDigest, "manifestDigest");
        requireDigest(targetBindingDigest, "targetBindingDigest");
        requireDigest(profileCoverageDigest, "profileCoverageDigest");
        embeddingBindingDigest.ifPresent(value -> requireDigest(value, "embeddingBindingDigest"));
        return canonical("DVS-INDEX-1", corpusKeyDigest, manifestDigest, targetBindingDigest,
                profileCoverageDigest, embeddingBindingDigest.orElse(""));
    }

    public static String reportCanonical(String subjectDigest,String policyDigest,String fixtureDigest,
            String releaseDigest,ReportStatus status,List<GateResult> gates,List<Metric> metrics,
            Instant completedAt,Instant expiresAt,String integrityEvidenceRef){
        java.util.ArrayList<String> values=new java.util.ArrayList<>(List.of("DVR-1",subjectDigest,policyDigest,
                fixtureDigest,releaseDigest,status.name(),completedAt.toString(),expiresAt.toString(),integrityEvidenceRef));
        for(GateResult gate:gates.stream().sorted(Comparator.comparing(GateResult::gateCode)).toList()){
            values.add(gate.gateCode());values.add(gate.status().name());values.add(gate.evidenceDigest());
            values.add(gate.safeReasonCode()==null?"":gate.safeReasonCode());
        }
        for(Metric metric:metrics.stream().sorted(Comparator.comparing(Metric::metricCode).thenComparing(Metric::scopeCode)).toList()){
            values.add(metric.metricCode());values.add(metric.scopeCode());values.add(metric.value().toPlainString());
            values.add(metric.unit());values.add(metric.evidenceDigest());
        }
        return canonical(values.toArray(String[]::new));
    }

    static String canonical(String... values) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (String value : values) {
                byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
                digest.update(ByteBuffer.allocate(4).putInt(bytes.length).array());
                digest.update(bytes);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (Exception ex) { throw new IllegalStateException(ex); }
    }

    private static String sha256(byte[] value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value)); }
        catch (Exception ex) { throw new IllegalStateException(ex); }
    }

    static void requireDigest(String value, String name) {
        if (value == null || !value.matches("[0-9a-f]{64}")) throw new IllegalArgumentException(name + " must be SHA-256 hex");
    }

    static void requireText(String value, String name) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " must not be blank");
    }

    public enum ReportStatus { PASSED, BLOCKED, FAILED }
    public enum GateStatus { PASSED, FAILED, NOT_EVALUATED }

    public record IndexSubjectProjection(DocumentCorpusKeyDto corpusKey, String targetPhysicalIndexSafeRef,
            String schemaVersion, String contentDigest, String manifestDigest, String attestationDigest,
            String profileCoverageDigest, Optional<String> embeddingBindingDigest) {
        public IndexSubjectProjection {
            if (corpusKey == null) throw new NullPointerException("corpusKey must not be null");
            requireText(targetPhysicalIndexSafeRef, "targetPhysicalIndexSafeRef");
            requireText(schemaVersion, "schemaVersion");
            requireDigest(contentDigest, "contentDigest"); requireDigest(manifestDigest, "manifestDigest");
            requireDigest(attestationDigest, "attestationDigest"); requireDigest(profileCoverageDigest, "profileCoverageDigest");
            embeddingBindingDigest = embeddingBindingDigest == null ? Optional.empty() : embeddingBindingDigest;
            embeddingBindingDigest.ifPresent(value -> requireDigest(value, "embeddingBindingDigest"));
        }
    }

    public record GateResult(String gateCode, GateStatus status, String evidenceDigest, String safeReasonCode) {
        public GateResult {
            requireText(gateCode, "gateCode"); if (status == null) throw new NullPointerException("status must not be null");
            requireDigest(evidenceDigest, "evidenceDigest");
            if (status != GateStatus.PASSED) requireText(safeReasonCode, "safeReasonCode");
        }
    }

    public record Metric(String metricCode, String scopeCode, BigDecimal value, String unit, String evidenceDigest) {
        public Metric {
            requireText(metricCode, "metricCode"); requireText(scopeCode, "scopeCode");
            if (value == null) throw new NullPointerException("value must not be null");
            value = value.setScale(9, java.math.RoundingMode.UNNECESSARY);
            requireText(unit, "unit"); requireDigest(evidenceDigest, "evidenceDigest");
        }
    }

    public record IndexValidationReport(String reportId, String subjectDigest, IndexSubjectProjection subject,
            String policyDigest, String fixtureDigest, String releaseDigest, ReportStatus status,
            List<GateResult> gates, List<Metric> metrics, Instant completedAt, Instant expiresAt,
            String integrityEvidenceRef, String canonicalDigest, String createdByRunId) {
        public IndexValidationReport {
            requireText(reportId, "reportId"); requireDigest(subjectDigest, "subjectDigest");
            if (subject == null || status == null) throw new NullPointerException("subject/status must not be null");
            requireDigest(policyDigest, "policyDigest"); requireDigest(fixtureDigest, "fixtureDigest");
            requireDigest(releaseDigest, "releaseDigest"); gates = List.copyOf(gates); metrics = List.copyOf(metrics);
            if(new java.util.HashSet<>(gates.stream().map(GateResult::gateCode).toList()).size()!=gates.size())
                throw new IllegalArgumentException("validation report contains duplicate gates");
            if(new java.util.HashSet<>(metrics.stream().map(value->value.metricCode()+"\u001f"+value.scopeCode()).toList()).size()!=metrics.size())
                throw new IllegalArgumentException("validation report contains duplicate metrics");
            if (status == ReportStatus.PASSED && (gates.isEmpty() || gates.stream().anyMatch(g -> g.status() != GateStatus.PASSED)))
                throw new IllegalArgumentException("PASSED report requires every gate PASSED");
            if (completedAt == null || expiresAt == null || !completedAt.isBefore(expiresAt))
                throw new IllegalArgumentException("report expiry must be after completion");
            requireText(integrityEvidenceRef, "integrityEvidenceRef"); requireDigest(canonicalDigest, "canonicalDigest");
            requireText(createdByRunId, "createdByRunId");
            String expected=reportCanonical(subjectDigest,policyDigest,fixtureDigest,releaseDigest,status,gates,metrics,
                    completedAt,expiresAt,integrityEvidenceRef);
            if(!expected.equals(canonicalDigest)||!reportId.equals(canonicalDigest))
                throw new IllegalArgumentException("DVR-1 canonical/reportId mismatch");
        }
    }

    public record IndexTargetBindingReference(String schemaVersion, String contentDigest, String manifestDigest,
            String attestationDigest, String canonicalDigest) {}

    public record IndexReportAuthority(String reportId, String corpusKeyDigest, String subjectDigest,
            String reportDigest, ReportStatus status, Instant expiresAt, String targetIndex,
            IndexTargetBindingReference targetBinding, String profileCoverageDigest,
            Optional<String> embeddingBindingDigest) {}
}
