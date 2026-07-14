package com.dylan.agent.capability.document.provider;

import com.dylan.common.security.ServiceTokenProperties;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentProviderSecurityValidatorTest {

    @Test
    void failsWithoutProviderScopeBecauseDocumentRegistrationIsNotFeatureFlagged() {
        ServiceTokenProperties serviceTokenProperties = new ServiceTokenProperties();
        serviceTokenProperties.setScopes(List.of("agent.permission.resolve"));

        var validator = new DocumentProviderSecurityValidator(serviceTokenProperties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining(DocumentProviderSecurityValidator.PROVIDER_INVOKE_SCOPE);
    }

    @Test
    void passesWithProviderScope() {
        ServiceTokenProperties serviceTokenProperties = new ServiceTokenProperties();
        serviceTokenProperties.setScopes(List.of("agent.permission.resolve", DocumentProviderSecurityValidator.PROVIDER_INVOKE_SCOPE));

        var validator = new DocumentProviderSecurityValidator(serviceTokenProperties);

        assertThatCode(validator::afterPropertiesSet).doesNotThrowAnyException();
    }
}
