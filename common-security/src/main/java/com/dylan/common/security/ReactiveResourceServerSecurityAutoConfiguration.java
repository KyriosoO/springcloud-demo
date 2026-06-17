package com.dylan.common.security;

import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.oauth2.jwt.NimbusReactiveJwtDecoder;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.security.web.server.SecurityWebFilterChain;

import javax.crypto.SecretKey;

@AutoConfiguration(after = JwtConfig.class)
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.REACTIVE)
@ConditionalOnClass({ ServerHttpSecurity.class, ReactiveJwtDecoder.class })
public class ReactiveResourceServerSecurityAutoConfiguration {

	@Bean
	@ConditionalOnMissingBean
	ReactiveJwtDecoder reactiveJwtDecoder(SecretKey secretKey) {
		return NimbusReactiveJwtDecoder.withSecretKey(secretKey).build();
	}

	@Bean
	@ConditionalOnMissingBean(SecurityWebFilterChain.class)
	SecurityWebFilterChain reactiveResourceServerSecurityWebFilterChain(ServerHttpSecurity http) {
		return http.csrf(ServerHttpSecurity.CsrfSpec::disable)
				.authorizeExchange(auth -> auth
						// WebSocket 握手放行，由业务 WebSocketHandler 自己校验 token。
						.pathMatchers("/ws/**").permitAll()
						.anyExchange().authenticated())
				.oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
				.build();
	}
}
