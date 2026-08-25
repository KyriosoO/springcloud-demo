package com.dylan.employee.security;

import java.util.Set;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.core.convert.converter.Converter;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.util.matcher.RequestMatcher;

import com.dylan.common.security.JwtResourceServerHttpSecurity;

@Configuration(proxyBeanMethods = false)
public class EmployeeDetailSecurityConfiguration {
	private static final Set<String> NON_DETAIL_SEGMENTS = Set.of("count", "es");

	@Bean
	@Order(1)
	SecurityFilterChain employeeDetailSecurityFilterChain(HttpSecurity http,
			@Qualifier("userRoleJwtAuthenticationConverter")
			Converter<Jwt, AbstractAuthenticationToken> converter) throws Exception {
		RequestMatcher detailMatcher = employeeDetailMatcher();
		return http.securityMatcher(detailMatcher)
				.csrf(csrf -> csrf.disable())
				.authorizeHttpRequests(auth -> auth.anyRequest()
						.hasAnyAuthority("ROLE_ADMIN", "ROLE_VIEWER"))
				.oauth2ResourceServer(oauth2 -> oauth2
						.jwt(jwt -> jwt.jwtAuthenticationConverter(converter)))
				.build();
	}

	@Bean
	@Order(2)
	SecurityFilterChain employeeEsQuerySecurityFilterChain(HttpSecurity http,
			@Qualifier("userRoleJwtAuthenticationConverter")
			Converter<Jwt, AbstractAuthenticationToken> converter) throws Exception {
		return http.securityMatcher(employeeEsQueryMatcher())
				.csrf(csrf -> csrf.disable())
				.authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
				.oauth2ResourceServer(oauth2 -> oauth2
						.jwt(jwt -> jwt.jwtAuthenticationConverter(converter)))
				.build();
	}

	@Bean
	@Order(3)
	SecurityFilterChain employeeFallbackSecurityFilterChain(HttpSecurity http) throws Exception {
		return JwtResourceServerHttpSecurity.applyDefaults(http)
				.authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
				.build();
	}

	static RequestMatcher employeeDetailMatcher() {
		return request -> {
			if (!"GET".equalsIgnoreCase(request.getMethod())) {
				return false;
			}
			String requestUri = request.getRequestURI();
			String contextPath = request.getContextPath();
			String path = contextPath == null || contextPath.isEmpty()
					? requestUri
					: requestUri.substring(contextPath.length());
			if (path == null || !path.startsWith("/employees/")) {
				return false;
			}
			String segment = path.substring("/employees/".length());
			return !segment.isBlank() && !segment.contains("/") && !NON_DETAIL_SEGMENTS.contains(segment);
		};
	}

	static RequestMatcher employeeEsQueryMatcher() {
		return request -> {
			if (!"POST".equalsIgnoreCase(request.getMethod())) {
				return false;
			}
			String requestUri = request.getRequestURI();
			String contextPath = request.getContextPath();
			String path = contextPath == null || contextPath.isEmpty()
					? requestUri
					: requestUri.substring(contextPath.length());
			return "/employees/es/search".equals(path)
					|| "/employees/es/vector-search".equals(path);
		};
	}
}
