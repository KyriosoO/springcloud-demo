package com.dylan.agent.adapter.api.document;

import com.dylan.agent.api.plan.DocumentPlanOperation;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

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
}
