package com.dylan.common.security;

import javax.crypto.SecretKey;

import org.springframework.context.annotation.Bean;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.core.env.Environment;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.OctetSequenceKey;
import com.nimbusds.jose.jwk.source.ImmutableJWKSet;
import com.nimbusds.jose.proc.SecurityContext;

@AutoConfiguration
@EnableConfigurationProperties(SecretProperties.class)
public class JwtConfig {

	@Bean
	@ConditionalOnMissingBean
	SecretMaterialProvider secretMaterialProvider(SecretProperties properties, Environment environment) {
		SecretPropertiesValidator.validateJwt(properties, environment);
		return new CompositeSecretMaterialProvider(properties);
	}

	@Bean
	@ConditionalOnMissingBean
	JwtKeyProvider jwtKeyProvider(
			SecretProperties properties,
			SecretMaterialProvider secretMaterialProvider,
			Environment environment) {
		SecretPropertiesValidator.validateJwt(properties, environment);
		return new SecretMaterialJwtKeyProvider(properties, secretMaterialProvider);
	}

	@Bean
	@ConditionalOnMissingBean
	SecretKey jwtSecretKey(JwtKeyProvider jwtKeyProvider) {
		return jwtKeyProvider.current().activeKey();
	}

	@Bean
	@ConditionalOnMissingBean
	JwtEncoder jwtEncoder(JwtKeyProvider jwtKeyProvider) {
		JwtKeySet keySet = jwtKeyProvider.current();
		OctetSequenceKey jwk = new OctetSequenceKey.Builder(keySet.activeKey().getEncoded())
				.keyID(keySet.activeKeyId())
				.algorithm(JWSAlgorithm.HS256)
				.build();
		return new NimbusJwtEncoder(new ImmutableJWKSet<SecurityContext>(new JWKSet(jwk)));
	}

	@Bean
	@ConditionalOnMissingBean
	JwtDecoder jwtDecoder(JwtKeyProvider jwtKeyProvider) {
		return new KidAwareJwtDecoder(jwtKeyProvider);
	}
}
