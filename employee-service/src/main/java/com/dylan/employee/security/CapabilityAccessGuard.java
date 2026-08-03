package com.dylan.employee.security;

import com.dylan.common.security.SecurityTokenUtils;

import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

/** 统一校验 Employee 能力接口的用户身份。 */
@Component
public class CapabilityAccessGuard {
	private static final java.util.Set<String> EMPLOYEE_READ_AUTHORITIES = java.util.Set.of(
			"ROLE_ADMIN", "ROLE_VIEWER");

    public void requireUser(Authentication authentication) {
        Jwt jwt = extractJwt(authentication);
        if (!SecurityTokenUtils.isUserToken(jwt)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Employee capability permission denied");
        }
    }

	public void requireEmployeeRead(Authentication authentication) {
		requireUser(authentication);
		boolean allowed = authentication.getAuthorities().stream()
				.map(GrantedAuthority::getAuthority)
				.anyMatch(EMPLOYEE_READ_AUTHORITIES::contains);
		if (!allowed) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Employee capability permission denied");
		}
	}

    private Jwt extractJwt(Authentication authentication) {
        if (authentication instanceof JwtAuthenticationToken jwtAuthentication) {
            return jwtAuthentication.getToken();
        }
        return authentication != null && authentication.getPrincipal() instanceof Jwt principal
                ? principal : null;
    }
}
