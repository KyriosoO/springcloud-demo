package com.dylan.common.security;

import java.util.ArrayList;
import java.util.List;

import org.springframework.core.convert.converter.Converter;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

/**
 * Strictly converts the user JWT role claim into the finite application
 * authorities shared by Agent-facing provider endpoints.
 */
public final class UserRoleJwtAuthenticationConverter
		implements Converter<Jwt, AbstractAuthenticationToken> {

	public static final String ROLE_CLAIM = "role";
	public static final String ROLE_ADMIN = "ADMIN";
	public static final String ROLE_VIEWER = "VIEWER";
	public static final String AUTHORITY_ADMIN = "ROLE_ADMIN";
	public static final String AUTHORITY_VIEWER = "ROLE_VIEWER";

	@Override
	public AbstractAuthenticationToken convert(Jwt jwt) {
		if (!SecurityTokenUtils.isUserToken(jwt)) {
			throw new OAuth2AuthenticationException(
					new OAuth2Error("invalid_token"),
					"A verified user token is required");
		}

		return new JwtAuthenticationToken(jwt, authorities(jwt));
	}

	private static List<GrantedAuthority> authorities(Jwt jwt) {
		Object claim = jwt.getClaims().get(ROLE_CLAIM);
		if (!(claim instanceof List<?> roles) || roles.isEmpty()) {
			return List.of();
		}

		boolean admin = false;
		boolean viewer = false;
		for (Object value : roles) {
			if (!(value instanceof String role)) {
				return List.of();
			}
			if (ROLE_ADMIN.equals(role)) {
				admin = true;
			} else if (ROLE_VIEWER.equals(role)) {
				viewer = true;
			} else {
				return List.of();
			}
		}

		List<GrantedAuthority> result = new ArrayList<>(2);
		if (admin) {
			result.add(new SimpleGrantedAuthority(AUTHORITY_ADMIN));
		}
		if (viewer) {
			result.add(new SimpleGrantedAuthority(AUTHORITY_VIEWER));
		}
		return List.copyOf(result);
	}
}
