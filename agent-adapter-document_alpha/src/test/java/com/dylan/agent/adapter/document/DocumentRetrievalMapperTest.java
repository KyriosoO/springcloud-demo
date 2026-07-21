package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.*;
import com.dylan.agent.adapter.api.operation.*;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import com.dylan.esquery.api.model.DocumentProtectedFilterDto;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentRetrievalMapperTest {
    @Test
    void mapsCallerAndProtectedFiltersIntoSeparateTypedFields() {
        var mapped = new DocumentRetrievalMapper().toDocumentHybridRequest(request(), context());

        assertThat(mapped.corpusKey().domain()).isEqualTo("policy");
        assertThat(mapped.protectedFilter().kind()).isEqualTo(DocumentProtectedFilterDto.Kind.ALL_OF);
        assertThat(mapped.protectedFilterDigest()).isEqualTo("a".repeat(64));
        assertThat(mapped.executionBinding().aclEvidenceDigest()).isEqualTo("b".repeat(64));
        assertThat(mapped.executionBinding().resourceLimit().canonicalDigest()).isEqualTo("d".repeat(64));
        assertThat(mapped.channels().get(0).numCandidates()).isEqualTo(40);
    }

    private DocumentRetrievalCommand request() {
        var binding = new DocumentProtectedFilterBinding(new DocumentCorpusKey("policy", "document"),
                new DocumentAllOf(List.of(new DocumentExactTerm(DocumentAclIndexField.TENANT_ID, "tenant-1"))),
                "a".repeat(64), "b".repeat(64), "c".repeat(64), reference());
        var execution = new DocumentRetrievalExecutionBinding("tax-v2", "v2", "c".repeat(64), reference(), "d".repeat(64), "b".repeat(64));
        var channels = new DocumentRetrievalChannels(List.of(DocumentRetrievalChannel.DENSE_VECTOR), List.of(),
                Map.of(DocumentRetrievalChannel.DENSE_VECTOR, 1), 10, 40);
        return new DocumentRetrievalCommand(new DocumentCorpusKey("policy", "document"), execution, List.of(), binding,
                new DocumentPreparedQuery("休假政策", List.of(), List.of(), Optional.empty()), channels,
                new DocumentFusionSpec(60, 50), new DocumentDedupSpec(5, 3), new DocumentContextSpec(0, 0, 0));
    }

    private CapabilityOperationContext context() {
        return new CapabilityOperationContext("inv-1", "corr-1", "document.search", "op-1",
                CapabilityOperationType.of("DOCUMENT_RETRIEVAL"), Instant.now().plusSeconds(60), () -> false,
                new CapabilityResourceLimitView() {
                    @Override public <T extends CapabilityResourceLimit> T require(com.dylan.agent.api.contract.common.ContractRef ref, Class<T> type) { return type.cast(limit()); }
                    @Override public ResourceLimitReference reference() { return DocumentRetrievalMapperTest.this.reference(); }
                });
    }

    private DocumentResourceLimit limit() {
        return new DocumentResourceLimit(new DocumentResourceLimit.DocumentInputLimit(500, 10),
                new DocumentResourceLimit.DocumentRetrievalLimit(4, 50, 100, 3, 20),
                new DocumentResourceLimit.DocumentEnhancementLimit(3, 1, 1024, 20),
                new DocumentResourceLimit.DocumentEvidenceOutputLimit(20, 10000, 1000, 4000, 20, 4000, 2000, 10, 100000L));
    }
    private ResourceLimitReference reference() { return new ResourceLimitReference(AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, "d".repeat(64), "inv-1", "document-reg"); }
}
