package com.dylan.common.security;

import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;

public final class JwtResourceServerHttpSecurity {

	private JwtResourceServerHttpSecurity() {
	}

	public static HttpSecurity applyDefaults(HttpSecurity http) throws Exception {
		return http.csrf(csrf -> csrf.disable())
				.oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()));
	}
}
