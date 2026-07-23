package com.dylan.springgateway.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.util.List;
import java.util.function.Supplier;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.HttpStatus;
import org.springframework.http.codec.ServerCodecConfigurer;
import org.springframework.web.reactive.result.view.ViewResolver;

import com.alibaba.csp.sentinel.adapter.gateway.common.rule.GatewayRuleManager;
import com.alibaba.csp.sentinel.adapter.gateway.sc.callback.GatewayCallbackManager;

@DisplayName("SentinelConfig")
class SentinelConfigTest {

    @SuppressWarnings({"unchecked", "rawtypes"})
    @Test
    @DisplayName("只注册当前存在的 Gateway 路由限流规则")
    void shouldRegisterActiveRouteRateLimits() {
        ObjectProvider<List<ViewResolver>> provider = mock(ObjectProvider.class);
        when(provider.getIfAvailable(any(Supplier.class))).thenReturn(List.of());

        SentinelConfig config = new SentinelConfig(provider, ServerCodecConfigurer.create());
        config.doInit();

        assertThat(GatewayRuleManager.getRules())
                .extracting(candidate -> candidate.getResource())
                .containsExactlyInAnyOrder("hello_route", "auth_route", "direct_route");
        var rule = GatewayRuleManager.getRules().stream()
                .filter(candidate -> "hello_route".equals(candidate.getResource()))
                .findFirst()
                .orElseThrow();
        assertThat(rule.getCount()).isEqualTo(5);
        assertThat(rule.getIntervalSec()).isEqualTo(10);
        assertThat(rule.getBurst()).isEqualTo(5);

        var response = GatewayCallbackManager.getBlockHandler()
                .handleRequest(null, null)
                .block();
        assertThat(response).isNotNull();
        assertThat(response.statusCode()).isEqualTo(HttpStatus.TOO_MANY_REQUESTS);
    }
}
