package com.dylan.agent.adapter.employee;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.dylan.common.security.ServiceTokenProvider;

import feign.RequestInterceptor;
import feign.RequestTemplate;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;

class EmployeeAgentFeignSecurityConfigurationTest {

    @Test
    void replacesRelayedUserTokenWithServiceToken() {
        ServiceTokenProvider provider = mock(ServiceTokenProvider.class);
        when(provider.token()).thenReturn("employee-service-token");
        RequestInterceptor interceptor = new EmployeeAgentFeignSecurityConfiguration()
                .employeeAgentServiceTokenInterceptor(provider);
        RequestTemplate template = new RequestTemplate();
        template.header(HttpHeaders.AUTHORIZATION, "Bearer user-token");

        interceptor.apply(template);

        assertThat(template.headers().get(HttpHeaders.AUTHORIZATION))
                .containsExactly("Bearer employee-service-token");
    }
}
