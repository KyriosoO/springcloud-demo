package com.dylan.common.security;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;

import org.springframework.context.annotation.Bean;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;

import com.nimbusds.jose.jwk.source.ImmutableSecret;

@AutoConfiguration
public class JwtConfig {

	private static final String SECRET = "my-super-secret-key-my-super-secret-key";

	@Bean
	@ConditionalOnMissingBean
	SecretKey jwtSecretKey() {
		return new SecretKeySpec(SECRET.getBytes(), "HmacSHA256");
	}

	@Bean
	@ConditionalOnMissingBean
	JwtEncoder jwtEncoder(SecretKey secretKey) {
		return new NimbusJwtEncoder(new ImmutableSecret<>(secretKey));
	}

	@Bean
	@ConditionalOnMissingBean
	JwtDecoder jwtDecoder(SecretKey secretKey) {
		return NimbusJwtDecoder.withSecretKey(secretKey).build();
	}
}
