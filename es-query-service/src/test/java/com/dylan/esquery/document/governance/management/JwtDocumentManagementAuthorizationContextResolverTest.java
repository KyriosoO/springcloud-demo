package com.dylan.esquery.document.governance.management;

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
    @Test void requiresAllowlistedServiceAndExactIndexScope(){
        Instant issued=Instant.parse("2026-07-14T08:00:00Z");
        var resolver=new JwtDocumentManagementAuthorizationContextResolver(Set.of("index-release-tooling"));
        var context=resolver.resolve(authentication("index-release-tooling","service",issued,
                "SCOPE_es.document.governance.index.activate"),DocumentManagementOperation.INDEX_ACTIVATE);
        assertThat(context.scopes()).containsExactly(DocumentManagementScope.INDEX_ACTIVATE);
        assertThat(context.authenticationEvidenceDigest()).matches("[0-9a-f]{64}");
        assertThatThrownBy(()->resolver.resolve(authentication("index-release-tooling","user",issued,
                "SCOPE_es.document.governance.index.activate"),DocumentManagementOperation.INDEX_ACTIVATE))
                .isInstanceOf(AccessDeniedException.class);
    }
    private static JwtAuthenticationToken authentication(String subject,String tokenType,Instant issued,String authority){
        Jwt jwt=new Jwt("token",issued,issued.plusSeconds(60),java.util.Map.of("alg","none"),
                java.util.Map.of("sub",subject,"jti","token-1","token_type",tokenType));
        return new JwtAuthenticationToken(jwt,List.of(new SimpleGrantedAuthority(authority)));
    }
}
