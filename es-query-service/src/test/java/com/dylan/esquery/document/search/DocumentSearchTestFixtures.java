package com.dylan.esquery.document.search;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentProtectedFilterDto;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;
import com.dylan.esquery.api.model.DocumentSearchChannel;
import com.dylan.esquery.api.model.DocumentTargetBindingDto;
import com.dylan.esquery.api.model.document.*;
import com.dylan.esquery.document.DocumentCorpusDefinition;
import com.dylan.esquery.document.ResolvedIndexTargetRef;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.Set;

final class DocumentSearchTestFixtures {
    static final String D1 = "1".repeat(64);
    static final String D2 = "2".repeat(64);
    static final String D3 = "3".repeat(64);
    static final String D4 = "4".repeat(64);
    static final DocumentCorpusKeyDto CORPUS_KEY = new DocumentCorpusKeyDto("policy", "document");

    private DocumentSearchTestFixtures() {
    }

    static HybridSearchRequest request(HybridContextRequest context) {
        return request(context,
                List.of(new DocumentHybridChannelRequest(DocumentSearchChannel.BM25, true, 1, 10, 10)),
                new HybridFusionRequest(60, 20), new HybridDedupRequest(5, 2));
    }

    static HybridSearchRequest request(
            HybridContextRequest context,
            List<DocumentHybridChannelRequest> channels,
            HybridFusionRequest fusion,
            HybridDedupRequest dedup) {
        ResourceLimitBindingDto limits = new ResourceLimitBindingDto(
                "agent", "DocumentResourceLimit", "v1", D1, "inv-1", "document-reg");
        DocumentSearchExecutionBinding execution = new DocumentSearchExecutionBinding(
                "policy-v3", "v3", D2, limits, D3, D4);
        DocumentSearchOperationMetadata operation = new DocumentSearchOperationMetadata(
                "corr-1", "op-1", "DOCUMENT_RETRIEVAL", Instant.now().plusSeconds(60).toEpochMilli(),
                "document-reg", limits);
        DocumentProtectedFilterDto filter = new DocumentProtectedFilterDto(
                DocumentProtectedFilterDto.Kind.EXACT, DocumentProtectedFilterDto.Field.TENANT_ID,
                "tenant-1", List.of(), List.of());
        return new HybridSearchRequest(CORPUS_KEY, execution, List.of(), filter, D1,
                new DocumentQueryPlan("年假", List.of(), List.of(), Optional.empty()),
                channels, fusion, dedup, context, operation);
    }

    static DocumentCorpusDefinition corpus() {
        return new DocumentCorpusDefinition(CORPUS_KEY, "agent-doc-policy-read",
                new DocumentSchemaRefDto("document", "v3", D1), "cn", "disabled", "chunk-v1",
                "source-1", Set.of());
    }

    static ResolvedIndexTargetRef target() {
        return new ResolvedIndexTargetRef(CORPUS_KEY, "agent-doc-policy-read", "agent-doc-policy-v3-000001",
                new DocumentTargetBindingDto("v3", D1, D2, D3), "report-1", null, null, null);
    }
}
