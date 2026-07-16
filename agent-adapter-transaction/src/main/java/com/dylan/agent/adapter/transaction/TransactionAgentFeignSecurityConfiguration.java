package com.dylan.agent.adapter.transaction;

import com.dylan.common.security.ServiceTokenProvider;

import feign.RequestInterceptor;
import org.springframework.context.annotation.Bean;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpHeaders;

/** Transaction Agent Client 始终使用 agent-service 服务身份，不透传最终用户 JWT。 */
public class TransactionAgentFeignSecurityConfiguration {

    @Bean
    @Order(Ordered.LOWEST_PRECEDENCE)
    RequestInterceptor transactionAgentServiceTokenInterceptor(ServiceTokenProvider serviceTokenProvider) {
        return template -> {
            template.removeHeader(HttpHeaders.AUTHORIZATION);
            template.header(HttpHeaders.AUTHORIZATION, "Bearer " + serviceTokenProvider.token());
        };
    }
}
