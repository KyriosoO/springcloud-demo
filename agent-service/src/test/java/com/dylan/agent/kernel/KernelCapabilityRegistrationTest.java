package com.dylan.agent.kernel;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.capability.aggregate.AggregateCapabilityConfiguration;
import com.dylan.agent.capability.aggregate.AggregateCapabilityHandler;
import com.dylan.agent.capability.aggregate.AggregatePlanValidator;
import com.dylan.agent.capability.query.QueryCapabilityConfiguration;
import com.dylan.agent.capability.query.QueryCapabilityHandler;
import com.dylan.agent.capability.query.QueryPlanValidator;
import com.dylan.agent.capability.querypreview.QueryPreviewCapabilityConfiguration;
import com.dylan.agent.capability.querypreview.QueryPreviewCapabilityHandler;
import com.dylan.agent.capability.querypreview.QueryPreviewPlanValidator;
import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.kernel.registration.CapabilityRegistration;
import com.dylan.agent.kernel.registration.CapabilityRegistrationValidator;
import com.dylan.agent.kernel.registration.CapabilityRegistry;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

class KernelCapabilityRegistrationTest {

    @Test
    void queryAndAggregateRegistrationsAreResolvableByCapabilityIdOnly() {
        QueryCapabilityConfiguration queryConfig = new QueryCapabilityConfiguration();
        QueryPreviewCapabilityConfiguration previewConfig = new QueryPreviewCapabilityConfiguration();
        AggregateCapabilityConfiguration aggregateConfig = new AggregateCapabilityConfiguration();

        CapabilityRegistration<?, ?, ?> query = queryConfig.querySearchRegistration(
                mock(QueryPlanValidator.class),
                mock(QueryCapabilityHandler.class));
        CapabilityRegistration<?, ?, ?> preview = previewConfig.queryPreviewRegistration(
                mock(QueryPreviewPlanValidator.class),
                mock(QueryPreviewCapabilityHandler.class));
        CapabilityRegistration<?, ?, ?> aggregate = aggregateConfig.aggregateComputeRegistration(
                mock(AggregatePlanValidator.class),
                mock(AggregateCapabilityHandler.class));
        List<CapabilityRegistration<?, ?, ?>> registrations = List.of(query, preview, aggregate);

        ContractRegistry contracts = ContractRegistry.from(registrations);
        CapabilityRegistry registry = new CapabilityRegistry(
                registrations,
                new CapabilityRegistrationValidator(),
                contracts,
                Set.of(AdapterRole.QUERYABLE, AdapterRole.AGGREGATABLE));

        assertThat(registry.resolve("query.search").planKind()).isEqualTo(AgentPlanKind.QUERY);
        assertThat(registry.resolve("query.preview").planKind()).isEqualTo(AgentPlanKind.QUERY);
        assertThat(registry.resolve("aggregate.compute").planKind()).isEqualTo(AgentPlanKind.AGGREGATE);
        assertThat(registry.coverageByPlanKind().get(AgentPlanKind.QUERY))
                .containsExactly("query.search", "query.preview");
        assertThat(registry.coverageByPlanKind().get(AgentPlanKind.AGGREGATE)).containsExactly("aggregate.compute");
        assertThat(contracts.require(AgentExecutionContracts.QUERY_RESULT).javaType().getSimpleName())
                .isEqualTo("QueryAgentResultPayload");
        assertThat(contracts.require(AgentExecutionContracts.QUERY_PREVIEW_RESULT).javaType().getSimpleName())
                .isEqualTo("QueryPreviewResultPayload");
        assertThat(contracts.require(AgentExecutionContracts.AGGREGATE_RESULT).javaType().getSimpleName())
                .isEqualTo("AggregateAgentResultPayload");
    }
}
