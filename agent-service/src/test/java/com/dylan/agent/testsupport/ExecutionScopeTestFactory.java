package com.dylan.agent.testsupport;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.kernel.resource.EffectiveCapabilityResourceLimits;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Set;

/** 构造与当前 P1 冻结授权契约一致的测试执行范围。 */
public final class ExecutionScopeTestFactory {

    private ExecutionScopeTestFactory() {
    }

    public static ExecutionScope create(
            String subjectRef,
            DomainMetadataEvidence evidence,
            Instant now,
            String permissionEvidenceId,
            String permissionVersion,
            String policyVersion,
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Map<String, Set<String>> allowedFields,
            Map<String, MaskType> fieldMasks,
            EffectiveCapabilityResourceLimits resourceLimits) {
        Set<RuntimeContextType> contexts = inferContexts(allowedCapabilityIds);
        return create(subjectRef, evidence, now, permissionEvidenceId, permissionVersion, policyVersion,
                allowedCapabilityIds, allowedDomains, allowedFields, fieldMasks, contexts, contexts, resourceLimits);
    }

    public static ExecutionScope create(
            String subjectRef,
            DomainMetadataEvidence evidence,
            Instant now,
            String permissionEvidenceId,
            String permissionVersion,
            String policyVersion,
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Map<String, Set<String>> allowedFields,
            Map<String, MaskType> fieldMasks,
            Set<RuntimeContextType> readableContextTypes,
            Set<RuntimeContextType> writableContextTypes,
            EffectiveCapabilityResourceLimits resourceLimits) {
        String[] subject = subjectRef.split(":", 2);
        if (subject.length != 2) {
            throw new IllegalArgumentException("subjectRef 必须为 type:id");
        }
        return new ExecutionScope(
                "inv-1",
                "corr-1",
                new ExecutionSubjectRef(subject[0], subject[1]),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                AgentProfileRef.of("agent-default", "profile-v1"),
                evidence,
                now,
                now.plusSeconds(30),
                permissionEvidenceId,
                permissionVersion,
                policyVersion,
                allowedCapabilityIds,
                allowedDomains,
                allowedFields,
                Map.of(),
                Map.of(),
                fieldMasks,
                ExternalProcessingTestSupport.denied(),
                readableContextTypes,
                writableContextTypes,
                AgentCapabilityRiskLevel.READ_ONLY,
                AgentCapabilityExecutionMode.IMMEDIATE,
                Duration.ofDays(7),
                resourceLimits);
    }

    private static Set<RuntimeContextType> inferContexts(Set<String> capabilityIds) {
        if (capabilityIds.stream().anyMatch(id -> id.startsWith("document."))) {
            return Set.of(RuntimeContextType.DOCUMENT);
        }
        if (capabilityIds.stream().anyMatch(id -> id.startsWith("aggregate."))) {
            return Set.of(RuntimeContextType.QUERY, RuntimeContextType.AGGREGATE);
        }
        return Set.of(RuntimeContextType.QUERY);
    }
}
