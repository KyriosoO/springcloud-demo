package com.dylan.agent.adapter;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.AdapterAggregateResult;
import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.exception.AgentPlanValidationException;

@DisplayName("AggregatableAdapterRegistry")
class AggregatableAdapterRegistryTest {

    @Test
    @DisplayName("正常注册成功")
    void shouldRegisterSuccessfully() {
        var adapter = new TestAdapter("employee");
        var registry = new AggregatableAdapterRegistry(List.of(adapter));
        assertThat(registry.domains()).containsExactly("employee");
    }

    @Test
    @DisplayName("重复 domain 拒绝")
    void shouldRejectDuplicateDomains() {
        var a1 = new TestAdapter("employee");
        var a2 = new TestAdapter("employee");
        assertThatThrownBy(() -> new AggregatableAdapterRegistry(List.of(a1, a2)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Duplicate");
    }

    @Test
    @DisplayName("空 domain 拒绝")
    void shouldRejectBlankDomain() {
        var adapter = new TestAdapter("");
        assertThatThrownBy(() -> new AggregatableAdapterRegistry(List.of(adapter)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("blank");
    }

    @Test
    @DisplayName("空 supportedAggregateFields 拒绝")
    void shouldRejectEmptySupportedFields() {
        var adapter = new TestAdapter("employee", Set.of());
        assertThatThrownBy(() -> new AggregatableAdapterRegistry(List.of(adapter)))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    @DisplayName("getRequired 未注册 domain 拒绝")
    void shouldRejectUnknownDomain() {
        var registry = new AggregatableAdapterRegistry(List.of(new TestAdapter("employee")));
        assertThatThrownBy(() -> registry.getRequired("nonexistent"))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("不支持的聚合 domain");
    }

    static class TestAdapter implements AggregatableAdapter {
        private final String domain;
        private final Set<String> fields;

        TestAdapter(String domain) { this(domain, Set.of("amount")); }
        TestAdapter(String domain, Set<String> fields) { this.domain = domain; this.fields = fields; }
        @Override public String domain() { return domain; }
        @Override public Set<String> supportedAggregateFields() { return fields; }
        @Override public Set<AggregateFunction> supportedFunctions(String field) { return Set.of(AggregateFunction.COUNT); }
        @Override public AdapterAggregateResult aggregate(ValidatedAggregateQuery query) { return null; }
    }
}
