package com.dylan.agent.planning;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

import java.time.Clock;
import java.time.ZoneOffset;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import com.dylan.agent.client.AgentRuntimeClient;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.kernel.registration.CapabilityRegistry;
import com.dylan.agent.metadata.authorization.port.AuthorizationPlanningPort;
import com.dylan.agent.metadata.config.AgentMetadataStore;
import com.dylan.agent.metadata.context.port.ContextPlanningPort;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import com.dylan.common.security.SecretProperties;

class PlanningConfigurationTest {

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withUserConfiguration(PlanningConfiguration.class)
            .withBean(AuthorizationPlanningPort.class, () -> mock(AuthorizationPlanningPort.class))
            .withBean(CapabilityRegistry.class, () -> mock(CapabilityRegistry.class))
            .withBean(DomainMetadataPort.class, () -> mock(DomainMetadataPort.class))
            .withBean(AgentMetadataStore.class, () -> new AgentMetadataStore(
                    new com.dylan.agent.metadata.config.DefaultAgentMetadataBootstrap(
                            DomainMetadataTestSupport.agentProperties(),
                            DomainMetadataTestSupport.properties(),
                            new SecretProperties()).bootstrap()))
            .withBean(AgentRuntimeClient.class, () -> mock(AgentRuntimeClient.class))
            .withBean(ContextPlanningPort.class, () -> mock(ContextPlanningPort.class))
            .withBean(Clock.class, () -> Clock.fixed(
                    DomainMetadataTestSupport.TEST_CLOCK.instant(),
                    ZoneOffset.UTC))
            .withBean(AgentProperties.class, DomainMetadataTestSupport::agentProperties);

    @Test
    void registersPlanningServiceWhenAllProductionDependenciesExist() {
        contextRunner.run(context -> assertThat(context).hasSingleBean(PlanningService.class));
    }

    @Test
    void missingMetadataStoreFailsStartupInsteadOfStartingHalfChain() {
        new ApplicationContextRunner()
                .withUserConfiguration(PlanningConfiguration.class)
                .withBean(AuthorizationPlanningPort.class, () -> mock(AuthorizationPlanningPort.class))
                .withBean(CapabilityRegistry.class, () -> mock(CapabilityRegistry.class))
                .withBean(DomainMetadataPort.class, () -> mock(DomainMetadataPort.class))
                .withBean(AgentRuntimeClient.class, () -> mock(AgentRuntimeClient.class))
                .withBean(ContextPlanningPort.class, () -> mock(ContextPlanningPort.class))
                .withBean(Clock.class, () -> Clock.fixed(
                        DomainMetadataTestSupport.TEST_CLOCK.instant(),
                        ZoneOffset.UTC))
                .withBean(AgentProperties.class, DomainMetadataTestSupport::agentProperties)
                .run(context -> assertThat(context).hasFailed());
    }
}
