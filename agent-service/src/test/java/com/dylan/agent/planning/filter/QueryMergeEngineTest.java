package com.dylan.agent.planning.filter;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.config.AgentProperties.DomainProperties;
import com.dylan.agent.config.AgentProperties.FieldProperties;
import com.dylan.agent.model.MaskType;

class QueryMergeEngineTest {

    private QueryMergeEngine engine;

    @BeforeEach
    void setUp() {
        engine = new QueryMergeEngine(new FieldConstraintValidator());
    }

    // Helper: create ValidatedFilter
    private ValidatedFilter vf(String field, AgentOperator op, String value, List<String> values) {
        return new ValidatedFilter(field, op, value, values);
    }

    // Helper: create DomainProperties for final query validation (range checks)
    private DomainProperties dpWith(String field, AgentFieldType type) {
        FieldProperties fp = new FieldProperties();
        fp.setType(type);
        if (type == AgentFieldType.DECIMAL) { fp.setDecimalPrecision(50); fp.setDecimalScale(2); }
        if (type == AgentFieldType.INSTANT) { fp.setFormatHint("ISO-8601"); }
        fp.setOperators(Set.of(AgentOperator.values()));
        fp.setFilterRoles(Set.of("agent:viewer"));
        fp.setDisplayRoles(Set.of("agent:viewer"));
        fp.setMask(MaskType.NONE);
        DomainProperties d = new DomainProperties();
        d.setFields(new java.util.LinkedHashMap<>(java.util.Map.of(field, fp)));
        return d;
    }

    // --- 状态转换表 (18 cases) ---

    @Test
    void emptyToAtomic() {
        List<ValidatedFilter> result = engine.merge(
                List.of(),
                List.of(vf("name", AgentOperator.EQ, "张三", null)),
                Set.of());
        assertThat(result).hasSize(1);
        assertThat(result.get(0).getOperator()).isEqualTo(AgentOperator.EQ);
        assertThat(result.get(0).getValue()).isEqualTo("张三");
    }

    @Test
    void emptyToLower() {
        List<ValidatedFilter> result = engine.merge(
                List.of(),
                List.of(vf("amount", AgentOperator.GT, "100", null)),
                Set.of());
        assertThat(result).hasSize(1);
        assertThat(result.get(0).getOperator()).isEqualTo(AgentOperator.GT);
    }

    @Test
    void emptyToUpper() {
        List<ValidatedFilter> result = engine.merge(
                List.of(),
                List.of(vf("amount", AgentOperator.LT, "1000", null)),
                Set.of());
        assertThat(result).hasSize(1);
        assertThat(result.get(0).getOperator()).isEqualTo(AgentOperator.LT);
    }

    @Test
    void emptyToBoundedRange() {
        List<ValidatedFilter> result = engine.merge(
                List.of(),
                List.of(
                        vf("amount", AgentOperator.GT, "100", null),
                        vf("amount", AgentOperator.LT, "1000", null)),
                Set.of());
        assertThat(result).hasSize(2);
        assertThat(result.get(0).getOperator()).isEqualTo(AgentOperator.GT);
        assertThat(result.get(1).getOperator()).isEqualTo(AgentOperator.LT);
    }

    @Test
    void atomicToAtomic() {
        List<ValidatedFilter> result = engine.merge(
                List.of(vf("name", AgentOperator.EQ, "张三", null)),
                List.of(vf("name", AgentOperator.EQ, "李四", null)),
                Set.of());
        assertThat(result).hasSize(1);
        assertThat(result.get(0).getValue()).isEqualTo("李四");
    }

    @Test
    void atomicToLower() {
        List<ValidatedFilter> result = engine.merge(
                List.of(vf("amount", AgentOperator.EQ, "500", null)),
                List.of(vf("amount", AgentOperator.GT, "100", null)),
                Set.of());
        assertThat(result).hasSize(1);
        assertThat(result.get(0).getOperator()).isEqualTo(AgentOperator.GT);
    }

    @Test
    void atomicToUpper() {
        List<ValidatedFilter> result = engine.merge(
                List.of(vf("amount", AgentOperator.EQ, "500", null)),
                List.of(vf("amount", AgentOperator.LT, "1000", null)),
                Set.of());
        assertThat(result).hasSize(1);
        assertThat(result.get(0).getOperator()).isEqualTo(AgentOperator.LT);
    }

    @Test
    void atomicToBoundedRange() {
        List<ValidatedFilter> result = engine.merge(
                List.of(vf("amount", AgentOperator.EQ, "500", null)),
                List.of(
                        vf("amount", AgentOperator.GT, "100", null),
                        vf("amount", AgentOperator.LT, "1000", null)),
                Set.of());
        assertThat(result).hasSize(2);
        assertThat(result.get(0).getOperator()).isEqualTo(AgentOperator.GT);
        assertThat(result.get(1).getOperator()).isEqualTo(AgentOperator.LT);
    }

    @Test
    void rangeToAtomic() {
        List<ValidatedFilter> result = engine.merge(
                List.of(
                        vf("amount", AgentOperator.GT, "100", null),
                        vf("amount", AgentOperator.LT, "1000", null)),
                List.of(vf("amount", AgentOperator.EQ, "500", null)),
                Set.of());
        assertThat(result).hasSize(1);
        assertThat(result.get(0).getOperator()).isEqualTo(AgentOperator.EQ);
        assertThat(result.get(0).getValue()).isEqualTo("500");
    }

    @Test
    void lowerToLower() {
        List<ValidatedFilter> result = engine.merge(
                List.of(vf("amount", AgentOperator.GT, "100", null)),
                List.of(vf("amount", AgentOperator.GT, "200", null)),
                Set.of());
        assertThat(result).hasSize(1);
        assertThat(result.get(0).getValue()).isEqualTo("200");
    }

    @Test
    void upperToUpper() {
        List<ValidatedFilter> result = engine.merge(
                List.of(vf("amount", AgentOperator.LT, "1000", null)),
                List.of(vf("amount", AgentOperator.LT, "2000", null)),
                Set.of());
        assertThat(result).hasSize(1);
        assertThat(result.get(0).getValue()).isEqualTo("2000");
    }

    @Test
    void lowerToUpper() {
        List<ValidatedFilter> result = engine.merge(
                List.of(vf("amount", AgentOperator.GT, "100", null)),
                List.of(vf("amount", AgentOperator.LT, "1000", null)),
                Set.of());
        assertThat(result).hasSize(2);
        assertThat(result.get(0).getOperator()).isEqualTo(AgentOperator.GT);
        assertThat(result.get(1).getOperator()).isEqualTo(AgentOperator.LT);
    }

    @Test
    void upperToLower() {
        List<ValidatedFilter> result = engine.merge(
                List.of(vf("amount", AgentOperator.LT, "1000", null)),
                List.of(vf("amount", AgentOperator.GT, "100", null)),
                Set.of());
        assertThat(result).hasSize(2);
        assertThat(result.get(0).getOperator()).isEqualTo(AgentOperator.GT);
        assertThat(result.get(1).getOperator()).isEqualTo(AgentOperator.LT);
    }

    @Test
    void boundedToLower() {
        List<ValidatedFilter> result = engine.merge(
                List.of(
                        vf("amount", AgentOperator.GT, "100", null),
                        vf("amount", AgentOperator.LT, "1000", null)),
                List.of(vf("amount", AgentOperator.GT, "200", null)),
                Set.of());
        assertThat(result).hasSize(2);
        assertThat(result.get(0).getValue()).isEqualTo("200"); // 新 lower
        assertThat(result.get(1).getValue()).isEqualTo("1000"); // 旧 upper 保留
    }

    @Test
    void boundedToUpper() {
        List<ValidatedFilter> result = engine.merge(
                List.of(
                        vf("amount", AgentOperator.GT, "100", null),
                        vf("amount", AgentOperator.LT, "1000", null)),
                List.of(vf("amount", AgentOperator.LT, "2000", null)),
                Set.of());
        assertThat(result).hasSize(2);
        assertThat(result.get(0).getValue()).isEqualTo("100"); // 旧 lower 保留
        assertThat(result.get(1).getValue()).isEqualTo("2000"); // 新 upper
    }

    @Test
    void boundedToBounded() {
        List<ValidatedFilter> result = engine.merge(
                List.of(
                        vf("amount", AgentOperator.GT, "100", null),
                        vf("amount", AgentOperator.LT, "1000", null)),
                List.of(
                        vf("amount", AgentOperator.GT, "200", null),
                        vf("amount", AgentOperator.LT, "2000", null)),
                Set.of());
        assertThat(result).hasSize(2);
        assertThat(result.get(0).getValue()).isEqualTo("200");
        assertThat(result.get(1).getValue()).isEqualTo("2000");
    }

    @Test
    void removeField() {
        List<ValidatedFilter> result = engine.merge(
                List.of(
                        vf("name", AgentOperator.EQ, "张三", null),
                        vf("amount", AgentOperator.GT, "100", null)),
                List.of(),
                Set.of("amount"));
        assertThat(result).hasSize(1);
        assertThat(result.get(0).getField()).isEqualTo("name");
    }

    // --- 顺序测试 ---

    @Test
    void shouldPreserveFieldOrderOnUpdate() {
        List<ValidatedFilter> result = engine.merge(
                List.of(
                        vf("name", AgentOperator.EQ, "张三", null),
                        vf("amount", AgentOperator.GT, "100", null)),
                List.of(vf("name", AgentOperator.EQ, "李四", null)),
                Set.of());
        assertThat(result).hasSize(2);
        assertThat(result.get(0).getField()).isEqualTo("name");
        assertThat(result.get(1).getField()).isEqualTo("amount");
        assertThat(result.get(0).getValue()).isEqualTo("李四");
    }

    @Test
    void shouldAppendNewField() {
        List<ValidatedFilter> result = engine.merge(
                List.of(vf("name", AgentOperator.EQ, "张三", null)),
                List.of(vf("amount", AgentOperator.GT, "100", null)),
                Set.of());
        assertThat(result).hasSize(2);
        assertThat(result.get(0).getField()).isEqualTo("name");
        assertThat(result.get(1).getField()).isEqualTo("amount");
    }

    @Test
    void shouldPreserveOrderAfterRemove() {
        List<ValidatedFilter> result = engine.merge(
                List.of(
                        vf("name", AgentOperator.EQ, "张三", null),
                        vf("amount", AgentOperator.GT, "100", null),
                        vf("type", AgentOperator.EQ, "PAY", null)),
                List.of(),
                Set.of("amount"));
        assertThat(result).hasSize(2);
        assertThat(result.get(0).getField()).isEqualTo("name");
        assertThat(result.get(1).getField()).isEqualTo("type");
    }

    @Test
    void shouldOutputLowerThenUpper() {
        List<ValidatedFilter> result = engine.merge(
                List.of(),
                List.of(
                        vf("amount", AgentOperator.LT, "1000", null),
                        vf("amount", AgentOperator.GT, "100", null)),
                Set.of());
        assertThat(result).hasSize(2);
        assertThat(result.get(0).getOperator()).isEqualTo(AgentOperator.GT);
        assertThat(result.get(1).getOperator()).isEqualTo(AgentOperator.LT);
    }

    @Test
    void shouldBeDeterministic() {
        var prev = List.of(vf("name", AgentOperator.EQ, "张三", null));
        var chg = List.of(vf("amount", AgentOperator.GT, "100", null));
        List<ValidatedFilter> r1 = engine.merge(prev, chg, Set.of());
        List<ValidatedFilter> r2 = engine.merge(prev, chg, Set.of());
        assertThat(r1).hasSize(r2.size());
        for (int i = 0; i < r1.size(); i++) {
            assertThat(r1.get(i).getField()).isEqualTo(r2.get(i).getField());
            assertThat(r1.get(i).getOperator()).isEqualTo(r2.get(i).getOperator());
            assertThat(r1.get(i).getValue()).isEqualTo(r2.get(i).getValue());
        }
    }
}
