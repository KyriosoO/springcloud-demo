package com.dylan.common.security;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.core.env.Environment;
import org.springframework.http.HttpHeaders;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import feign.RequestInterceptor;

/**
 * Feign token 转发自动配置，统一处理用户 token 透传和服务 token 兜底。
 */
@AutoConfiguration(after = JwtConfig.class)
@ConditionalOnClass(RequestInterceptor.class)
@EnableConfigurationProperties(ServiceTokenProperties.class)
public class FeignTokenRelayAutoConfiguration {
	/**
	 * 创建服务 token 提供器。
	 */
	@Bean
	@ConditionalOnBean(JwtEncoder.class)
	@ConditionalOnMissingBean
	@ConditionalOnProperty(prefix = "common.security.service-token", name = "enabled", havingValue = "true", matchIfMissing = true)
	ServiceTokenProvider serviceTokenProvider(JwtEncoder jwtEncoder, ServiceTokenProperties properties,
			Environment environment) {
		return new ServiceTokenProvider(jwtEncoder, properties, environment);
	}

	/**
	 * 创建 Feign 请求拦截器，优先转发用户 token，缺失时使用服务 token。
	 */
	@Bean
	@ConditionalOnMissingBean(name = "feignTokenRelayInterceptor")
	RequestInterceptor feignTokenRelayInterceptor(ObjectProvider<ServiceTokenProvider> serviceTokenProvider) {
		return template -> {
			Jwt jwt = currentJwt();
			if (jwt != null && jwt.getTokenValue() != null && !jwt.getTokenValue().isBlank()) {
				template.header(HttpHeaders.AUTHORIZATION, "Bearer " + jwt.getTokenValue());
				return;
			}
			ServiceTokenProvider provider = serviceTokenProvider.getIfAvailable();
			if (provider != null) {
				template.header(HttpHeaders.AUTHORIZATION, "Bearer " + provider.token());
			}
		};
	}

	/**
	 * 从当前安全上下文读取 Jwt。
	 */
	private Jwt currentJwt() {
		Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
		if (authentication instanceof JwtAuthenticationToken jwtAuthenticationToken) {
			return jwtAuthenticationToken.getToken();
		}
		if (authentication != null && authentication.getPrincipal() instanceof Jwt jwt) {
			return jwt;
		}
		return null;
	}
}
