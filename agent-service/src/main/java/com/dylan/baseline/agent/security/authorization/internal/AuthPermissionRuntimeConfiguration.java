package com.dylan.baseline.agent.security.authorization.internal;

import com.dylan.baseline.agent.security.authorization.AuthPermissionAuthorityPort;
import com.dylan.common.security.JwtKeyProvider;
import com.dylan.common.security.ServiceTokenProperties;
import com.dylan.common.security.ServiceTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.http.HttpClient;
import java.time.Clock;
import java.time.Duration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.web.client.RestClient;

@Configuration(proxyBeanMethods = false)
@EnableConfigurationProperties({AuthPermissionClientProperties.class, ServiceTokenProperties.class})
class AuthPermissionRuntimeConfiguration {

    @Bean
    @ConditionalOnMissingBean
    Clock agentSecurityClock() {
        return Clock.systemUTC();
    }

    @Bean
    @ConditionalOnMissingBean
    ServiceTokenProvider agentServiceTokenProvider(
            JwtEncoder jwtEncoder,
            ServiceTokenProperties properties,
            Environment environment,
            JwtKeyProvider jwtKeyProvider) {
        return new ServiceTokenProvider(jwtEncoder, properties, environment, jwtKeyProvider);
    }

    @Bean
    AuthPermissionRestClientFactory authPermissionRestClientFactory(
            RestClient.Builder builder,
            AuthPermissionClientProperties properties) {
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(properties.getConnectTimeout())
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        RestClient.Builder template = builder.clone();
        return readTimeout -> buildClient(template, httpClient, properties.getBaseUrl(), readTimeout);
    }

    @Bean
    AuthPermissionAuthorityAdapter authPermissionAuthorityAdapter(Clock clock) {
        return new AuthPermissionAuthorityAdapter(clock);
    }

    @Bean
    AuthPermissionAuthorityPort authPermissionAuthorityPort(
            AuthPermissionRestClientFactory restClientFactory,
            AuthPermissionClientProperties properties,
            ServiceTokenProvider serviceTokenProvider,
            ObjectMapper objectMapper,
            AuthPermissionAuthorityAdapter responseAdapter,
            Clock clock) {
        return new HttpAuthPermissionAuthorityAdapter(
                restClientFactory,
                properties,
                serviceTokenProvider,
                objectMapper,
                responseAdapter,
                clock);
    }

    private static RestClient buildClient(
            RestClient.Builder template,
            HttpClient httpClient,
            String baseUrl,
            Duration readTimeout) {
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(readTimeout);
        return template.clone()
                .baseUrl(baseUrl)
                .requestFactory(requestFactory)
                .build();
    }
}
