package com.dylan.agent.capability.aggregate;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.context.AggregateCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.plan.AggregateAgentPlan;
import com.dylan.agent.api.response.AggregateAgentResultPayload;
import com.dylan.agent.kernel.definition.CapabilityDefinition;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;
import com.dylan.agent.kernel.definition.ContextAccessDeclaration;
import com.dylan.agent.kernel.definition.ContextReadDeclaration;
import com.dylan.agent.kernel.definition.ContextWriteDeclaration;
import com.dylan.agent.kernel.registration.CapabilityRegistration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Duration;
import java.util.List;
import java.util.Set;

@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(prefix = "agent.kernel", name = "enabled", havingValue = "true")
public class AggregateCapabilityConfiguration {

    @Bean
    public CapabilityRegistration<AggregateAgentPlan, ValidatedAggregatePlan, AggregateAgentResultPayload>
    aggregateComputeRegistration(AggregatePlanValidator validator, AggregateCapabilityHandler handler) {
        return new CapabilityRegistration<>(
                CapabilityDefinition.builder()
                        .capabilityId(AggregatePlanValidator.KERNEL_CAPABILITY_ID)
                        .planKind(AgentPlanKind.AGGREGATE)
                        .routingDescriptor(new CapabilityRoutingDescriptor(
                                "Compute aggregate metrics and groups over records.",
                                List.of("aggregate", "metric", "group"),
                                List.of("detail pagination", "write")))
                        .domainMode(AgentDomainMode.REQUIRED)
                        .adapterRole(AdapterRole.AGGREGATABLE)
                        .riskLevel(AgentCapabilityRiskLevel.READ_ONLY)
                        .executionMode(AgentCapabilityExecutionMode.IMMEDIATE)
                        .inputContract(AgentExecutionContracts.AGGREGATE_PLAN)
                        .outputContract(AgentExecutionContracts.AGGREGATE_RESULT)
                        .contextAccess(new ContextAccessDeclaration(
                                List.of(new ContextReadDeclaration(
                                        RuntimeContextType.AGGREGATE,
                                        AgentExecutionContracts.AGGREGATE_CONTEXT,
                                        AggregateCapabilityContextPayload.class,
                                        false,
                                        Set.of("filters", "metrics", "groupByFields", "orderBy", "maxRows"))),
                                List.of(new ContextWriteDeclaration(
                                        RuntimeContextType.AGGREGATE,
                                        AgentExecutionContracts.AGGREGATE_CONTEXT,
                                        AggregateCapabilityContextPayload.class,
                                        Duration.ofDays(7),
                                        Set.of("filters", "metrics", "groupByFields", "orderBy", "maxRows")))))
                        .build(),
                AggregateAgentPlan.class,
                validator,
                ValidatedAggregatePlan.class,
                handler,
                AggregateAgentResultPayload.class);
    }
}
