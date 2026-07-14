package com.dylan.agent.metadata.config;

import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.kernel.port.AuthorizationExecutionPort;
import com.dylan.agent.kernel.port.ResultSecurityPort;
import com.dylan.agent.capability.document.DocumentObservabilitySupport;
import com.dylan.agent.capability.document.profile.DocumentProfileAssetRegistry;
import com.dylan.agent.capability.document.profile.DocumentProfileAssets;
import com.dylan.agent.capability.document.profile.DocumentProfileProperties;
import com.dylan.agent.capability.document.profile.DocumentPolicyConstraintRegistry;
import com.dylan.agent.capability.document.security.DocumentRevocationGuard;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.metadata.authorization.internal.AuthorizationExecutionPortImpl;
import com.dylan.agent.metadata.authorization.internal.AuthorizationPlanningPortImpl;
import com.dylan.agent.metadata.authorization.internal.UserPermissionBoundary;
import com.dylan.agent.metadata.authorization.port.AuthorizationPlanningPort;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.crypto.internal.AeadProtectedPayloadCodec;
import com.dylan.agent.metadata.crypto.internal.SecretMaterialPayloadKeyProvider;
import com.dylan.agent.metadata.crypto.port.PayloadKeyProvider;
import com.dylan.agent.metadata.crypto.port.ProtectedPayloadCodec;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.metadata.policy.internal.AgentPolicyConfiguration;
import com.dylan.agent.metadata.profile.internal.AgentProfileRegistry;
import com.dylan.agent.metadata.profile.internal.EffectiveProfileCalculator;
import com.dylan.agent.metadata.result.AggregateResultSecurityProjector;
import com.dylan.agent.metadata.result.DocumentResultSecurityProjector;
import com.dylan.agent.metadata.result.QueryPreviewResultSecurityProjector;
import com.dylan.agent.metadata.result.QueryResultSecurityProjector;
import com.dylan.agent.metadata.result.ResultSecurityBoundary;
import com.dylan.agent.metadata.result.ResultSecurityProjector;
import com.dylan.agent.metadata.result.ResultSecurityProjectorRegistry;
import com.dylan.agent.metadata.result.ResultValueMaskingSupport;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.common.security.SecretMaterialProvider;
import com.dylan.common.security.SecretProperties;
import com.dylan.common.security.SecretPropertiesValidator;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.core.env.Environment;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

import java.time.Clock;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * D03 规划和执行端口的元数据/安全装配根。
 */
@Configuration(proxyBeanMethods = false)
@EnableConfigurationProperties(DocumentProfileProperties.class)
public class AgentMetadataSecurityConfiguration {

    @Bean
    DocumentProfileAssets.BuiltAssets documentProfileAssets(DocumentProfileProperties properties) {
        return DocumentProfileAssets.build(properties);
    }

    @Bean
    DocumentProfileAssetRegistry documentProfileAssetRegistry(DocumentProfileAssets.BuiltAssets assets) {
        return assets.profileRegistry();
    }

    @Bean
    DocumentPolicyConstraintRegistry documentPolicyConstraintRegistry(DocumentProfileAssets.BuiltAssets assets) {
        return assets.policyRegistry();
    }

    @Bean
    AgentMetadataBootstrap agentMetadataBootstrap(
            AgentProperties properties,
            DocumentProfileAssets.BuiltAssets documentAssets) {
        return new DefaultAgentMetadataBootstrap(properties, documentAssets);
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
    AgentProfileRegistry agentProfileRegistry(AgentMetadataStore metadataStore) {
        return new AgentProfileRegistry(metadataStore);
    }

    @Bean
    AgentPolicyConfiguration agentPolicyConfiguration(AgentMetadataStore metadataStore) {
        return new AgentPolicyConfiguration(metadataStore);
    }

    @Bean
    PayloadKeyProvider payloadKeyProvider(
            SecretProperties secretProperties,
            SecretMaterialProvider secretMaterialProvider,
            Environment environment) {
        SecretPropertiesValidator.validateAgentPayload(secretProperties, environment);
        return new SecretMaterialPayloadKeyProvider(secretProperties, secretMaterialProvider);
    }

    @Bean
    ProtectedPayloadCodec protectedPayloadCodec(
            SecretProperties secretProperties,
            PayloadKeyProvider keyProvider) {
        String activeKeyId = secretProperties.getAgentPayload().getActiveKeyId();
        AgentMetadataPropertiesValidator.validate(activeKeyId, keyProvider);
        return new AeadProtectedPayloadCodec(activeKeyId, keyProvider);
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
    DocumentResultSecurityProjector documentResultSecurityProjector(
            ResultValueMaskingSupport maskingSupport,
            com.fasterxml.jackson.databind.ObjectMapper objectMapper,
            Clock clock) {
        return new DocumentResultSecurityProjector(maskingSupport, objectMapper, clock);
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
            AgentMetadataStore metadataStore,
            DomainMetadataPort domainMetadataPort,
            Clock clock) {
        return new AuthorizationExecutionPortImpl(userPermissionBoundary, metadataStore, domainMetadataPort, clock);
    }

    @Bean
    EffectiveProfileCalculator effectiveProfileCalculator() {
        return new EffectiveProfileCalculator();
    }

    @Bean
    AuthorizationPlanningPort authorizationPlanningPort(
            AgentMetadataStore metadataStore,
            EffectiveProfileCalculator profileCalculator,
            UserPermissionBoundary userPermissionBoundary,
            com.dylan.agent.kernel.resource.CapabilityResourceLimitRegistry resourceLimitRegistry,
            DomainMetadataPort domainMetadataPort,
            Clock clock) {
        return new AuthorizationPlanningPortImpl(
                metadataStore,
                profileCalculator,
                userPermissionBoundary,
                new com.dylan.agent.metadata.authorization.resource.CapabilityResourceLimitResolver(
                        resourceLimitRegistry),
                domainMetadataPort,
                clock);
    }
}
