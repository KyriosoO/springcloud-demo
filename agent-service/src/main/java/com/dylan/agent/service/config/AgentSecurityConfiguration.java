package com.dylan.agent.service.config;

import com.dylan.agent.service.contract.CapabilityStatus;
import com.dylan.agent.service.contract.FailureSource;
import com.dylan.agent.service.web.AgentPublicErrorWriter;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.convert.converter.Converter;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.security.web.server.SecurityWebFilterChain;

import reactor.core.publisher.Mono;

@Configuration(proxyBeanMethods = false)
public class AgentSecurityConfiguration {

    @Bean
    SecurityWebFilterChain agentSecurityWebFilterChain(
            ServerHttpSecurity http,
            ReactiveJwtDecoder decoder,
            @Qualifier("reactiveUserRoleJwtAuthenticationConverter")
            Converter<Jwt, Mono<AbstractAuthenticationToken>> authorityConverter,
            AgentPublicErrorWriter errorWriter) {
        return http
                .csrf(ServerHttpSecurity.CsrfSpec::disable)
                .authorizeExchange(authorize -> authorize
                        .pathMatchers("/actuator/health/**").permitAll()
                        .pathMatchers(HttpMethod.GET, "/agent.html").authenticated()
                        .pathMatchers(HttpMethod.POST, "/api/v1/agent/query-runs").hasAuthority("ROLE_ADMIN")
                        .pathMatchers(HttpMethod.POST, "/api/v1/agent/queries").authenticated()
                        .anyExchange().denyAll())
                .oauth2ResourceServer(oauth2 -> oauth2
                        .jwt(jwt -> jwt.jwtDecoder(decoder).jwtAuthenticationConverter(authorityConverter))
                        .authenticationEntryPoint((exchange, error) -> errorWriter.write(
                                exchange, HttpStatus.UNAUTHORIZED, CapabilityStatus.UNAUTHENTICATED,
                                "core.user_identity_required", FailureSource.CORE))
                        .accessDeniedHandler((exchange, error) -> errorWriter.write(
                                exchange, HttpStatus.FORBIDDEN, CapabilityStatus.FORBIDDEN,
                                "core.access_denied", FailureSource.CORE)))
                .exceptionHandling(exceptions -> exceptions
                        .authenticationEntryPoint((exchange, error) -> errorWriter.write(
                                exchange, HttpStatus.UNAUTHORIZED, CapabilityStatus.UNAUTHENTICATED,
                                "core.user_identity_required", FailureSource.CORE))
                        .accessDeniedHandler((exchange, error) -> errorWriter.write(
                                exchange, HttpStatus.FORBIDDEN, CapabilityStatus.FORBIDDEN,
                                "core.access_denied", FailureSource.CORE)))
                .build();
    }
}
