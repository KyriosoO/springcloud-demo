package com.dylan.agent.capability.document.provider;

import com.dylan.common.security.ServiceTokenProvider;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class DocumentProviderAuthHeaderProviderTest {

    @Test
    void returnsBearerHeaderFromServiceToken() {
        ServiceTokenProvider tokenProvider = mock(ServiceTokenProvider.class);
        when(tokenProvider.token()).thenReturn("service-token");

        var provider = new DocumentProviderAuthHeaderProvider(tokenProvider);

        assertThat(provider.authorizationHeader()).isEqualTo("Bearer service-token");
    }

    @Test
    void failsClosedWhenServiceTokenIsBlank() {
        ServiceTokenProvider tokenProvider = mock(ServiceTokenProvider.class);
        when(tokenProvider.token()).thenReturn(" ");

        var provider = new DocumentProviderAuthHeaderProvider(tokenProvider);

        assertThatThrownBy(provider::authorizationHeader)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("service token");
    }
}
