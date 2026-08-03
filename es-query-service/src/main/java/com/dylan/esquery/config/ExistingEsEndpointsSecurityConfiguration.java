package com.dylan.esquery.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;

/** Keeps the pre-existing generic ES endpoint access behavior unchanged. */
@Configuration(proxyBeanMethods = false)
public class ExistingEsEndpointsSecurityConfiguration {

	@Bean
	@Order(2)
	SecurityFilterChain existingEsEndpointsSecurityFilterChain(HttpSecurity http) throws Exception {
		return http.csrf(csrf -> csrf.disable())
				.authorizeHttpRequests(auth -> auth.anyRequest().permitAll())
				.build();
	}
}
