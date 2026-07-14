package com.dylan.agent.capability.document.governance.validation;

import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class DocumentReleaseGateEvaluatorTest {
    private static final Instant NOW = Instant.parse("2026-07-14T00:00:00Z");

    @Test
    void emitsLengthPrefixedExactTargetGateBoundByCurrentReport() {
        JdbcDocumentValidationReportRepository reports = mock(JdbcDocumentValidationReportRepository.class);
        String subject = "a".repeat(64);
        String reportDigest = "b".repeat(64);
        when(reports.findPassedCurrent(reportDigest, NOW)).thenReturn(Optional.of(
                new JdbcDocumentValidationReportRepository.ReportAuthorityView(
                        "report-1", "PROVIDER_OPERATION", subject, "c".repeat(64),
                        "d".repeat(64), NOW.plusSeconds(600), reportDigest)));
        var evaluator = new DocumentReleaseGateEvaluator(reports,
                Clock.fixed(NOW, ZoneOffset.UTC), Duration.ofMinutes(2));

        var gate = evaluator.evaluate("PROVIDER_OPERATION", "f".repeat(64), "e".repeat(64),
                reportDigest, subject, "approval-1");

        assertThat(gate.canonicalDigest()).isEqualTo(DocumentReleaseGateEvaluator.canonical(
                "DRG-1", gate.unitType(), gate.unitKeyDigest(), gate.exactTargetStateDigest(),
                gate.reportCanonicalDigest(), gate.approvalSafeRef(),
                gate.issuedAt().toString(), gate.expiresAt().toString()));
        assertThat(gate.expiresAt()).isEqualTo(NOW.plusSeconds(120));
    }

    @Test
    void rejectsCallerInventedUnitTypeBeforeReadingReport() {
        var evaluator = new DocumentReleaseGateEvaluator(mock(JdbcDocumentValidationReportRepository.class),
                Clock.fixed(NOW, ZoneOffset.UTC), Duration.ofMinutes(2));
        assertThatThrownBy(() -> evaluator.evaluate("INDEX_RELEASE", "a".repeat(64),
                "b".repeat(64), "c".repeat(64), "d".repeat(64), "approval-1"))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("unit type");
    }
}
