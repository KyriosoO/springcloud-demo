package com.dylan.esquery.document;

import com.dylan.common.security.SecurityTokenUtils;
import org.springframework.http.HttpStatus;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.server.ResponseStatusException;

import java.util.Set;

/** Document 专用检索端点的服务身份和最小 scope gate。 */
public final class DocumentSearchAccessGuard {
    static final String REQUIRED_SERVICE = "agent-service";
    static final String REQUIRED_SCOPE = "document:hybrid-search";

    public void requireAuthorized(Jwt jwt) {
        if (!SecurityTokenUtils.isServiceToken(jwt)
                || !REQUIRED_SERVICE.equals(SecurityTokenUtils.subject(jwt))
                || !scopes(jwt).contains(REQUIRED_SCOPE)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "document search service identity rejected");
        }
    }

    private static Set<String> scopes(Jwt jwt) {
        String scope = jwt == null ? null : jwt.getClaimAsString("scope");
        if (scope == null || scope.isBlank()) return Set.of();
        return Set.of(scope.trim().split("\\s+"));
    }
}
