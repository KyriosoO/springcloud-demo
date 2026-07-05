package com.dylan.agent.capability.query;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.response.QueryAgentResultPayload;
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
public class QueryCapabilityConfiguration {

    @Bean
    public CapabilityRegistration<QueryAgentPlan, ValidatedQueryPlan, QueryAgentResultPayload>
    querySearchRegistration(QueryPlanValidator validator, QueryCapabilityHandler handler) {
        return new CapabilityRegistration<>(
                CapabilityDefinition.builder()
                        .capabilityId(QueryPlanValidator.KERNEL_CAPABILITY_ID)
                        .planKind(AgentPlanKind.QUERY)
                        .routingDescriptor(new CapabilityRoutingDescriptor(
                                "Query records with filters, selected fields, and pagination.",
                                List.of("query", "filter", "page"),
                                List.of("aggregate", "write")))
                        .domainMode(AgentDomainMode.REQUIRED)
                        .adapterRole(AdapterRole.QUERYABLE)
                        .riskLevel(AgentCapabilityRiskLevel.READ_ONLY)
                        .executionMode(AgentCapabilityExecutionMode.IMMEDIATE)
                        .inputContract(AgentExecutionContracts.QUERY_PLAN)
                        .outputContract(AgentExecutionContracts.QUERY_RESULT)
                        .contextAccess(new ContextAccessDeclaration(
                                List.of(new ContextReadDeclaration(
                                        RuntimeContextType.QUERY,
                                        AgentExecutionContracts.QUERY_CONTEXT,
                                        QueryCapabilityContextPayload.class,
                                        false,
                                        Set.of("filters", "selectFields", "page", "size",
                                                "total", "totalExact", "totalPages"))),
                                List.of(new ContextWriteDeclaration(
                                        RuntimeContextType.QUERY,
                                        AgentExecutionContracts.QUERY_CONTEXT,
                                        QueryCapabilityContextPayload.class,
                                        Duration.ofDays(7),
                                        Set.of("filters", "selectFields", "page", "size",
                                                "total", "totalExact", "totalPages")))))
                        .build(),
                QueryAgentPlan.class,
                validator,
                ValidatedQueryPlan.class,
                handler,
                QueryAgentResultPayload.class);
    }
}
