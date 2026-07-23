package com.dylan.authcenter.config;

import java.util.Arrays;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.core.annotation.Order;
import org.springframework.core.env.Environment;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2TokenValidatorResult;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.web.SecurityFilterChain;

import com.dylan.common.security.KidAwareJwtDecoder;
import com.dylan.common.security.JwtKeyProvider;
import com.dylan.common.security.PurposeScopedJwtKeyProvider;
import com.dylan.common.security.SecretMaterialProvider;
import com.dylan.common.security.SecretProperties;
import com.dylan.common.security.SecretPropertiesValidator;
import com.dylan.common.security.SecretPurpose;

@Configuration
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
@EnableConfigurationProperties(AgentServiceJwtProperties.class)
public class AgentInternalSecurityConfig {

	@Bean("userJwtDecoder")
	@Primary
	JwtDecoder userJwtDecoder(JwtKeyProvider jwtKeyProvider) {
		return new KidAwareJwtDecoder(jwtKeyProvider);
	}

	@Bean("agentServiceJwtDecoder")
	JwtDecoder agentServiceJwtDecoder(SecretProperties secrets,
			SecretMaterialProvider materialProvider,
			Environment environment,
			AgentServiceJwtProperties properties) {
		SecretPropertiesValidator.validateAgentServiceJwt(secrets, environment);
		PurposeScopedJwtKeyProvider provider = new PurposeScopedJwtKeyProvider(
				SecretPurpose.AGENT_SERVICE_JWT, secrets.getAgentServiceJwt(), materialProvider);
		KidAwareJwtDecoder decoder = new KidAwareJwtDecoder(provider);
		OAuth2TokenValidator<Jwt> contract = jwt -> validateContract(jwt, properties);
		decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(
				JwtValidators.createDefaultWithIssuer(properties.getIssuer()), contract));
		return decoder;
	}

	@Bean
	@Order(1)
	SecurityFilterChain agentInternalFilterChain(HttpSecurity http,
			@Qualifier("agentServiceJwtDecoder") JwtDecoder decoder) throws Exception {
		return http.securityMatcher("/internal/agent/**")
				.csrf(csrf -> csrf.disable())
				.authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
				.oauth2ResourceServer(oauth -> oauth.jwt(jwt -> jwt.decoder(decoder)))
				.build();
	}

	private static OAuth2TokenValidatorResult validateContract(Jwt jwt, AgentServiceJwtProperties properties) {
		String scope = jwt.getClaimAsString("scope");
		var actualScopes = scope == null ? java.util.Set.<String>of()
				: java.util.Set.copyOf(Arrays.asList(scope.trim().split("\\s+")));
		if (jwt.getAudience().contains(properties.getAudience())
				&& properties.getRequiredSubject().equals(jwt.getSubject())
				&& "service".equals(jwt.getClaimAsString("token_type"))
				&& actualScopes.containsAll(properties.getRequiredScopes())) {
			return OAuth2TokenValidatorResult.success();
		}
		return OAuth2TokenValidatorResult.failure(
				new OAuth2Error("invalid_token", "Invalid Agent service token", null));
	}
}
