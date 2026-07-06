package com.dylan.agent.kernel.core;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.invocation.model.CancellationSource;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.kernel.port.model.AdapterExecutionBinding;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Set;

public final class DocumentCapabilityHandlerTestSupport {

    private static final Instant NOW = Instant.parse("2026-07-01T00:00:00Z");

    private DocumentCapabilityHandlerTestSupport() {
    }

    public static ExecutionContext context(DocumentRetrievableAdapter adapter) {
        return new ExecutionContext(
                "inv-1",
                new ExecutionSubjectRef("user", "u-1"),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                executionScope(),
                new AdapterExecutionBinding(
                        AdapterRole.DOCUMENT_RETRIEVABLE,
                        "policy_document",
                        DocumentRetrievableAdapter.class,
                        adapter,
                        "adapter-reg-test",
                        NOW),
                NOW.plusSeconds(30),
                new CancellationSource().token());
    }

    static ExecutionScope executionScope() {
        return new ExecutionScope(
                "user:u-1",
                new DomainMetadataEvidence("catalog-v1", "adapter-v1", "availability", NOW),
                NOW,
                "perm-evidence",
                "perm-v1",
                "policy-v1",
                Set.of("document.answer", "document.search", "document.summarize"),
                Set.of("policy_document"),
                Map.of("policy_document", Set.of("sourceType")),
                Map.of(),
                Duration.ofSeconds(30),
                1,
                20,
                1024 * 1024);
    }
}
