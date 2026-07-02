package com.dylan.agent.metadata.authorization.internal;

import com.dylan.agent.config.AgentProperties;
import com.dylan.common.security.ServiceTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.net.http.HttpClient;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

@Configuration(proxyBeanMethods = false)
@EnableConfigurationProperties(AgentProperties.class)
public class AuthServiceUserPermissionAuthorityConfiguration {

    @Bean
    RestClient authServicePermissionRestClient(RestClient.Builder builder, AgentProperties properties) {
        AgentProperties.AuthServiceProperties authService = properties.getAuthService();
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(authService.getConnectTimeout())
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(authService.getReadTimeout());
        return builder
                .baseUrl(authService.getBaseUrl())
                .requestFactory(requestFactory)
                .defaultHeader("Content-Type", "application/json")
                .build();
    }

    @Bean
    AuthServiceUserPermissionAuthorityAdapter authServiceUserPermissionAuthorityAdapter(
            @Qualifier("authServicePermissionRestClient") RestClient restClient,
            AgentProperties properties,
            ObjectMapper objectMapper,
            ServiceTokenProvider serviceTokenProvider,
            java.time.Clock clock) {
        return new AuthServiceUserPermissionAuthorityAdapter(
                restClient,
                properties.getAuthService(),
                objectMapper,
                serviceTokenProvider,
                clock);
    }
}
