package com.dylan.agent.capability.document.provider;

import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import com.dylan.common.security.ServiceTokenProperties;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentProviderSecurityValidatorTest {

    @Test
    void passesWhenProviderDisabledWithoutProviderScope() {
        var agentProperties = DomainMetadataTestSupport.agentProperties();
        ServiceTokenProperties serviceTokenProperties = new ServiceTokenProperties();
        serviceTokenProperties.setScopes(List.of("agent.permission.resolve"));

        var validator = new DocumentProviderSecurityValidator(agentProperties, serviceTokenProperties);

        assertThatCode(validator::afterPropertiesSet).doesNotThrowAnyException();
    }

    @Test
    void failsWhenEmbeddingEnabledWithoutProviderScope() {
        var agentProperties = DomainMetadataTestSupport.agentProperties();
        agentProperties.getDocument().getEmbedding().setEnabled(true);
        ServiceTokenProperties serviceTokenProperties = new ServiceTokenProperties();
        serviceTokenProperties.setScopes(List.of("agent.permission.resolve"));

        var validator = new DocumentProviderSecurityValidator(agentProperties, serviceTokenProperties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining(DocumentProviderSecurityValidator.PROVIDER_INVOKE_SCOPE);
    }

    @Test
    void passesWhenGenerationEnabledWithProviderScope() {
        var agentProperties = DomainMetadataTestSupport.agentProperties();
        agentProperties.getDocument().getGeneration().setEnabled(true);
        ServiceTokenProperties serviceTokenProperties = new ServiceTokenProperties();
        serviceTokenProperties.setScopes(List.of("agent.permission.resolve", DocumentProviderSecurityValidator.PROVIDER_INVOKE_SCOPE));

        var validator = new DocumentProviderSecurityValidator(agentProperties, serviceTokenProperties);

        assertThatCode(validator::afterPropertiesSet).doesNotThrowAnyException();
    }
}
