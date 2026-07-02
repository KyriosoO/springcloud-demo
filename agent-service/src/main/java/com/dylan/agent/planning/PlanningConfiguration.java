package com.dylan.agent.planning;

import com.dylan.agent.client.AgentRuntimeClient;
import com.dylan.agent.client.AgentRuntimeErrorMapper;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.kernel.registration.CapabilityRegistry;
import com.dylan.agent.metadata.authorization.port.AuthorizationPlanningPort;
import com.dylan.agent.metadata.catalog.CapabilityCatalog;
import com.dylan.agent.metadata.config.AgentMetadataStore;
import com.dylan.agent.metadata.context.port.ContextPlanningPort;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.metadata.profile.internal.ProfileBehaviorProjectionBoundary;

import java.time.Clock;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * D03 Planning 装配根。
 */
@Configuration(proxyBeanMethods = false)
public class PlanningConfiguration {

    @Bean
    RouteOutcomeValidator routeOutcomeValidator() {
        return new RouteOutcomeValidator();
    }

    @Bean
    PlanOutcomeValidator planOutcomeValidator() {
        return new PlanOutcomeValidator();
    }

    @Bean
    PlanningClarificationResolver planningClarificationResolver() {
        return new PlanningClarificationResolver();
    }

    @Bean
    AgentRuntimeErrorMapper agentRuntimeErrorMapper() {
        return new AgentRuntimeErrorMapper();
    }

    @Bean
    CapabilityCatalog capabilityCatalog(
            CapabilityRegistry capabilityRegistry,
            DomainMetadataPort domainMetadataPort,
            Clock clock) {
        return new CapabilityCatalog(capabilityRegistry, domainMetadataPort, clock);
    }

    @Bean
    CapabilitySelectionResolver capabilitySelectionResolver(CapabilityRegistry capabilityRegistry) {
        return new CapabilitySelectionResolver(capabilityRegistry);
    }

    @Bean
    ProfileBehaviorProjectionBoundary profileBehaviorProjectionBoundary(AgentMetadataStore store) {
        return new ProfileBehaviorProjectionBoundary(store);
    }

    @Bean
    RuntimePlanningRequestFactory runtimePlanningRequestFactory(
            DomainMetadataPort domainMetadataPort,
            ProfileBehaviorProjectionBoundary profileBehaviorProjectionBoundary,
            AgentProperties properties) {
        return new RuntimePlanningRequestFactory(domainMetadataPort, profileBehaviorProjectionBoundary, properties);
    }

    @Bean
    PlanningService planningService(
            AuthorizationPlanningPort authorizationPlanningPort,
            CapabilityCatalog capabilityCatalog,
            RuntimePlanningRequestFactory requestFactory,
            AgentRuntimeClient runtimeClient,
            RouteOutcomeValidator routeOutcomeValidator,
            CapabilitySelectionResolver capabilitySelectionResolver,
            ContextPlanningPort contextPlanningPort,
            PlanOutcomeValidator planOutcomeValidator,
            PlanningClarificationResolver clarificationResolver,
            AgentRuntimeErrorMapper runtimeErrorMapper,
            Clock clock) {
        return new PlanningService(
                authorizationPlanningPort,
                capabilityCatalog,
                requestFactory,
                runtimeClient,
                routeOutcomeValidator,
                capabilitySelectionResolver,
                contextPlanningPort,
                planOutcomeValidator,
                clarificationResolver,
                runtimeErrorMapper,
                clock);
    }
}
