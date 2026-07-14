package com.dylan.agent.capability.document.governance.validation;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Clock;
import java.time.Duration;
import java.util.HexFormat;

/** 根据 current immutable report 生成一次 exact change 的短效 DRG-1 evidence。 */
public final class DocumentReleaseGateEvaluator {
    private final JdbcDocumentValidationReportRepository reports;
    private final Clock clock;
    private final Duration evidenceTtl;

    public DocumentReleaseGateEvaluator(JdbcDocumentValidationReportRepository reports, Clock clock, Duration evidenceTtl) {
        this.reports = reports;
        this.clock = clock;
        this.evidenceTtl = evidenceTtl;
        if (evidenceTtl.isNegative() || evidenceTtl.isZero() || evidenceTtl.compareTo(Duration.ofMinutes(10)) > 0) {
            throw new IllegalArgumentException("release gate evidence TTL must be 1ms-10m");
        }
    }

    public DocumentValidationModels.ReleaseGateEvidence evaluate(
            String unitType, String unitKeyDigest, String expectedStateDigest, String targetStateDigest,
            String reportDigest, String expectedReportSubjectDigest, String approvalSafeRef) {
        DocumentValidationModels.requireText(unitType, "unitType");
        if (!java.util.Set.of("PROVIDER_OPERATION", "P1_RELEASE_CANDIDATE").contains(unitType)) {
            throw new IllegalArgumentException("unsupported release gate unit type");
        }
        DocumentValidationModels.requireDigest(unitKeyDigest, "unitKeyDigest");
        DocumentValidationModels.requireDigest(expectedStateDigest, "expectedStateDigest");
        DocumentValidationModels.requireDigest(targetStateDigest, "targetStateDigest");
        DocumentValidationModels.requireDigest(reportDigest, "reportDigest");
        DocumentValidationModels.requireDigest(expectedReportSubjectDigest, "expectedReportSubjectDigest");
        DocumentValidationModels.requireText(approvalSafeRef, "approvalSafeRef");
        var now = clock.instant();
        var report = reports.findPassedCurrent(reportDigest, now)
                .orElseThrow(() -> new IllegalStateException("current PASSED validation report required"));
        if (!report.subjectType().equals(unitType)) {
            throw new IllegalStateException("validation report subject type does not bind change unit");
        }
        if (!report.subjectDigest().equals(expectedReportSubjectDigest)) {
            throw new IllegalStateException("validation report subject does not bind change unit");
        }
        var expiresAt = now.plus(evidenceTtl).isBefore(report.expiresAt()) ? now.plus(evidenceTtl) : report.expiresAt();
        String digest = canonical("DRG-1", unitType, unitKeyDigest, expectedStateDigest, targetStateDigest, reportDigest,
                approvalSafeRef, now.toString(), expiresAt.toString());
        return new DocumentValidationModels.ReleaseGateEvidence(
                "DRG-" + digest.substring(0, 20), unitType, unitKeyDigest, expectedStateDigest, targetStateDigest,
                reportDigest, approvalSafeRef, now, expiresAt, digest);
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
}
