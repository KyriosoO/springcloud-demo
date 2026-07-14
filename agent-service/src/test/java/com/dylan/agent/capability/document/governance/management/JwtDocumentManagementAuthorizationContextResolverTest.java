package com.dylan.agent.capability.document.governance.management;

import org.junit.jupiter.api.Test;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import java.time.Instant;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class JwtDocumentManagementAuthorizationContextResolverTest {
    @Test
    void resolvesOnlyAllowlistedServiceWithExactOperationScope() {
        Instant issuedAt=Instant.parse("2026-07-14T08:00:00Z");
        var resolver=new JwtDocumentManagementAuthorizationContextResolver(Set.of("agent-release-tooling"));
        var authentication=authentication("agent-release-tooling","service",issuedAt,
                "SCOPE_agent.document.governance.emergency-evidence.issue");

        var context=resolver.resolve(authentication,DocumentManagementOperation.EMERGENCY_EVIDENCE_ISSUE);

        assertThat(context.serviceSubject()).isEqualTo("agent-release-tooling");
        assertThat(context.scopes()).containsExactly(DocumentManagementScope.EMERGENCY_EVIDENCE_ISSUE);
        assertThat(context.authenticationEvidenceDigest()).matches("[0-9a-f]{64}");
    }

    @Test
    void rejectsUserTokenAndWrongServiceSubject() {
        Instant issuedAt=Instant.parse("2026-07-14T08:00:00Z");
        var resolver=new JwtDocumentManagementAuthorizationContextResolver(Set.of("agent-release-tooling"));
        assertThatThrownBy(()->resolver.resolve(authentication("agent-release-tooling","user",issuedAt,
                "SCOPE_agent.document.governance.emergency-evidence.issue"),DocumentManagementOperation.EMERGENCY_EVIDENCE_ISSUE))
                .isInstanceOf(AccessDeniedException.class);
        assertThatThrownBy(()->resolver.resolve(authentication("other-service","service",issuedAt,
                "SCOPE_agent.document.governance.emergency-evidence.issue"),DocumentManagementOperation.EMERGENCY_EVIDENCE_ISSUE))
                .isInstanceOf(AccessDeniedException.class);
    }

    private static JwtAuthenticationToken authentication(String subject,String tokenType,Instant issuedAt,String authority){
        Jwt jwt=new Jwt("token",issuedAt,issuedAt.plusSeconds(60),
                java.util.Map.of("alg","none"),java.util.Map.of("sub",subject,"jti","token-1","token_type",tokenType));
        return new JwtAuthenticationToken(jwt,List.of(new SimpleGrantedAuthority(authority)));
    }
}
