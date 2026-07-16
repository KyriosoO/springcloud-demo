package com.dylan.employee.security;

import com.dylan.common.security.SecurityTokenUtils;

import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

/** 统一校验 Employee 能力接口的用户身份或 Agent 服务身份。 */
@Component
public class CapabilityAccessGuard {

    private static final String AGENT_SERVICE = "agent-service";

    public void requireUserOrAgentScope(Authentication authentication, String requiredScope) {
        Jwt jwt = extractJwt(authentication);
        if (!SecurityTokenUtils.isUserOrAuthorizedService(jwt, AGENT_SERVICE, requiredScope)) {
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
