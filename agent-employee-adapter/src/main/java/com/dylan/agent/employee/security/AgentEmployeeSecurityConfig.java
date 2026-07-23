package com.dylan.agent.employee.security;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.core.env.Environment;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.OAuth2TokenValidatorResult;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.web.SecurityFilterChain;

import com.dylan.common.security.KidAwareJwtDecoder;
import com.dylan.common.security.PurposeScopedJwtKeyProvider;
import com.dylan.common.security.SecretMaterialProvider;
import com.dylan.common.security.SecretProperties;
import com.dylan.common.security.SecretPropertiesValidator;
import com.dylan.common.security.SecretPurpose;
import com.dylan.agent.employee.config.AgentEmployeeAdapterProperties;

@Configuration
@EnableConfigurationProperties(AgentEmployeeAdapterProperties.class)
public class AgentEmployeeSecurityConfig {

	@Bean("agentEmployeeJwtDecoder")
	JwtDecoder agentEmployeeJwtDecoder(SecretProperties secrets, SecretMaterialProvider materialProvider,
			Environment environment, AgentEmployeeAdapterProperties properties) {
		SecretPropertiesValidator.validateAgentServiceJwt(secrets, environment);
		PurposeScopedJwtKeyProvider provider = new PurposeScopedJwtKeyProvider(
				SecretPurpose.AGENT_SERVICE_JWT, secrets.getAgentServiceJwt(), materialProvider);
		KidAwareJwtDecoder decoder = new KidAwareJwtDecoder(provider);
		decoder.setAllowedTypes(java.util.Set.of("agent-business-delegated+jwt"));
		decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(
				JwtValidators.createDefaultWithIssuer("agent-service"),
				jwt -> jwt.getAudience().contains(properties.getDelegatedAudience())
						&& "agent-service".equals(jwt.getSubject())
						? OAuth2TokenValidatorResult.success()
						: OAuth2TokenValidatorResult.failure(
								new OAuth2Error("invalid_token", "Invalid Employee delegated token", null))));
		return decoder;
	}

	@Bean
	@Order(1)
	SecurityFilterChain agentEmployeeFilterChain(HttpSecurity http,
			@Qualifier("agentEmployeeJwtDecoder") JwtDecoder decoder) throws Exception {
		return http.securityMatcher("/internal/agent/employee/**")
				.csrf(csrf -> csrf.disable())
				.authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
				.oauth2ResourceServer(oauth -> oauth.jwt(jwt -> jwt.decoder(decoder)))
				.build();
	}

	@Bean
	@Order(2)
	SecurityFilterChain denyUnmatchedRequests(HttpSecurity http) throws Exception {
		return http.csrf(csrf -> csrf.disable())
				.authorizeHttpRequests(auth -> auth.anyRequest().denyAll())
				.build();
	}
}
