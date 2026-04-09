package com.dylan.springGateway.config;

import javax.crypto.SecretKey;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.oauth2.jwt.NimbusReactiveJwtDecoder;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;

@Configuration("gatewayJwtConfig")
public class JwtConfig {

	@Bean
	ReactiveJwtDecoder reactiveJwtDecoder(SecretKey secretKey) {
		return NimbusReactiveJwtDecoder.withSecretKey(secretKey).build();
	}
}