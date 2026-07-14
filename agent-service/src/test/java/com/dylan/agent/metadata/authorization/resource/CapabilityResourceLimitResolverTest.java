package com.dylan.agent.metadata.authorization.resource;

import com.dylan.agent.adapter.api.operation.StandardCapabilityResourceLimit;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.kernel.resource.CapabilityResourceLimitDeclaration;
import com.dylan.agent.kernel.resource.CapabilityResourceLimitRegistry;
import com.dylan.agent.kernel.resource.StandardCapabilityResourceLimitContract;
import com.dylan.agent.kernel.resource.StandardResourceLimits;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class CapabilityResourceLimitResolverTest {

    private final CapabilityResourceLimitResolver resolver = new CapabilityResourceLimitResolver(
            new CapabilityResourceLimitRegistry(List.of(new StandardCapabilityResourceLimitContract())));

    @Test
    void executionRecheckRetainsFrozenRequestNarrowingAndAppliesStricterCurrentPolicy() {
        CapabilityResourceLimitDeclaration<StandardCapabilityResourceLimit> declaration =
                StandardResourceLimits.declaration(100, 100, 10_000);
        var frozen = resolver.resolve(
                "inv-1", "corr-1", "registration-v1", "a".repeat(64), declaration,
                List.of(
                        contribution(ResourceLimitSource.PROFILE, 100, 100, 10_000, "profile-v1"),
                        contribution(ResourceLimitSource.POLICY, 100, 100, 10_000, "policy-v1"),
                        contribution(ResourceLimitSource.PERMISSION, 100, 100, 10_000, "permission-v1"),
                        contribution(ResourceLimitSource.REQUEST, 80, 80, 8_000, "request-v1")),
                Instant.parse("2026-07-14T00:00:00Z"));

        var rechecked = resolver.recheck(
                frozen,
                CapabilityResourceLimitContributions.of(List.of(
                        contribution(ResourceLimitSource.PROFILE, 100, 100, 10_000, "profile-v1"))),
                CapabilityResourceLimitContributions.of(List.of(
                        contribution(ResourceLimitSource.POLICY, 60, 70, 7_000, "policy-v1"))),
                "permission-current");

        var limits = rechecked.require(
                AgentExecutionContracts.STANDARD_RESOURCE_LIMIT,
                StandardCapabilityResourceLimit.class);
        assertThat(limits).isEqualTo(new StandardCapabilityResourceLimit(60, 70, 7_000));
        assertThat(rechecked.bindingIdentity()).isEqualTo(frozen.bindingIdentity());
    }

    private static CapabilityResourceLimitContribution<StandardCapabilityResourceLimit> contribution(
            ResourceLimitSource source,
            int maxPageSize,
            int maxRows,
            long maxBytes,
            String evidenceRef) {
        return new CapabilityResourceLimitContribution<>(
                source,
                AgentExecutionContracts.STANDARD_RESOURCE_LIMIT,
                StandardCapabilityResourceLimit.class,
                new StandardCapabilityResourceLimit(maxPageSize, maxRows, maxBytes),
                evidenceRef);
    }
}
