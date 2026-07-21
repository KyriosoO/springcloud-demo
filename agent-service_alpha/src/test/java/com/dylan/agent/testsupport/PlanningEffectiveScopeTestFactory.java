package com.dylan.agent.testsupport;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.authorization.resource.CapabilityResourceLimitContributions;
import com.dylan.agent.metadata.authorization.resource.CapabilityResourceLimitContribution;
import com.dylan.agent.metadata.authorization.resource.ResourceLimitSource;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.profile.model.PlanningBudgetLimits;

import java.time.Duration;
import java.util.Map;
import java.util.Set;

/** 将旧预算型测试输入显式收敛到规划预算与 typed resource contribution。 */
public final class PlanningEffectiveScopeTestFactory {
    private PlanningEffectiveScopeTestFactory() {
    }

    public static PlanningEffectiveScope create(
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Map<CanonicalFieldRef, PlanningEffectiveScope.FieldAccess> fieldAccess,
            Set<RuntimeContextType> readableContextTypes,
            Set<RuntimeContextType> writableContextTypes,
            AgentCapabilityRiskLevel maxRiskLevel,
            AgentCapabilityExecutionMode maxExecutionMode,
            Duration maxTotalDuration,
            int maxRepairAttempts,
            int maxPageSize,
            int maxResultRows,
            long maxResultBytes) {
        return new PlanningEffectiveScope(
                allowedCapabilityIds,
                allowedDomains,
                fieldAccess,
                ExternalProcessingTestSupport.denied(),
                readableContextTypes,
                writableContextTypes,
                maxRiskLevel,
                maxExecutionMode,
                new PlanningBudgetLimits(maxTotalDuration, maxRepairAttempts),
                contributions(allowedCapabilityIds, maxPageSize, maxResultRows, maxResultBytes));
    }

    private static CapabilityResourceLimitContributions contributions(
            Set<String> capabilityIds,
            int maxPageSize,
            int maxResultRows,
            long maxResultBytes) {
        if (capabilityIds.stream().anyMatch(id -> id.startsWith("document."))) {
            var defaults = com.dylan.agent.kernel.resource.DocumentResourceLimits.defaults();
            var retrieval = defaults.retrieval();
            var output = defaults.output();
            var limit = new com.dylan.agent.adapter.api.document.DocumentResourceLimit(
                    defaults.input(),
                    new com.dylan.agent.adapter.api.document.DocumentResourceLimit.DocumentRetrievalLimit(
                            retrieval.maxChannelCount(), retrieval.maxCandidatesPerChannel(),
                            retrieval.maxFusedCandidates(), retrieval.maxChunksPerDocument(),
                            Math.min(maxPageSize, retrieval.maxReturnedDocuments())),
                    defaults.enhancement(),
                    new com.dylan.agent.adapter.api.document.DocumentResourceLimit.DocumentEvidenceOutputLimit(
                            output.maxEvidenceCount(), output.maxEvidenceChars(), output.maxSnippetChars(),
                            output.maxContextChars(), output.maxCitationCount(), output.maxGeneratedChars(),
                            output.maxSummaryChars(), output.maxSummaryBullets(), maxResultBytes));
            return pair(
                    com.dylan.agent.api.contract.common.AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT,
                    com.dylan.agent.adapter.api.document.DocumentResourceLimit.class,
                    limit);
        }
        var limit = new com.dylan.agent.adapter.api.operation.StandardCapabilityResourceLimit(
                maxPageSize, maxResultRows, maxResultBytes);
        return pair(
                com.dylan.agent.api.contract.common.AgentExecutionContracts.STANDARD_RESOURCE_LIMIT,
                com.dylan.agent.adapter.api.operation.StandardCapabilityResourceLimit.class,
                limit);
    }

    private static <T extends com.dylan.agent.adapter.api.operation.CapabilityResourceLimit>
    CapabilityResourceLimitContributions pair(
            com.dylan.agent.api.contract.common.ContractRef contractRef,
            Class<T> type,
            T limit) {
        return CapabilityResourceLimitContributions.of(java.util.List.of(
                new CapabilityResourceLimitContribution<>(
                        ResourceLimitSource.PROFILE, contractRef, type, limit, "test-profile"),
                new CapabilityResourceLimitContribution<>(
                        ResourceLimitSource.POLICY, contractRef, type, limit, "test-policy")));
    }
}
