package com.dylan.common.security;

import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.web.SecurityFilterChain;

@AutoConfiguration(after = JwtConfig.class)
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
@ConditionalOnClass({ HttpSecurity.class, JwtDecoder.class })
public class ResourceServerSecurityAutoConfiguration {

	@Bean
	@ConditionalOnMissingBean(SecurityFilterChain.class)
	SecurityFilterChain resourceServerSecurityFilterChain(HttpSecurity http) throws Exception {
		return JwtResourceServerHttpSecurity.applyDefaults(http)
				.authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
				.build();
	}
}
