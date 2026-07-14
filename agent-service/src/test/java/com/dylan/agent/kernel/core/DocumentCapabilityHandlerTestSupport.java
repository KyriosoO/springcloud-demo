package com.dylan.agent.kernel.core;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.api.capability.*;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.*;
import com.dylan.agent.kernel.port.model.AdapterExecutionBinding;
import com.dylan.agent.kernel.port.model.ExecutionValidationProjection;
import com.dylan.agent.kernel.resource.*;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.testsupport.ExternalProcessingTestSupport;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.shared.ref.AgentProfileRef;
import java.time.*;
import java.util.*;

public final class DocumentCapabilityHandlerTestSupport {
    private static final Instant NOW = Instant.now();
    private DocumentCapabilityHandlerTestSupport() {}

    public static ExecutionContext context(DocumentRetrievableAdapter adapter) {
        ExecutionScope scope = executionScope();
        return new ExecutionContext("inv-1", "corr-1", "document.answer",
                new ExecutionSubjectRef("user", "u-1"), new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"), scope,
                com.dylan.agent.testsupport.DomainMetadataTestSupport.binding(
                        AdapterRole.DOCUMENT_RETRIEVABLE, "policy_document",
                        DocumentRetrievableAdapter.class, adapter, "adapter-v1",
                        scope.domainMetadataEvidence(), NOW),
                NOW.plusSeconds(30), new CancellationSource().token());
    }

    public static ExecutionScope executionScope() {
        EffectiveCapabilityResourceLimits limits = new EffectiveCapabilityResourceLimits(
                AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT,
                com.dylan.agent.adapter.api.document.DocumentResourceLimit.class,
                DocumentResourceLimits.defaults(), "a".repeat(64),
                new ResourceLimitBindingIdentity("inv-1", "corr-1", "document-reg", "b".repeat(64), NOW));
        Set<com.dylan.agent.adapter.api.operation.CapabilityOperationType> providerPurposes = Set.of(
                com.dylan.agent.adapter.api.operation.CapabilityOperationType.of("DOCUMENT_REWRITE"),
                com.dylan.agent.adapter.api.operation.CapabilityOperationType.of("DOCUMENT_EMBEDDING"),
                com.dylan.agent.adapter.api.operation.CapabilityOperationType.of("DOCUMENT_RERANK"),
                com.dylan.agent.adapter.api.operation.CapabilityOperationType.of("DOCUMENT_GENERATION"));
        var externalProcessing = ExternalProcessingTestSupport.allowed(
                "policy_document", Set.of("title", "section", "page", "snippet"), providerPurposes);
        return new ExecutionScope("inv-1", "corr-1", new ExecutionSubjectRef("user", "u-1"),
                new ContextOwnerRef("conversation", "conv-1"), new ConversationScope("conv-1"),
                AgentProfileRef.of("agent-default", "profile-v1"),
                com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence("catalog-v1", "adapter-v1", "availability", NOW),
                NOW, NOW.plusSeconds(30), "perm-evidence", "perm-v1", "policy-v1",
                Set.of("document.answer", "document.search", "document.summarize"), Set.of("policy_document"),
                Map.of("policy_document", Set.of("title", "sourceType", "section", "page", "sourceUri", "snippet")),
                Map.of(), Map.of(), Map.of(), externalProcessing,
                Set.of(RuntimeContextType.DOCUMENT), Set.of(RuntimeContextType.DOCUMENT),
                AgentCapabilityRiskLevel.READ_ONLY, AgentCapabilityExecutionMode.IMMEDIATE, Duration.ofDays(7), limits);
    }

    public static ExecutionValidationContext validationContext(String capabilityId, String domain) {
        return new ExecutionValidationContext(capabilityId,
                com.dylan.agent.api.contract.runtime.common.AgentPlanKind.DOCUMENT,
                com.dylan.agent.api.contract.runtime.common.AgentDomainMode.REQUIRED,
                executionScope(), new ExecutionValidationProjection(AdapterRole.DOCUMENT_RETRIEVABLE,
                domain, Map.of(), List.of(), Set.of(), "catalog-v1"), null, List.of(),
                NOW.plusSeconds(30), new CancellationSource().token());
    }
}
