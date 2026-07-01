package com.dylan.agent.security;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.exception.AgentPermissionDeniedException;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;

@DisplayName("AgentPermissionService")
class AgentPermissionServiceTest {

    private AgentProperties properties;
    private AgentPermissionService service;
    private AgentUserContext admin;
    private AgentUserContext viewer;

    @BeforeEach
    void setUp() {
        properties = testProperties();
        service = new AgentPermissionService(properties);
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
    @DisplayName("查询字段权限")
    class QueryFieldPermission {

        @Test
        @DisplayName("viewer 查询 position 成功")
        void shouldAllowViewerQueryPosition() {
            ValidatedQuery q = buildQuery("position", AgentOperator.EQ);
            assertThatCode(() -> service.checkQuery(viewer, "employee", q)).doesNotThrowAnyException();
        }

        @Test
        @DisplayName("viewer 查询 idCardNo 拒绝")
        void shouldRejectViewerQueryIdCard() {
            ValidatedQuery q = buildQuery("idCardNo", AgentOperator.EQ);
            assertThatThrownBy(() -> service.checkQuery(viewer, "employee", q))
                    .isInstanceOf(AgentPermissionDeniedException.class)
                    .hasMessageContaining("idCardNo");
        }

        @Test
        @DisplayName("admin 查询 idCardNo 成功")
        void shouldAllowAdminQueryIdCard() {
            ValidatedQuery q = buildQuery("idCardNo", AgentOperator.EQ);
            assertThatCode(() -> service.checkQuery(admin, "employee", q)).doesNotThrowAnyException();
        }

        @Test
        @DisplayName("未声明字段拒绝")
        void shouldRejectUnknownField() {
            ValidatedQuery q = buildQuery("salary", AgentOperator.EQ);
            assertThatThrownBy(() -> service.checkQuery(admin, "employee", q))
                    .isInstanceOf(AgentPermissionDeniedException.class);
        }
    }

    @Nested
    @DisplayName("Operator 权限")
    class OperatorPermission {

        @Test
        @DisplayName("viewer 使用 EQ 通过")
        void shouldAllowEqForViewer() {
            ValidatedQuery q = buildQuery("position", AgentOperator.EQ);
            assertThatCode(() -> service.checkQuery(viewer, "employee", q)).doesNotThrowAnyException();
        }

        @Test
        @DisplayName("viewer 使用 IN 通过")
        void shouldAllowInForViewer() {
            var filter = new ValidatedFilter("memberNo", AgentOperator.IN, null, java.util.List.of("E001"));
            var q = new ValidatedQuery(java.util.List.of(filter), java.util.List.of("chineseName"), 1, 20);
            assertThatCode(() -> service.checkQuery(viewer, "employee", q)).doesNotThrowAnyException();
        }
    }

    @Nested
    @DisplayName("展示字段权限")
    class DisplayPermission {

        @Test
        @DisplayName("admin 可展示 phoneNo")
        void shouldAllowAdminDisplayPhone() {
            ValidatedQuery q = buildQuerySelect("position", AgentOperator.EQ, java.util.List.of("chineseName", "phoneNo", "email"));
            assertThatCode(() -> service.checkQuery(admin, "employee", q)).doesNotThrowAnyException();
        }

        @Test
        @DisplayName("viewer 展示 phoneNo 拒绝")
        void shouldRejectViewerDisplayPhone() {
            ValidatedQuery q = buildQuerySelect("position", AgentOperator.EQ, java.util.List.of("chineseName", "phoneNo"));
            assertThatThrownBy(() -> service.checkQuery(viewer, "employee", q))
                    .isInstanceOf(AgentPermissionDeniedException.class)
                    .hasMessageContaining("phoneNo");
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
        return buildQuerySelect(field, op, java.util.List.of("chineseName"));
    }

    private ValidatedQuery buildQuerySelect(String field, AgentOperator op, java.util.List<String> selectFields) {
        ValidatedFilter f;
        if (op == AgentOperator.IN) {
            f = new ValidatedFilter(field, op, null, java.util.List.of("test"));
        } else {
            f = new ValidatedFilter(field, op, "test", java.util.List.of());
        }
        return new ValidatedQuery(java.util.List.of(f), selectFields, 1, 20);
    }

    private AgentProperties testProperties() {
        AgentProperties p = new AgentProperties();
        p.setIntentRoles(Map.of(
                AgentIntent.QUERY, Set.of("agent:viewer", "agent:admin"),
                AgentIntent.CLARIFY, Set.of("agent:viewer", "agent:admin")));

        AgentProperties.RuntimeProperties rt = new AgentProperties.RuntimeProperties();
        rt.setBaseUrl("http://localhost:9230"); rt.setSharedKey("test-key-at-least-16");
        rt.setConnectTimeout(java.time.Duration.ofSeconds(2)); rt.setReadTimeout(java.time.Duration.ofSeconds(15));
        p.setRuntime(rt);

        AgentProperties.ConversationProperties c = new AgentProperties.ConversationProperties();
        c.setRecentTurnLimit(6); c.setRetentionDays(7); c.setCleanupDelay(java.time.Duration.ofHours(1));
        p.setConversation(c);

        AgentProperties.QueryProperties q = new AgentProperties.QueryProperties();
        q.setDefaultSize(20); q.setMaxSize(100); q.setMaxResultWindow(10000);
        q.setMaxFilters(5); q.setMaxInValues(20); q.setMaxFilterValueLength(256);
        p.setQuery(q);

        AgentProperties.DomainProperties emp = new AgentProperties.DomainProperties();
        emp.setAccessRoles(Set.of("agent:viewer", "agent:admin"));
        emp.setDefaultSelectFields(java.util.List.of("chineseName", "memberNo", "position"));
        Map<String, AgentProperties.FieldProperties> fields = new java.util.HashMap<>();
        // viewer-accessible
        fields.put("chineseName", makeFp(Set.of("agent:viewer", "agent:admin"), Set.of("agent:viewer", "agent:admin")));
        fields.put("memberNo", makeFp(Set.of("agent:viewer", "agent:admin"), Set.of("agent:viewer", "agent:admin")));
        fields.put("position", makeFp(Set.of("agent:viewer", "agent:admin"), Set.of("agent:viewer", "agent:admin")));
        // admin-only
        fields.put("contactAddress", makeFp(Set.of("agent:admin"), Set.of("agent:admin")));
        fields.put("idCardNo", makeFp(Set.of("agent:admin"), Set.of("agent:admin")));
        fields.put("phoneNo", makeFp(Set.of("agent:admin"), Set.of("agent:admin")));
        fields.put("email", makeFp(Set.of("agent:admin"), Set.of("agent:admin")));
        emp.setFields(fields);
        p.setDomains(Map.of("employee", emp));
        return p;
    }

    private AgentProperties.FieldProperties makeFp(Set<String> filterRoles, Set<String> displayRoles) {
        AgentProperties.FieldProperties fp = new AgentProperties.FieldProperties();
        fp.setAliases(java.util.List.of());
        fp.setOperators(Set.of(AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN));
        fp.setFilterRoles(filterRoles);
        fp.setDisplayRoles(displayRoles);
        fp.setMask(MaskType.NONE);
        return fp;
    }
}
