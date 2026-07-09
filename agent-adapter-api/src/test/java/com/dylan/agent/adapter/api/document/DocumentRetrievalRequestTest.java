package com.dylan.agent.adapter.api.document;

import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentRetrievalRequestTest {

    @Test
    void keepsExistingConstructorsAndCopiesAclScope() {
        DocumentRetrievalRequest request = new DocumentRetrievalRequest(
                DocumentPlanOperation.SEARCH,
                "policy_document",
                "休假政策",
                List.of(),
                List.of(),
                5,
                1,
                5,
                null,
                false);
        DocumentAclScope scope = new DocumentAclScope(
                "tenant-1",
                "user-1",
                List.of("dept-1"),
                List.of("role-1"),
                List.of("region:CN"),
                "acl-v1",
                Instant.now().plusSeconds(60));

        DocumentRetrievalRequest copied = request.withAclScope(scope);

        assertThat(request.getAclScope()).isNull();
        assertThat(copied.getAclScope()).isSameAs(scope);
        assertThat(copied.getDomain()).isEqualTo(request.getDomain());
        assertThat(copied.getQueryVector()).isEmpty();
    }

    @Test
    void copiesProfileAndRewriteCandidatesWhenAclScopeIsAdded() {
        DocumentHybridOptions hybridOptions = new DocumentHybridOptions(
                11,
                12,
                60,
                100,
                13,
                14,
                2,
                List.of("BM25", "EXACT"),
                Map.of("BM25", 2.0d),
                "embedding_v2",
                true,
                20);
        DocumentRetrievalRequest request = new DocumentRetrievalRequest(
                DocumentPlanOperation.ANSWER,
                "policy_document",
                "tax_policy",
                "tax-v2",
                "v2",
                "agent-doc-tax-policy-read",
                "增值税优惠政策",
                List.of("财税〔2026〕1号"),
                List.of("增值税小规模纳税人优惠"),
                List.of(),
                List.of(),
                5,
                1,
                5,
                null,
                true,
                DocumentRetrievalMode.HYBRID,
                List.of(0.1, 0.2),
                hybridOptions,
                null,
                null);
        DocumentAclScope scope = new DocumentAclScope(
                "tenant-1",
                "user-1",
                List.of("dept-1"),
                List.of("role-1"),
                List.of("region:CN"),
                "acl-v1",
                Instant.now().plusSeconds(60));

        DocumentRetrievalRequest copied = request.withAclScope(scope);

        assertThat(copied.getMaterialType()).isEqualTo("tax_policy");
        assertThat(copied.getRetrievalProfile()).isEqualTo("tax-v2");
        assertThat(copied.getProfileVersion()).isEqualTo("v2");
        assertThat(copied.getIndexAlias()).isEqualTo("agent-doc-tax-policy-read");
        assertThat(copied.getRuleKeywords()).containsExactly("财税〔2026〕1号");
        assertThat(copied.getRewriteCandidates()).containsExactly("增值税小规模纳税人优惠");
        assertThat(copied.getHybridOptions()).isSameAs(hybridOptions);
        assertThat(copied.getAclScope()).isSameAs(scope);
    }
}
