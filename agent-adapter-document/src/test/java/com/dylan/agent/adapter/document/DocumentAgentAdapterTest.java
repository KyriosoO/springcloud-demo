package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.*;
import com.dylan.agent.adapter.api.operation.*;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentTargetBindingDto;
import com.dylan.esquery.api.model.DocumentSearchChannel;
import com.dylan.esquery.api.model.document.*;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.time.Clock;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Optional;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class DocumentAgentAdapterTest {
    @Test
    void rejectsCancelledOperationBeforeOutboundCall() {
        DocumentSearchClient client = mock(DocumentSearchClient.class);
        var adapter = adapter(client);

        var cancelled = new CapabilityOperationContext("inv-1", "corr-1", "document.search", "op-1",
                CapabilityOperationType.of("DOCUMENT_RETRIEVAL"), Instant.parse("2026-07-14T12:01:00Z"), () -> true,
                context().resourceLimits());
        assertThat(adapter.retrieve(command(), cancelled)).isInstanceOf(CapabilityOperationFailure.class);
        verifyNoInteractions(client);
    }

    @Test
    void usesOnlySpecializedDocumentHybridEndpoint() {
        DocumentSearchClient client = mock(DocumentSearchClient.class);
        HybridSearchResponse response = boundEmptyResponse();
        when(client.documentHybridSearch(any())).thenReturn(response);

        var outcome = adapter(client).retrieve(command(), context());
        var result = ((CapabilityOperationSuccess<AdapterDocumentRetrievalResult>) outcome).candidate();

        assertThat(result.hits()).isEmpty();
        verify(client).documentHybridSearch(any());
        verifyNoMoreInteractions(client);
    }

    @Test
    void rejectsForgedCandidateIdentityAsInvalidResponse() {
        DocumentSearchClient client = mock(DocumentSearchClient.class);
        when(client.documentHybridSearch(any())).thenReturn(forgedCandidateResponse());

        var outcome = adapter(client).retrieve(command(), context());

        assertThat(outcome).isInstanceOfSatisfying(CapabilityOperationFailure.class,
                failure -> {
                    assertThat(failure.code()).isEqualTo(CapabilityOperationFailureCode.INVALID_RESPONSE);
                    assertThat(failure.metadata().providerAttempts()).isEqualTo(1);
                });
    }

    private DocumentAgentAdapter adapter(DocumentSearchClient client) {
        return new DocumentAgentAdapter(client, new DocumentRetrievalMapper(), new DocumentEvidenceMapper(),
                new DocumentRetrievalResponseBindingValidator(), Clock.fixed(Instant.parse("2026-07-14T12:00:00Z"), ZoneOffset.UTC));
    }

    private DocumentRetrievalCommand command() {
        var execution = new DocumentRetrievalExecutionBinding("tax-v2", "v2", "c".repeat(64), reference(),
                "d".repeat(64), "b".repeat(64));
        var channels = new DocumentRetrievalChannels(List.of(DocumentRetrievalChannel.BM25, DocumentRetrievalChannel.EXACT_PHRASE,
                DocumentRetrievalChannel.DENSE_VECTOR), List.of(DocumentRetrievalChannel.BM25, DocumentRetrievalChannel.EXACT_PHRASE,
                DocumentRetrievalChannel.DENSE_VECTOR), Map.of(DocumentRetrievalChannel.BM25, 1, DocumentRetrievalChannel.EXACT_PHRASE, 1,
                DocumentRetrievalChannel.DENSE_VECTOR, 1), 10, 40);
        return new DocumentRetrievalCommand(new DocumentCorpusKey("policy", "document"), execution, List.of(), binding(),
                new DocumentPreparedQuery("休假政策", List.of(), List.of(), Optional.empty()), channels,
                new DocumentFusionSpec(60, 50), new DocumentDedupSpec(5, 3), new DocumentContextSpec(0, 0, 0));
    }

    private DocumentProtectedFilterBinding binding() {
        return new DocumentProtectedFilterBinding(new DocumentCorpusKey("policy", "document"),
                new DocumentAllOf(List.of(new DocumentExactTerm(DocumentAclIndexField.TENANT_ID, "tenant-1"))),
                "a".repeat(64), "b".repeat(64), "c".repeat(64), reference());
    }

    private CapabilityOperationContext context() {
        return new CapabilityOperationContext("inv-1", "corr-1", "document.search", "op-1",
                CapabilityOperationType.of("DOCUMENT_RETRIEVAL"), Instant.parse("2026-07-14T12:01:00Z"), () -> false,
                new CapabilityResourceLimitView() {
                    @Override public <T extends CapabilityResourceLimit> T require(com.dylan.agent.api.contract.common.ContractRef ref, Class<T> type) {
                        return type.cast(limit());
                    }
                    @Override public ResourceLimitReference reference() { return DocumentAgentAdapterTest.this.reference(); }
                });
    }

    private DocumentResourceLimit limit() {
        return new DocumentResourceLimit(new DocumentResourceLimit.DocumentInputLimit(500, 10),
                new DocumentResourceLimit.DocumentRetrievalLimit(4, 50, 100, 3, 20),
                new DocumentResourceLimit.DocumentEnhancementLimit(3, 1, 1024, 20),
                new DocumentResourceLimit.DocumentEvidenceOutputLimit(20, 10000, 1000, 4000, 20, 4000, 2000, 10, 100000L));
    }
    private ResourceLimitReference reference() {
        return new ResourceLimitReference(AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, "d".repeat(64), "inv-1", "document-reg");
    }

    private HybridSearchResponse boundEmptyResponse() {
        var limit = new ResourceLimitBindingDto("agent", "DocumentResourceLimit", "v1", "d".repeat(64), "inv-1", "document-reg");
        var responseBinding = new DocumentSearchResponseBinding("corr-1", "op-1",
                new DocumentCorpusKeyDto("policy", "document"),
                new DocumentTargetBindingDto("3.0.0", "e".repeat(64), "f".repeat(64), "1".repeat(64)),
                "c".repeat(64), limit, "d".repeat(64), "a".repeat(64), "b".repeat(64));
        return new HybridSearchResponse(responseBinding, List.of(), List.of(
                new DocumentChannelResultSummary(DocumentSearchChannel.BM25, DocumentChannelResultSummary.Outcome.SUCCEEDED, 0, null),
                new DocumentChannelResultSummary(DocumentSearchChannel.EXACT_PHRASE, DocumentChannelResultSummary.Outcome.SUCCEEDED, 0, null),
                new DocumentChannelResultSummary(DocumentSearchChannel.DENSE_VECTOR, DocumentChannelResultSummary.Outcome.SUCCEEDED, 0, null)),
                new HybridRetrievalDiagnostics(0, 0, 0, 0, false, false));
    }

    private HybridSearchResponse forgedCandidateResponse() {
        HybridSearchResponse empty = boundEmptyResponse();
        var rank = new DocumentChannelRank(DocumentSearchChannel.BM25, 1, java.math.BigDecimal.ONE);
        var score = java.math.BigDecimal.ONE.divide(java.math.BigDecimal.valueOf(61), 18,
                java.math.RoundingMode.HALF_EVEN);
        var hit = new HybridSearchHit("forged", "doc-1", "v1", "chunk-1", 0,
                "acl-1", "acl-v1", "title", null, null, null, null, "snippet", null,
                null, null, List.of(), List.of(), null, null, java.math.BigDecimal.ONE, score, List.of(rank));
        return new HybridSearchResponse(empty.binding(), List.of(hit), List.of(
                new DocumentChannelResultSummary(DocumentSearchChannel.BM25, DocumentChannelResultSummary.Outcome.SUCCEEDED, 1, null),
                new DocumentChannelResultSummary(DocumentSearchChannel.EXACT_PHRASE, DocumentChannelResultSummary.Outcome.SUCCEEDED, 0, null),
                new DocumentChannelResultSummary(DocumentSearchChannel.DENSE_VECTOR, DocumentChannelResultSummary.Outcome.SUCCEEDED, 0, null)),
                new HybridRetrievalDiagnostics(1, 1, 1, 1, false, false));
    }
}
