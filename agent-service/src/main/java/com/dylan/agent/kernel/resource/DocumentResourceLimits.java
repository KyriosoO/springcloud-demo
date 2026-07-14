package com.dylan.agent.kernel.resource;

import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;

import java.util.List;
import java.util.Set;

/** 文档能力 Definition 与消费者的 DLRL-1 声明工厂。 */
public final class DocumentResourceLimits {
    private DocumentResourceLimits() {}

    public static CapabilityResourceLimitDeclaration<DocumentResourceLimit> declaration(DocumentResourceLimit intrinsic) {
        return new CapabilityResourceLimitDeclaration<>(AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, DocumentResourceLimit.class, intrinsic, new DocumentCapabilityResourceLimitContract().supportedDimensions());
    }

    public static List<CapabilityResourceConsumerDeclaration> consumers(String capabilityId) {
        Set<ResourceLimitDimension> all = new DocumentCapabilityResourceLimitContract().supportedDimensions();
        return List.of(
                new CapabilityResourceConsumerDeclaration(capabilityId + ".validator", AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, filter(all, "document.input.", "document.retrieval.")),
                new CapabilityResourceConsumerDeclaration(capabilityId + ".handler", AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, all),
                new CapabilityResourceConsumerDeclaration(capabilityId + ".provider", AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, filter(all, "document.enhancement.", "document.output.")),
                new CapabilityResourceConsumerDeclaration(capabilityId + ".result-projector", AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, filter(all, "document.output.")));
    }

    public static DocumentResourceLimit defaults() {
        return new DocumentResourceLimit(
                new DocumentResourceLimit.DocumentInputLimit(500, 20),
                new DocumentResourceLimit.DocumentRetrievalLimit(3, 60, 180, 2, 30),
                new DocumentResourceLimit.DocumentEnhancementLimit(3, 32, 4096, 30),
                new DocumentResourceLimit.DocumentEvidenceOutputLimit(12, 1600, 500, 12000, 12, 2000, 2000, 12, 2_000_000L));
    }

    /** 按 capability operation 冻结 Definition intrinsic 上界；0 表示该操作禁止对应可选能力。 */
    public static DocumentResourceLimit intrinsicFor(String capabilityId) {
        DocumentResourceLimit value = defaults();
        var output = value.output();
        java.util.Map<String, DocumentResourceLimit> byCapability = java.util.Map.of(
            "document.search", withOutput(value,
                    new DocumentResourceLimit.DocumentEvidenceOutputLimit(
                            output.maxEvidenceCount(), output.maxEvidenceChars(), output.maxSnippetChars(),
                            0, output.maxCitationCount(), 0, 0, 0, output.maxResultBytes())),
            "document.answer", withOutput(value,
                    new DocumentResourceLimit.DocumentEvidenceOutputLimit(
                            output.maxEvidenceCount(), output.maxEvidenceChars(), output.maxSnippetChars(),
                            output.maxContextChars(), output.maxCitationCount(), output.maxGeneratedChars(),
                            0, 0, output.maxResultBytes())),
            "document.summarize", value);
        return java.util.Optional.ofNullable(byCapability.get(capabilityId))
                .orElseThrow(() -> new IllegalArgumentException("unknown document capability: " + capabilityId));
    }

    public static DocumentResourceLimit require(com.dylan.agent.metadata.authorization.model.ExecutionScope scope) {
        return scope.resourceLimits().require(AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, DocumentResourceLimit.class);
    }

    private static Set<ResourceLimitDimension> filter(Set<ResourceLimitDimension> all, String... prefixes) {
        return all.stream().filter(d -> java.util.Arrays.stream(prefixes).anyMatch(d.value()::startsWith)).collect(java.util.stream.Collectors.toUnmodifiableSet());
    }

    private static DocumentResourceLimit withOutput(
            DocumentResourceLimit source,
            DocumentResourceLimit.DocumentEvidenceOutputLimit output) {
        return new DocumentResourceLimit(source.input(), source.retrieval(), source.enhancement(), output);
    }
}
