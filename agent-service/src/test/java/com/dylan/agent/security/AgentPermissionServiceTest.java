package com.dylan.agent.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.exception.AgentPermissionDeniedException;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

@DisplayName("AgentPermissionService")
class AgentPermissionServiceTest {

    private AgentPermissionService service;
    private AgentUserContext admin;
    private AgentUserContext viewer;

    @BeforeEach
    void setUp() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        service = new AgentPermissionService(properties, DomainMetadataTestSupport.catalogView());
        admin = new AgentUserContext("admin", Set.of("agent:admin", "agent:viewer"));
        viewer = new AgentUserContext("viewer", Set.of("agent:viewer"));
    }

    @Nested
    @DisplayName("Agent 访问权限")
    class AgentAccess {

        @Test
        @DisplayName("有 agent 角色的用户通过")
        void shouldAllowAgentRole() {
            assertThatCode(() -> service.requireAgentAccess(admin)).doesNotThrowAnyException();
            assertThatCode(() -> service.requireAgentAccess(viewer)).doesNotThrowAnyException();
        }

        @Test
        @DisplayName("无 agent 角色的用户拒绝")
        void shouldRejectNoAgentRole() {
            AgentUserContext noRole = new AgentUserContext("guest", Set.of());
            assertThatThrownBy(() -> service.requireAgentAccess(noRole))
                    .isInstanceOf(AgentPermissionDeniedException.class);
        }
    }

    @Nested
    @DisplayName("查询字段与 operator")
    class QueryFieldPermission {

        @Test
        @DisplayName("已登记字段与 operator 通过")
        void shouldAllowKnownFieldAndOperator() {
            ValidatedQuery q = buildQuery("position", AgentOperator.EQ);
            assertThatCode(() -> service.checkQuery(viewer, "employee", q)).doesNotThrowAnyException();
        }

        @Test
        @DisplayName("未登记字段拒绝")
        void shouldRejectUnknownField() {
            ValidatedQuery q = buildQuery("salary", AgentOperator.EQ);
            assertThatThrownBy(() -> service.checkQuery(admin, "employee", q))
                    .isInstanceOf(AgentPermissionDeniedException.class)
                    .hasMessageContaining("salary");
        }

        @Test
        @DisplayName("字段不支持的 operator 拒绝")
        void shouldRejectUnsupportedOperator() {
            ValidatedQuery q = buildQuery("position", AgentOperator.GT);
            assertThatThrownBy(() -> service.checkQuery(admin, "employee", q))
                    .isInstanceOf(AgentPermissionDeniedException.class)
                    .hasMessageContaining("GT");
        }
    }

    @Nested
    @DisplayName("展示策略")
    class DisplayPolicy {

        @Test
        @DisplayName("展示策略来自 D04 Catalog 字段定义")
        void shouldReturnDisplayPolicyFromCatalog() {
            var policy = service.getDisplayPolicy(admin, "employee", "position");

            assertThat(policy.getField()).isEqualTo("position");
            assertThat(policy.getOperators()).contains(AgentOperator.EQ);
            assertThat(policy.getDisplayRoles()).contains("agent:admin", "agent:viewer");
        }
    }

    @Nested
    @DisplayName("Intent 权限")
    class IntentPermission {

        @Test
        @DisplayName("admin 允许 QUERY")
        void shouldAllowAdminQuery() {
            assertThatCode(() -> service.checkIntent(admin, AgentIntent.QUERY)).doesNotThrowAnyException();
        }

        @Test
        @DisplayName("admin 允许 CLARIFY")
        void shouldAllowAdminClarify() {
            assertThatCode(() -> service.checkIntent(admin, AgentIntent.CLARIFY)).doesNotThrowAnyException();
        }
    }

    private ValidatedQuery buildQuery(String field, AgentOperator op) {
        ValidatedFilter f;
        if (op == AgentOperator.IN) {
            f = new ValidatedFilter(field, op, null, List.of("test"));
        } else {
            f = new ValidatedFilter(field, op, "test", List.of());
        }
        return new ValidatedQuery(List.of(f), List.of("chineseName"), 1, 20);
    }
}
