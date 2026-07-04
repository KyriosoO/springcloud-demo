package com.dylan.springgateway.config;

import com.dylan.common.security.KidAwareReactiveJwtDecoder;
import com.dylan.common.security.JwtKeyProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;

@Configuration("gatewayJwtConfig")
public class JwtConfig {

	@Bean
	ReactiveJwtDecoder reactiveJwtDecoder(JwtKeyProvider jwtKeyProvider) {
		return new KidAwareReactiveJwtDecoder(jwtKeyProvider);
	}
}
