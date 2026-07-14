package com.dylan.agent.kernel.resource;

import com.dylan.agent.adapter.api.operation.StandardCapabilityResourceLimit;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;

import java.util.List;
import java.util.Set;

/** 表格型 Capability Definition 的资源声明工厂。 */
public final class StandardResourceLimits {

    private StandardResourceLimits() {
    }

    public static CapabilityResourceLimitDeclaration<StandardCapabilityResourceLimit> declaration(
            int maxPageSize,
            int maxResultRows,
            long maxResultBytes) {
        return new CapabilityResourceLimitDeclaration<>(
                AgentExecutionContracts.STANDARD_RESOURCE_LIMIT,
                StandardCapabilityResourceLimit.class,
                new StandardCapabilityResourceLimit(maxPageSize, maxResultRows, maxResultBytes),
                StandardCapabilityResourceLimitDimensions.ALL);
    }

    /** Standard capability 的四类运行时消费者声明。 */
    public static List<CapabilityResourceConsumerDeclaration> consumers(String capabilityId) {
        return List.of(
                consumer(capabilityId + ".validator",
                        Set.of(StandardCapabilityResourceLimitDimensions.PAGE_SIZE)),
                consumer(capabilityId + ".handler",
                        Set.of(StandardCapabilityResourceLimitDimensions.PAGE_SIZE,
                                StandardCapabilityResourceLimitDimensions.RESULT_ROWS)),
                consumer(capabilityId + ".provider",
                        Set.of(StandardCapabilityResourceLimitDimensions.PAGE_SIZE,
                                StandardCapabilityResourceLimitDimensions.RESULT_ROWS)),
                consumer(capabilityId + ".result-projector",
                        Set.of(StandardCapabilityResourceLimitDimensions.RESULT_ROWS,
                                StandardCapabilityResourceLimitDimensions.RESULT_BYTES)));
    }

    private static CapabilityResourceConsumerDeclaration consumer(
            String consumerId,
            Set<ResourceLimitDimension> dimensions) {
        return new CapabilityResourceConsumerDeclaration(
                consumerId,
                AgentExecutionContracts.STANDARD_RESOURCE_LIMIT,
                dimensions);
    }

    public static CapabilityResourceLimitDeclaration<StandardCapabilityResourceLimit> testDeclaration() {
        return declaration(100, 100, 1_000_000L);
    }

    public static CapabilityResourceLimitRegistry registry() {
        return new CapabilityResourceLimitRegistry(java.util.List.of(
                new StandardCapabilityResourceLimitContract()));
    }

    public static EffectiveCapabilityResourceLimits testEffective() {
        return testEffective(100, 100, 1_000_000L);
    }

    public static EffectiveCapabilityResourceLimits testEffective(
            int maxPageSize,
            int maxResultRows,
            long maxResultBytes) {
        var value = new StandardCapabilityResourceLimit(maxPageSize, maxResultRows, maxResultBytes);
        var contract = new StandardCapabilityResourceLimitContract();
        return new EffectiveCapabilityResourceLimits(
                AgentExecutionContracts.STANDARD_RESOURCE_LIMIT,
                StandardCapabilityResourceLimit.class,
                value,
                contract.canonicalDigest(value),
                new ResourceLimitBindingIdentity(
                        "inv-1", "corr-1", "registration-v1", "a".repeat(64),
                        java.time.Instant.parse("2026-07-01T00:00:00Z")));
    }

    public static StandardCapabilityResourceLimit require(
            com.dylan.agent.metadata.authorization.model.ExecutionScope scope) {
        return scope.resourceLimits().require(
                AgentExecutionContracts.STANDARD_RESOURCE_LIMIT,
                StandardCapabilityResourceLimit.class);
    }
}
