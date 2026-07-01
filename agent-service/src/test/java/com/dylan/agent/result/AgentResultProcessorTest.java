package com.dylan.agent.result;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.mask.AddressFieldMasker;
import com.dylan.agent.mask.EmailFieldMasker;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.mask.IdCardFieldMasker;
import com.dylan.agent.mask.MobileFieldMasker;
import com.dylan.agent.mask.NoneFieldMasker;
import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.security.AgentPermissionService;

@DisplayName("AgentResultProcessor")
class AgentResultProcessorTest {

    private AgentResultProcessor processor;
    private AgentUserContext admin;

    @BeforeEach
    void setUp() {
        AgentProperties p = testProperties();
        var permissionService = new AgentPermissionService(p);
        var maskerRegistry = new FieldMaskerRegistry(List.of(
                new NoneFieldMasker(), new IdCardFieldMasker(),
                new MobileFieldMasker(), new EmailFieldMasker(), new AddressFieldMasker()));
        processor = new AgentResultProcessor(permissionService, maskerRegistry);
        admin = new AgentUserContext("admin", Set.of("agent:admin", "agent:viewer"));
    }

    @Nested
    @DisplayName("过滤与脱敏")
    class FilterAndMask {

        @Test
        @DisplayName("保留总数是否精确的标记")
        void shouldPreserveTotalExactFlag() {
            var raw = new AdapterQueryResult(List.of(), 10000, false, 1, 20);
            ValidatedQuery q = new ValidatedQuery(
                    List.of(), List.of("chineseName"), 1, 20);

            var result = processor.process(raw, q, admin, "employee");

            assertThat(result.getTotal()).isEqualTo(10000);
            assertThat(result.isTotalExact()).isFalse();
        }

        @Test
        @DisplayName("只保留 selectFields")
        void shouldKeepOnlySelectFields() {
            var raw = new AdapterQueryResult(List.of(
                    Map.of("chineseName", "张三", "memberNo", "E001", "position", "HRM", "phoneNo", "13812345678")),
                    1, 1, 20);
            ValidatedQuery q = new ValidatedQuery(
                    List.of(), List.of("chineseName", "position"), 1, 20);
            var result = processor.process(raw, q, admin, "employee");
            assertThat(result.getColumns()).containsExactly("chineseName", "position");
            var row = result.getRows().get(0);
            assertThat(row).containsKeys("chineseName", "position");
            assertThat(row).doesNotContainKeys("memberNo", "phoneNo");
        }

        @Test
        @DisplayName("身份证脱敏")
        void shouldMaskIdCard() {
            var raw = new AdapterQueryResult(List.of(
                    Map.of("idCardNo", "110101199001010011", "chineseName", "张三")), 1, 1, 20);
            ValidatedQuery q = new ValidatedQuery(
                    List.of(), List.of("chineseName", "idCardNo"), 1, 20);
            var result = processor.process(raw, q, admin, "employee");
            assertThat(result.getRows().get(0).get("idCardNo")).isEqualTo("110101********0011");
        }

        @Test
        @DisplayName("手机号脱敏")
        void shouldMaskMobile() {
            var raw = new AdapterQueryResult(List.of(
                    Map.of("phoneNo", "13812345678")), 1, 1, 20);
            ValidatedQuery q = new ValidatedQuery(
                    List.of(), List.of("phoneNo"), 1, 20);
            var result = processor.process(raw, q, admin, "employee");
            assertThat(result.getRows().get(0).get("phoneNo")).isEqualTo("138****5678");
        }

        @Test
        @DisplayName("邮箱脱敏")
        void shouldMaskEmail() {
            var raw = new AdapterQueryResult(List.of(
                    Map.of("email", "zhangsan@example.com")), 1, 1, 20);
            ValidatedQuery q = new ValidatedQuery(
                    List.of(), List.of("email"), 1, 20);
            var result = processor.process(raw, q, admin, "employee");
            assertThat(result.getRows().get(0).get("email")).isEqualTo("z***@example.com");
        }

        @Test
        @DisplayName("地址脱敏")
        void shouldMaskAddress() {
            var raw = new AdapterQueryResult(List.of(
                    Map.of("contactAddress", "北京市海淀区中关村大道100号")), 1, 1, 20);
            ValidatedQuery q = new ValidatedQuery(
                    List.of(), List.of("contactAddress"), 1, 20);
            var result = processor.process(raw, q, admin, "employee");
            assertThat(result.getRows().get(0).get("contactAddress")).isEqualTo("北京市海淀区***");
        }

        @Test
        @DisplayName("列顺序稳定")
        void shouldKeepColumnOrder() {
            var raw = new AdapterQueryResult(List.of(
                    Map.of("memberNo", "E001", "chineseName", "张三", "position", "HRM")), 1, 1, 20);
            ValidatedQuery q = new ValidatedQuery(
                    List.of(), List.of("chineseName", "memberNo", "position"), 1, 20);
            var result = processor.process(raw, q, admin, "employee");
            assertThat(result.getColumns()).containsExactly("chineseName", "memberNo", "position");
        }

        @Test
        @DisplayName("对象/数组字段不进入响应")
        void shouldExcludeObjectFields() {
            var raw = new AdapterQueryResult(List.of(
                    Map.of("chineseName", "张三", "position", Map.of("key", "value"))), 1, 1, 20);
            ValidatedQuery q = new ValidatedQuery(
                    List.of(), List.of("chineseName", "position"), 1, 20);
            var result = processor.process(raw, q, admin, "employee");
            // Object fields → null, not the raw map
            var row = result.getRows().get(0);
            assertThat(row.get("position")).isNull();
        }
    }

    private AgentProperties testProperties() {
        AgentProperties p = new AgentProperties();
        p.setIntentRoles(Map.of(
                com.dylan.agent.api.enums.AgentIntent.QUERY, Set.of("agent:viewer", "agent:admin"),
                com.dylan.agent.api.enums.AgentIntent.CLARIFY, Set.of("agent:viewer", "agent:admin")));
        p.setRuntime(rt());
        p.setConversation(conv());
        p.setQuery(qp());

        AgentProperties.DomainProperties emp = new AgentProperties.DomainProperties();
        emp.setAccessRoles(Set.of("agent:viewer", "agent:admin"));
        emp.setDefaultSelectFields(List.of("chineseName", "memberNo", "position"));

        Map<String, AgentProperties.FieldProperties> fields = new java.util.HashMap<>();
        fields.put("chineseName", makeFp(Set.of("agent:viewer", "agent:admin"), Set.of("agent:viewer", "agent:admin"), MaskType.NONE));
        fields.put("memberNo", makeFp(Set.of("agent:viewer", "agent:admin"), Set.of("agent:viewer", "agent:admin"), MaskType.NONE));
        fields.put("position", makeFp(Set.of("agent:viewer", "agent:admin"), Set.of("agent:viewer", "agent:admin"), MaskType.NONE));
        fields.put("contactAddress", makeFp(Set.of("agent:admin"), Set.of("agent:admin"), MaskType.ADDRESS));
        fields.put("idCardNo", makeFp(Set.of("agent:admin"), Set.of("agent:admin"), MaskType.ID_CARD));
        fields.put("phoneNo", makeFp(Set.of("agent:admin"), Set.of("agent:admin"), MaskType.MOBILE));
        fields.put("email", makeFp(Set.of("agent:admin"), Set.of("agent:admin"), MaskType.EMAIL));
        emp.setFields(fields);
        p.setDomains(Map.of("employee", emp));
        return p;
    }

    private AgentProperties.FieldProperties makeFp(Set<String> filterRoles, Set<String> displayRoles, MaskType mask) {
        AgentProperties.FieldProperties fp = new AgentProperties.FieldProperties();
        fp.setAliases(List.of());
        fp.setOperators(Set.of(AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN));
        fp.setFilterRoles(filterRoles);
        fp.setDisplayRoles(displayRoles);
        fp.setMask(mask);
        return fp;
    }

    private AgentProperties.RuntimeProperties rt() {
        var rt = new AgentProperties.RuntimeProperties();
        rt.setBaseUrl("http://localhost:9230"); rt.setSharedKey("test-key-at-least-16");
        rt.setConnectTimeout(java.time.Duration.ofSeconds(2)); rt.setReadTimeout(java.time.Duration.ofSeconds(15));
        return rt;
    }

    private AgentProperties.ConversationProperties conv() {
        var c = new AgentProperties.ConversationProperties();
        c.setRecentTurnLimit(6); c.setRetentionDays(7); c.setCleanupDelay(java.time.Duration.ofHours(1));
        return c;
    }

    private AgentProperties.QueryProperties qp() {
        var q = new AgentProperties.QueryProperties();
        q.setDefaultSize(20); q.setMaxSize(100); q.setMaxResultWindow(10000);
        q.setMaxFilters(5); q.setMaxInValues(20); q.setMaxFilterValueLength(256);
        return q;
    }
}
