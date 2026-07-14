package com.dylan.agent.capability.document.governance.validation;

import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.List;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentValidationModelsTest {
    private static final String A="a".repeat(64),B="b".repeat(64),C="c".repeat(64),D="d".repeat(64);
    @Test void acceptsOnlyRecomputedDvrCanonicalAndDigestDerivedId(){
        var subject=new DocumentValidationModels.P1ReleaseCandidateSubjectRef(A,B,C,D);
        String subjectDigest=subject.canonicalDigest();
        String policyDigest=DocumentValidationModels.policyDigest("policy-v1","suite-v1");
        var policy=new DocumentValidationModels.PolicyRef("policy-v1","suite-v1",policyDigest);
        var gates=List.of(new DocumentValidationModels.GateResult(DocumentValidationModels.GateCode.CONTRACT_MIGRATION_CLEANUP,
                DocumentValidationModels.GateStatus.PASSED,A,null));
        Instant completed=Instant.parse("2026-07-14T08:00:00Z"),expires=completed.plusSeconds(60);
        String canonical=DocumentValidationModels.reportCanonical(subjectDigest,policyDigest,B,C,
                DocumentValidationModels.ReportStatus.PASSED,gates,List.of(),completed,expires,"integrity-1");
        new DocumentValidationModels.Report(canonical,subject,policy,B,C,DocumentValidationModels.ReportStatus.PASSED,
                gates,List.of(),completed,expires,"integrity-1",canonical,"run-1");
        assertThatThrownBy(()->new DocumentValidationModels.Report("report-1",subject,policy,B,C,
                DocumentValidationModels.ReportStatus.PASSED,gates,List.of(),completed,expires,"integrity-1",canonical,"run-1"))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
