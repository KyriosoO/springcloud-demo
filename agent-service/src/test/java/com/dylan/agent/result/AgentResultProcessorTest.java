package com.dylan.agent.result;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.mask.AddressFieldMasker;
import com.dylan.agent.mask.EmailFieldMasker;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.mask.IdCardFieldMasker;
import com.dylan.agent.mask.MobileFieldMasker;
import com.dylan.agent.mask.NoneFieldMasker;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.security.AgentPermissionService;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

@DisplayName("AgentResultProcessor")
class AgentResultProcessorTest {

    private AgentResultProcessor processor;
    private AgentUserContext admin;

    @BeforeEach
    void setUp() {
        var permissionService = new AgentPermissionService(
                DomainMetadataTestSupport.agentProperties(),
                DomainMetadataTestSupport.catalogView());
        var maskerRegistry = new FieldMaskerRegistry(List.of(
                new NoneFieldMasker(), new IdCardFieldMasker(),
                new MobileFieldMasker(), new EmailFieldMasker(), new AddressFieldMasker()));
        processor = new AgentResultProcessor(permissionService, maskerRegistry);
        admin = new AgentUserContext("admin", Set.of("agent:admin", "agent:viewer"));
    }

    @Nested
    @DisplayName("过滤与投影")
    class FilterAndProject {

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

            var row = result.getRows().get(0);
            assertThat(row.get("position")).isNull();
        }
    }
}
