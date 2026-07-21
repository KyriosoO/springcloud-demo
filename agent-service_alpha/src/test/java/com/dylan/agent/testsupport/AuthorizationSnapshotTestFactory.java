package com.dylan.agent.testsupport;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.kernel.resource.EffectiveCapabilityResourceLimits;
import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Set;

/** 当前不可变 AuthorizationSnapshot 的测试工厂。 */
public final class AuthorizationSnapshotTestFactory {
    private AuthorizationSnapshotTestFactory() {
    }

    public static AuthorizationSnapshot create(
            String snapshotId,
            String subjectRef,
            String profileVersion,
            String policyVersion,
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Map<String, Set<String>> allowedFields,
            Map<String, MaskType> fieldMasks,
            Instant capturedAt,
            DomainMetadataEvidence evidence,
            EffectiveCapabilityResourceLimits resourceLimits) {
        String[] subject = subjectRef.split(":", 2);
        Set<RuntimeContextType> contexts = allowedCapabilityIds.stream().anyMatch(id -> id.startsWith("document."))
                ? Set.of(RuntimeContextType.DOCUMENT) : Set.of(RuntimeContextType.QUERY);
        DomainMetadataEvidence resolvedEvidence = evidence == null
                ? com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence("catalog-v1", "adapter-v1", "availability-v1", capturedAt)
                : evidence;
        return new AuthorizationSnapshot(
                snapshotId,
                resourceLimits.bindingIdentity().invocationId(),
                resourceLimits.bindingIdentity().requestCorrelationId(),
                new ExecutionSubjectRef(subject[0], subject[1]),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                AgentProfileRef.of("agent-default", profileVersion),
                policyVersion,
                "perm-evidence",
                "perm-v1",
                DelegationConstraintRef.CHAT_ALL,
                allowedCapabilityIds,
                allowedDomains,
                allowedFields,
                Map.of(),
                Map.of(),
                fieldMasks,
                ExternalProcessingTestSupport.denied(),
                contexts,
                contexts,
                AgentCapabilityRiskLevel.READ_ONLY,
                AgentCapabilityExecutionMode.IMMEDIATE,
                Duration.ofDays(7),
                capturedAt,
                capturedAt.plusSeconds(60),
                resolvedEvidence,
                resourceLimits);
    }
}
