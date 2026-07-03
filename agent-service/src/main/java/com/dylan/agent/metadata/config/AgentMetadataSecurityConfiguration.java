package com.dylan.agent.metadata.config;

import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.kernel.port.AuthorizationExecutionPort;
import com.dylan.agent.kernel.port.ResultSecurityPort;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.metadata.authorization.internal.AuthorizationExecutionPortImpl;
import com.dylan.agent.metadata.authorization.internal.AuthorizationPlanningPortImpl;
import com.dylan.agent.metadata.authorization.internal.DelegationBoundary;
import com.dylan.agent.metadata.authorization.internal.UserPermissionBoundary;
import com.dylan.agent.metadata.authorization.model.DelegationConstraint;
import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;
import com.dylan.agent.metadata.authorization.port.AuthorizationPlanningPort;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.crypto.internal.AeadProtectedPayloadCodec;
import com.dylan.agent.metadata.crypto.internal.EnvironmentPayloadKeyProvider;
import com.dylan.agent.metadata.crypto.port.PayloadKeyProvider;
import com.dylan.agent.metadata.crypto.port.ProtectedPayloadCodec;
import com.dylan.agent.metadata.domain.internal.DomainMetadataProperties;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.metadata.policy.internal.AgentPolicyConfiguration;
import com.dylan.agent.metadata.profile.internal.AgentProfileRegistry;
import com.dylan.agent.metadata.profile.internal.EffectiveProfileCalculator;
import com.dylan.agent.metadata.result.AggregateResultSecurityProjector;
import com.dylan.agent.metadata.result.QueryPreviewResultSecurityProjector;
import com.dylan.agent.metadata.result.QueryResultSecurityProjector;
import com.dylan.agent.metadata.result.ResultSecurityBoundary;
import com.dylan.agent.metadata.result.ResultSecurityProjector;
import com.dylan.agent.metadata.result.ResultSecurityProjectorRegistry;
import com.dylan.agent.metadata.result.ResultValueMaskingSupport;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * D03 规划和执行端口的元数据/安全装配根。
 */
@Configuration(proxyBeanMethods = false)
public class AgentMetadataSecurityConfiguration {

    @Bean
    AgentMetadataBootstrap agentMetadataBootstrap(
            AgentProperties properties,
            DomainMetadataProperties domainMetadataProperties) {
        return new DefaultAgentMetadataBootstrap(properties, domainMetadataProperties);
    }

    @Bean
    AgentMetadataStore agentMetadataStore(AgentMetadataBootstrap bootstrap) {
        return new AgentMetadataStore(bootstrap.bootstrap());
    }

    @Bean
    PayloadJsonCodec payloadJsonCodec(ObjectMapper objectMapper) {
        return new PayloadJsonCodec(objectMapper);
    }

    @Bean
    AgentSecuritySettingsRegistry agentSecuritySettingsRegistry(AgentMetadataStore metadataStore) {
        return new AgentSecuritySettingsRegistry(metadataStore.current().securitySettings());
    }

    @Bean
    AgentProfileRegistry agentProfileRegistry(AgentMetadataStore metadataStore) {
        return new AgentProfileRegistry(metadataStore);
    }

    @Bean
    AgentPolicyConfiguration agentPolicyConfiguration(AgentMetadataStore metadataStore) {
        return new AgentPolicyConfiguration(metadataStore);
    }

    @Bean
    PayloadKeyProvider payloadKeyProvider() {
        return new EnvironmentPayloadKeyProvider();
    }

    @Bean
    ProtectedPayloadCodec protectedPayloadCodec(
            AgentSecuritySettingsRegistry settingsRegistry,
            PayloadKeyProvider keyProvider) {
        return new AeadProtectedPayloadCodec(settingsRegistry, keyProvider);
    }

    @Bean
    ResultValueMaskingSupport resultValueMaskingSupport(FieldMaskerRegistry fieldMaskerRegistry) {
        return new ResultValueMaskingSupport(fieldMaskerRegistry);
    }

    @Bean
    QueryResultSecurityProjector queryResultSecurityProjector(ResultValueMaskingSupport maskingSupport) {
        return new QueryResultSecurityProjector(maskingSupport);
    }

    @Bean
    QueryPreviewResultSecurityProjector queryPreviewResultSecurityProjector(ResultValueMaskingSupport maskingSupport) {
        return new QueryPreviewResultSecurityProjector(maskingSupport);
    }

    @Bean
    AggregateResultSecurityProjector aggregateResultSecurityProjector(ResultValueMaskingSupport maskingSupport) {
        return new AggregateResultSecurityProjector(maskingSupport);
    }

    @Bean
    ResultSecurityProjectorRegistry resultSecurityProjectorRegistry(
            List<ResultSecurityProjector<?>> projectors) {
        return new ResultSecurityProjectorRegistry(projectors);
    }

    @Bean
    ResultSecurityPort resultSecurityPort(ContractRegistry contractRegistry,
                                          ResultSecurityProjectorRegistry projectorRegistry,
                                          PayloadJsonCodec payloadJsonCodec) {
        return new ResultSecurityBoundary(contractRegistry, projectorRegistry, payloadJsonCodec);
    }

    @Bean
    AuthorizationExecutionPort authorizationExecutionPort(
            UserPermissionBoundary userPermissionBoundary,
            DomainMetadataPort domainMetadataPort,
            Clock clock) {
        return new AuthorizationExecutionPortImpl(userPermissionBoundary, domainMetadataPort, clock);
    }

    @Bean
    EffectiveProfileCalculator effectiveProfileCalculator() {
        return new EffectiveProfileCalculator();
    }

    @Bean
    DelegationBoundary delegationBoundary() {
        return new DelegationBoundary(Map.of(
                DelegationConstraintRef.CHAT_ALL,
                new DelegationConstraint(DelegationConstraintRef.CHAT_ALL, Set.of(), Set.of())));
    }

    @Bean
    AuthorizationPlanningPort authorizationPlanningPort(
            AgentMetadataStore metadataStore,
            EffectiveProfileCalculator profileCalculator,
            UserPermissionBoundary userPermissionBoundary,
            DelegationBoundary delegationBoundary,
            DomainMetadataPort domainMetadataPort,
            Clock clock) {
        return new AuthorizationPlanningPortImpl(
                metadataStore,
                profileCalculator,
                userPermissionBoundary,
                delegationBoundary,
                domainMetadataPort,
                clock);
    }
}
