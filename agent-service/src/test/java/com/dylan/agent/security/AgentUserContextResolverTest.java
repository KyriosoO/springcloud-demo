package com.dylan.agent.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.Jwt;

import com.dylan.agent.model.AgentUserContext;

@DisplayName("AgentUserContextResolver")
class AgentUserContextResolverTest {

    private AgentUserContextResolver resolver;

    @BeforeEach
    void setUp() {
        resolver = new AgentUserContextResolver();
    }

    @Nested
    @DisplayName("正常解析")
    class SuccessfulResolution {

        @Test
        @DisplayName("role claim 为 List 时可解析")
        void shouldResolveRoleAsList() {
            Jwt jwt = jwtWithRoles("admin", java.util.List.of("agent:admin", "agent:viewer"));
            AgentUserContext ctx = resolver.resolve(jwt);
            assertThat(ctx.getUserId()).isEqualTo("admin");
            assertThat(ctx.getRoles()).containsExactlyInAnyOrder("agent:admin", "agent:viewer");
        }

        @Test
        @DisplayName("role claim 为数组时可解析")
        void shouldResolveRoleAsArray() {
            Jwt jwt = jwtWithRoles("dylan", new String[] { "agent:admin", "agent:viewer" });
            AgentUserContext ctx = resolver.resolve(jwt);
            assertThat(ctx.getRoles()).containsExactlyInAnyOrder("agent:admin", "agent:viewer");
        }

        @Test
        @DisplayName("role claim 为单字符串时可解析")
        void shouldResolveRoleAsString() {
            Jwt jwt = jwtWithRoles("viewer_t", "agent:viewer");
            AgentUserContext ctx = resolver.resolve(jwt);
            assertThat(ctx.getRoles()).containsExactly("agent:viewer");
        }
    }

    @Nested
    @DisplayName("拒绝场景")
    class RejectionScenarios {

        @Test
        @DisplayName("null JWT 拒绝")
        void shouldRejectNullJwt() {
            assertThatThrownBy(() -> resolver.resolve(null))
                    .isInstanceOf(SecurityException.class)
                    .hasMessageContaining("Missing JWT");
        }

        @Test
        @DisplayName("缺少 subject 拒绝")
        void shouldRejectMissingSubject() {
            Jwt jwt = Jwt.withTokenValue("token")
                    .header("alg", "HS256")
                    .claim("role", java.util.List.of("agent:viewer"))
                    .build();
            assertThatThrownBy(() -> resolver.resolve(jwt))
                    .isInstanceOf(SecurityException.class)
                    .hasMessageContaining("subject");
        }

        @Test
        @DisplayName("缺失 Agent role 时返回空 roles")
        void shouldReturnEmptyRolesWhenMissing() {
            Jwt jwt = jwtWithRoles("test-user", null);
            AgentUserContext ctx = resolver.resolve(jwt);
            assertThat(ctx.getRoles()).isEmpty();
        }
    }

    private Jwt jwtWithRoles(String subject, Object roleClaim) {
        Jwt.Builder builder = Jwt.withTokenValue("token")
                .header("alg", "HS256")
                .subject(subject);
        if (roleClaim != null) {
            builder.claim("role", roleClaim);
        }
        return builder.build();
    }
}
