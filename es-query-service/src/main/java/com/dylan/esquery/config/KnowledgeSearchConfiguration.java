package com.dylan.esquery.config;

import org.elasticsearch.client.RestClient;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.core.convert.converter.Converter;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.access.intercept.AuthorizationFilter;

import com.dylan.common.security.BoundedRequestBodyFilter;
import com.dylan.esquery.service.KnowledgeProfileVerifier;
import com.dylan.esquery.service.KnowledgeReadAccessGuard;
import com.dylan.esquery.service.KnowledgeSearchService;
import com.dylan.esquery.web.KnowledgeSearchJsonCodec;
import com.fasterxml.jackson.databind.ObjectMapper;

@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(prefix = "es.query.knowledge", name = "enabled", havingValue = "true")
public class KnowledgeSearchConfiguration {

	@Bean
	KnowledgeSearchJsonCodec knowledgeSearchJsonCodec(ObjectMapper objectMapper) {
		return new KnowledgeSearchJsonCodec(objectMapper);
	}

	@Bean
	BoundedRequestBodyFilter knowledgeSearchBodyLimitFilter() {
		return new BoundedRequestBodyFilter("/es/knowledge/", KnowledgeSearchJsonCodec.MAX_BODY_BYTES);
	}

	@Bean
	FilterRegistrationBean<BoundedRequestBodyFilter> knowledgeSearchBodyLimitFilterRegistration(
			BoundedRequestBodyFilter filter) {
		FilterRegistrationBean<BoundedRequestBodyFilter> registration = new FilterRegistrationBean<>(filter);
		registration.setEnabled(false);
		return registration;
	}

	@Bean
	KnowledgeReadAccessGuard knowledgeReadAccessGuard(KnowledgeSearchProperties properties) {
		return new KnowledgeReadAccessGuard(properties);
	}

	@Bean
	KnowledgeSearchService knowledgeSearchService(RestClient restClient, ObjectMapper objectMapper,
			KnowledgeSearchProperties properties) {
		return new KnowledgeSearchService(restClient, objectMapper, properties);
	}

	@Bean
	KnowledgeProfileVerifier knowledgeProfileVerifier(RestClient restClient, ObjectMapper objectMapper,
			KnowledgeSearchProperties properties) {
		return new KnowledgeProfileVerifier(restClient, objectMapper, properties);
	}

	@Bean
	@Order(1)
	SecurityFilterChain knowledgeSearchSecurityFilterChain(HttpSecurity http,
			@Qualifier("userRoleJwtAuthenticationConverter")
			Converter<Jwt, AbstractAuthenticationToken> converter,
			BoundedRequestBodyFilter knowledgeSearchBodyLimitFilter) throws Exception {
		return http.securityMatcher("/es/knowledge/**")
				.csrf(csrf -> csrf.disable())
				.authorizeHttpRequests(auth -> auth.anyRequest()
						.hasAnyAuthority("ROLE_ADMIN", "ROLE_VIEWER"))
				.oauth2ResourceServer(oauth2 -> oauth2
						.jwt(jwt -> jwt.jwtAuthenticationConverter(converter)))
				.addFilterAfter(knowledgeSearchBodyLimitFilter, AuthorizationFilter.class)
				.build();
	}
}
