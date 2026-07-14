package com.dylan.agent.capability.querypreview;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.response.QueryPreviewResultPayload;
import com.dylan.agent.kernel.definition.CapabilityDefinition;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;
import com.dylan.agent.kernel.definition.ContextAccessDeclaration;
import com.dylan.agent.kernel.definition.ContextReadDeclaration;
import com.dylan.agent.kernel.registration.CapabilityRegistration;
import com.dylan.agent.kernel.resource.StandardResourceLimits;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.List;
import java.util.Set;

@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(prefix = "agent.kernel", name = "enabled", havingValue = "true")
public class QueryPreviewCapabilityConfiguration {

    @Bean
    public CapabilityRegistration<QueryAgentPlan, ValidatedQueryPreviewPlan, QueryPreviewResultPayload>
    queryPreviewRegistration(QueryPreviewPlanValidator validator, QueryPreviewCapabilityHandler handler) {
        return new CapabilityRegistration<>(
                CapabilityDefinition.builder()
                        .capabilityId(QueryPreviewPlanValidator.KERNEL_CAPABILITY_ID)
                        .planKind(AgentPlanKind.QUERY)
                        .routingDescriptor(new CapabilityRoutingDescriptor(
                                "Preview query records with authorized fields and a bounded sample.",
                                List.of("preview", "sample", "query"),
                                List.of("aggregate", "write")))
                        .domainMode(AgentDomainMode.REQUIRED)
                        .adapterRole(AdapterRole.QUERYABLE)
                        .riskLevel(AgentCapabilityRiskLevel.READ_ONLY)
                        .executionMode(AgentCapabilityExecutionMode.IMMEDIATE)
                        .inputContract(AgentExecutionContracts.QUERY_PLAN)
                        .outputContract(AgentExecutionContracts.QUERY_PREVIEW_RESULT)
                        .resourceLimitDeclaration(StandardResourceLimits.declaration(100, 100, 2_000_000L))
                        .resourceLimitConsumers(StandardResourceLimits.consumers(
                                QueryPreviewPlanValidator.KERNEL_CAPABILITY_ID))
                        .contextAccess(new ContextAccessDeclaration(
                                List.of(new ContextReadDeclaration(
                                        RuntimeContextType.QUERY,
                                        AgentExecutionContracts.QUERY_CONTEXT,
                                        QueryCapabilityContextPayload.class,
                                        false,
                                        Set.of("filters", "selectFields", "page", "size"))),
                                List.of()))
                        .build(),
                QueryAgentPlan.class,
                validator,
                ValidatedQueryPreviewPlan.class,
                handler,
                QueryPreviewResultPayload.class);
    }
}
