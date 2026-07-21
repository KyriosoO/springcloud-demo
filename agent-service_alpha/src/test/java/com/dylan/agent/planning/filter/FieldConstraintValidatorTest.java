package com.dylan.agent.planning.filter;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

class FieldConstraintValidatorTest {

    private FieldConstraintValidator validator;
    private Map<String, ExecutionFieldRule> dp;

    @BeforeEach
    void setUp() {
        validator = new FieldConstraintValidator();
        dp = DomainMetadataTestSupport.executionFieldRules("employee", AdapterRole.QUERYABLE);
    }

    // --- groupByField success ---

    @Test
    void shouldAllowSingleAtomic() {
        var set = validator.groupByField(List.of(
                vf("chineseName", AgentOperator.EQ, "test", null)));
        assertThat(set.get("chineseName").hasAtomic()).isTrue();
    }

    @Test
    void shouldAllowGtAlone() {
        var set = validator.groupByField(List.of(
                vf("amount", AgentOperator.GT, "100", null)));
        assertThat(set.get("amount").lowerBound()).isNotNull();
    }

    @Test
    void shouldAllowLtAlone() {
        var set = validator.groupByField(List.of(
                vf("amount", AgentOperator.LT, "1000", null)));
        assertThat(set.get("amount").upperBound()).isNotNull();
    }

    @Test
    void shouldAllowGtAndLt() {
        var set = validator.groupByField(List.of(
                vf("amount", AgentOperator.GT, "100", null),
                vf("amount", AgentOperator.LT, "1000", null)));
        FieldFilterSet fs = set.get("amount");
        assertThat(fs.lowerBound()).isNotNull();
        assertThat(fs.upperBound()).isNotNull();
    }

    @Test
    void shouldAllowValidDecimalRange() {
        validator.validateFinalQuery(List.of(
                vf("amount", AgentOperator.GT, "100", null),
                vf("amount", AgentOperator.LT, "1000", null)), dp);
    }

    @Test
    void shouldAllowValidInstantRange() {
        validator.validateFinalQuery(List.of(
                vf("transDate", AgentOperator.GT, "2026-01-01T00:00:00Z", null),
                vf("transDate", AgentOperator.LT, "2026-12-31T00:00:00Z", null)), dp);
    }

    @Test
    void shouldNotConflictDifferentFields() {
        var set = validator.groupByField(List.of(
                vf("chineseName", AgentOperator.EQ, "test", null),
                vf("amount", AgentOperator.GT, "100", null)));
        assertThat(set).hasSize(2);
    }

    @Test
    void shouldAllowChangesWithoutRemoveOverlap() {
        assertThatCode(() -> validator.validateChanges(
                List.of(vf("amount", AgentOperator.EQ, "100", null)),
                Set.of("chineseName")))
                .doesNotThrowAnyException();
    }

    // --- groupByField / validateFinalQuery rejection ---

    @Test
    void shouldRejectEqAndIn() {
        assertThatThrownBy(() -> validator.groupByField(List.of(
                vf("chineseName", AgentOperator.EQ, "test", null),
                vf("chineseName", AgentOperator.IN, null, List.of("a", "b")))))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("多个普通条件");
    }

    @Test
    void shouldRejectEqAndContains() {
        assertThatThrownBy(() -> validator.groupByField(List.of(
                vf("chineseName", AgentOperator.EQ, "test", null),
                vf("chineseName", AgentOperator.CONTAINS, "ab", null))))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("多个普通条件");
    }

    @Test
    void shouldRejectContainsAndStartsWith() {
        assertThatThrownBy(() -> validator.groupByField(List.of(
                vf("chineseName", AgentOperator.CONTAINS, "test", null),
                vf("chineseName", AgentOperator.STARTS_WITH, "ab", null))))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("多个普通条件");
    }

    @Test
    void shouldRejectContainsAnyAndStartsWithAny() {
        assertThatThrownBy(() -> validator.groupByField(List.of(
                vf("chineseName", AgentOperator.CONTAINS_ANY, null, List.of("a", "b")),
                vf("chineseName", AgentOperator.STARTS_WITH_ANY, null, List.of("c", "d")))))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("多个普通条件");
    }

    @Test
    void shouldRejectAtomicAndGt() {
        assertThatThrownBy(() -> validator.groupByField(List.of(
                vf("amount", AgentOperator.EQ, "500", null),
                vf("amount", AgentOperator.GT, "100", null))))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("GT/LT");
    }

    @Test
    void shouldRejectAtomicAndLt() {
        assertThatThrownBy(() -> validator.groupByField(List.of(
                vf("amount", AgentOperator.EQ, "500", null),
                vf("amount", AgentOperator.LT, "1000", null))))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("GT/LT");
    }

    @Test
    void shouldRejectDuplicateGt() {
        assertThatThrownBy(() -> validator.groupByField(List.of(
                vf("amount", AgentOperator.GT, "100", null),
                vf("amount", AgentOperator.GT, "200", null))))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("重复的 GT 下界");
    }

    @Test
    void shouldRejectDuplicateLt() {
        assertThatThrownBy(() -> validator.groupByField(List.of(
                vf("amount", AgentOperator.LT, "1000", null),
                vf("amount", AgentOperator.LT, "2000", null))))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("重复的 LT 上界");
    }

    @Test
    void shouldRejectLowerGreaterThanUpper() {
        assertThatThrownBy(() -> validator.validateFinalQuery(List.of(
                vf("amount", AgentOperator.GT, "1000", null),
                vf("amount", AgentOperator.LT, "100", null)), dp))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("范围无效");
    }

    @Test
    void shouldRejectLowerEqualToUpper() {
        assertThatThrownBy(() -> validator.validateFinalQuery(List.of(
                vf("amount", AgentOperator.GT, "100", null),
                vf("amount", AgentOperator.LT, "100", null)), dp))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("范围无效");
    }

    @Test
    void shouldRejectEmptyFinalFilters() {
        assertThatThrownBy(() -> validator.validateFinalQuery(List.of(), dp))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("不能为空");
    }

    @Test
    void shouldRejectChangeAndRemoveOverlap() {
        assertThatThrownBy(() -> validator.validateChanges(
                List.of(vf("amount", AgentOperator.EQ, "100", null)),
                Set.of("amount")))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("不能同时出现");
    }

    // --- helpers ---

    private ValidatedFilter vf(String field, AgentOperator op, String value, List<String> values) {
        return new ValidatedFilter(field, op, value, values);
    }

}
