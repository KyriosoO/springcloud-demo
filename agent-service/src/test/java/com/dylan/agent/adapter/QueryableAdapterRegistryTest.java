package com.dylan.agent.adapter;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;

@DisplayName("QueryableAdapterRegistry")
class QueryableAdapterRegistryTest {

    @Nested
    @DisplayName("正常注册和查询")
    class ValidRegistration {

        @Test
        @DisplayName("已注册 domain 可获取")
        void shouldResolveEmployeeAdapter() {
            var adapter = new TestAdapter("employee");
            var registry = new QueryableAdapterRegistry(List.of(adapter));
            assertThat(registry.getRequired("employee")).isSameAs(adapter);
        }
    }

    @Nested
    @DisplayName("拒绝场景")
    class RejectionScenarios {

        @Test
        @DisplayName("未知 domain 拒绝")
        void shouldRejectUnknownDomain() {
            var registry = new QueryableAdapterRegistry(List.of(new TestAdapter("employee")));
            assertThatThrownBy(() -> registry.getRequired("transaction"))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("transaction");
        }

        @Test
        @DisplayName("重复 domain 构造失败")
        void shouldRejectDuplicateDomain() {
            var adapters = java.util.Arrays.<QueryableAdapter>asList(new TestAdapter("employee"), new TestAdapter("employee"));
            assertThatThrownBy(() -> new QueryableAdapterRegistry(adapters))
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("Duplicate");
        }
    }

    public static class TestAdapter implements QueryableAdapter {
        private final String domain;
        TestAdapter(String domain) { this.domain = domain; }
        @Override public String domain() { return domain; }
        @Override public java.util.Set<String> supportedFields() { return java.util.Set.of("test"); }
        @Override public AdapterQueryResult query(ValidatedQuery query) {
            return new AdapterQueryResult(List.of(), 0, 1, 20);
        }
    }
}
