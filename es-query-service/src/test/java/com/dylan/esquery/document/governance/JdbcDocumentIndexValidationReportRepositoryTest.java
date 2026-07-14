package com.dylan.esquery.document.governance;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import org.junit.jupiter.api.Test;
import java.util.Optional;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class JdbcDocumentIndexValidationReportRepositoryTest {
    private static final String A="a".repeat(64),B="b".repeat(64),C="c".repeat(64),D="d".repeat(64);
    @Test void indexSubjectCanonicalBindsProfileCoverageAndOptionalEmbedding(){
        String corpus=JdbcDocumentIndexValidationReportRepository.corpusKeyDigest(new DocumentCorpusKeyDto("hr","policy"));
        var binding=JdbcDocumentIndexValidationReportRepository.targetBinding("v1",A,B,C);
        String without=JdbcDocumentIndexValidationReportRepository.indexSubjectDigest(corpus,B,binding.canonicalDigest(),D,Optional.empty());
        String with=JdbcDocumentIndexValidationReportRepository.indexSubjectDigest(corpus,B,binding.canonicalDigest(),D,Optional.of(A));
        String otherProfile=JdbcDocumentIndexValidationReportRepository.indexSubjectDigest(corpus,B,binding.canonicalDigest(),C,Optional.empty());
        assertThat(without).matches("[0-9a-f]{64}").isNotEqualTo(with).isNotEqualTo(otherProfile);
    }
    @Test void acceptsOnlyRecomputedDvrCanonicalAndDigestDerivedId(){
        var corpus=new DocumentCorpusKeyDto("hr","policy");
        String corpusDigest=JdbcDocumentIndexValidationReportRepository.corpusKeyDigest(corpus);
        var binding=JdbcDocumentIndexValidationReportRepository.targetBinding("v1",A,B,C);
        String subjectDigest=JdbcDocumentIndexValidationReportRepository.indexSubjectDigest(corpusDigest,B,binding.canonicalDigest(),D,Optional.empty());
        var subject=new JdbcDocumentIndexValidationReportRepository.IndexSubjectProjection(corpus,"index-safe","v1",A,B,C,D,Optional.empty());
        var gates=java.util.Arrays.stream(JdbcDocumentIndexValidationReportRepository.GateCode.values())
                .filter(code -> code != JdbcDocumentIndexValidationReportRepository.GateCode.EMBEDDING_INDEX_COMPATIBILITY)
                .map(code -> new JdbcDocumentIndexValidationReportRepository.GateResult(code,
                        JdbcDocumentIndexValidationReportRepository.GateStatus.PASSED,A,null)).toList();
        var completed=java.time.Instant.parse("2026-07-14T08:00:00Z");var expires=completed.plusSeconds(60);
        String canonical=JdbcDocumentIndexValidationReportRepository.reportCanonical(subjectDigest,A,B,C,
                JdbcDocumentIndexValidationReportRepository.ReportStatus.PASSED,gates,java.util.List.of(),completed,expires,"integrity-1");
        new JdbcDocumentIndexValidationReportRepository.IndexValidationReport(canonical,subjectDigest,subject,A,B,C,
                JdbcDocumentIndexValidationReportRepository.ReportStatus.PASSED,gates,java.util.List.of(),completed,expires,"integrity-1",canonical,"run-1");
        assertThatThrownBy(()->new JdbcDocumentIndexValidationReportRepository.IndexValidationReport("report-1",subjectDigest,subject,A,B,C,
                JdbcDocumentIndexValidationReportRepository.ReportStatus.PASSED,gates,java.util.List.of(),completed,expires,"integrity-1",canonical,"run-1"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test void rejectsPassedIndexReportWithIncompleteGateSet(){
        var corpus=new DocumentCorpusKeyDto("hr","policy");
        String corpusDigest=JdbcDocumentIndexValidationReportRepository.corpusKeyDigest(corpus);
        var binding=JdbcDocumentIndexValidationReportRepository.targetBinding("v1",A,B,C);
        String subjectDigest=JdbcDocumentIndexValidationReportRepository.indexSubjectDigest(
                corpusDigest,B,binding.canonicalDigest(),D,Optional.empty());
        var subject=new JdbcDocumentIndexValidationReportRepository.IndexSubjectProjection(
                corpus,"index-safe","v1",A,B,C,D,Optional.empty());
        var gates=java.util.List.of(new JdbcDocumentIndexValidationReportRepository.GateResult(
                JdbcDocumentIndexValidationReportRepository.GateCode.INDEX_TECHNICAL,
                JdbcDocumentIndexValidationReportRepository.GateStatus.PASSED,A,null));
        var completed=java.time.Instant.parse("2026-07-14T08:00:00Z");var expires=completed.plusSeconds(60);
        String canonical=JdbcDocumentIndexValidationReportRepository.reportCanonical(subjectDigest,A,B,C,
                JdbcDocumentIndexValidationReportRepository.ReportStatus.PASSED,gates,java.util.List.of(),completed,expires,"integrity-1");
        assertThatThrownBy(()->new JdbcDocumentIndexValidationReportRepository.IndexValidationReport(
                canonical,subjectDigest,subject,A,B,C,
                JdbcDocumentIndexValidationReportRepository.ReportStatus.PASSED,gates,java.util.List.of(),
                completed,expires,"integrity-1",canonical,"run-1"))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("missing required gates");
    }
}
