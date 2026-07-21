package com.dylan.agent.planning.filter;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

import org.junit.jupiter.api.Test;

import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;

class OperatorSemanticsTest {

    @Test
    void shouldHaveProfileForEveryOperator() {
        assertThat(AgentOperator.values())
                .allSatisfy(op -> assertThatCode(
                        () -> OperatorSemantics.profileOf(op))
                        .doesNotThrowAnyException());
    }

    @Test
    void shouldClassifyExactFamily() {
        assertThat(OperatorSemantics.profileOf(AgentOperator.EQ).family())
                .isEqualTo(OperatorSemantics.OperatorFamily.EXACT);
        assertThat(OperatorSemantics.profileOf(AgentOperator.IN).family())
                .isEqualTo(OperatorSemantics.OperatorFamily.EXACT);
    }

    @Test
    void shouldClassifyTextFamily() {
        assertThat(OperatorSemantics.profileOf(AgentOperator.CONTAINS).family())
                .isEqualTo(OperatorSemantics.OperatorFamily.TEXT);
        assertThat(OperatorSemantics.profileOf(AgentOperator.CONTAINS_ANY).family())
                .isEqualTo(OperatorSemantics.OperatorFamily.TEXT);
        assertThat(OperatorSemantics.profileOf(AgentOperator.STARTS_WITH).family())
                .isEqualTo(OperatorSemantics.OperatorFamily.TEXT);
        assertThat(OperatorSemantics.profileOf(AgentOperator.STARTS_WITH_ANY).family())
                .isEqualTo(OperatorSemantics.OperatorFamily.TEXT);
    }

    @Test
    void shouldClassifyRangeFamily() {
        assertThat(OperatorSemantics.profileOf(AgentOperator.GT).family())
                .isEqualTo(OperatorSemantics.OperatorFamily.RANGE);
        assertThat(OperatorSemantics.profileOf(AgentOperator.LT).family())
                .isEqualTo(OperatorSemantics.OperatorFamily.RANGE);
    }

    @Test
    void shouldAssignAtomicSlotToNonRangeOperators() {
        assertThat(OperatorSemantics.profileOf(AgentOperator.EQ).slot())
                .isEqualTo(OperatorSemantics.FilterSlot.ATOMIC);
        assertThat(OperatorSemantics.profileOf(AgentOperator.IN).slot())
                .isEqualTo(OperatorSemantics.FilterSlot.ATOMIC);
        assertThat(OperatorSemantics.profileOf(AgentOperator.CONTAINS).slot())
                .isEqualTo(OperatorSemantics.FilterSlot.ATOMIC);
        assertThat(OperatorSemantics.profileOf(AgentOperator.CONTAINS_ANY).slot())
                .isEqualTo(OperatorSemantics.FilterSlot.ATOMIC);
        assertThat(OperatorSemantics.profileOf(AgentOperator.STARTS_WITH).slot())
                .isEqualTo(OperatorSemantics.FilterSlot.ATOMIC);
        assertThat(OperatorSemantics.profileOf(AgentOperator.STARTS_WITH_ANY).slot())
                .isEqualTo(OperatorSemantics.FilterSlot.ATOMIC);
    }

    @Test
    void shouldAssignBoundSlotsToRangeOperators() {
        assertThat(OperatorSemantics.profileOf(AgentOperator.GT).slot())
                .isEqualTo(OperatorSemantics.FilterSlot.LOWER_BOUND);
        assertThat(OperatorSemantics.profileOf(AgentOperator.LT).slot())
                .isEqualTo(OperatorSemantics.FilterSlot.UPPER_BOUND);
    }

    @Test
    void shouldAssignSingleValueShape() {
        assertThat(OperatorSemantics.profileOf(AgentOperator.EQ).valueShape())
                .isEqualTo(OperatorSemantics.ValueShape.SINGLE);
        assertThat(OperatorSemantics.profileOf(AgentOperator.CONTAINS).valueShape())
                .isEqualTo(OperatorSemantics.ValueShape.SINGLE);
        assertThat(OperatorSemantics.profileOf(AgentOperator.STARTS_WITH).valueShape())
                .isEqualTo(OperatorSemantics.ValueShape.SINGLE);
        assertThat(OperatorSemantics.profileOf(AgentOperator.GT).valueShape())
                .isEqualTo(OperatorSemantics.ValueShape.SINGLE);
        assertThat(OperatorSemantics.profileOf(AgentOperator.LT).valueShape())
                .isEqualTo(OperatorSemantics.ValueShape.SINGLE);
    }

    @Test
    void shouldAssignMultiValueShape() {
        assertThat(OperatorSemantics.profileOf(AgentOperator.IN).valueShape())
                .isEqualTo(OperatorSemantics.ValueShape.MULTI);
        assertThat(OperatorSemantics.profileOf(AgentOperator.CONTAINS_ANY).valueShape())
                .isEqualTo(OperatorSemantics.ValueShape.MULTI);
        assertThat(OperatorSemantics.profileOf(AgentOperator.STARTS_WITH_ANY).valueShape())
                .isEqualTo(OperatorSemantics.ValueShape.MULTI);
    }

    @Test
    void shouldRejectStringWithGt() {
        assertThat(OperatorSemantics.supports(AgentOperator.GT, AgentFieldType.STRING))
                .isFalse();
    }

    @Test
    void shouldRejectStringWithLt() {
        assertThat(OperatorSemantics.supports(AgentOperator.LT, AgentFieldType.STRING))
                .isFalse();
    }

    @Test
    void shouldRejectDecimalWithContains() {
        assertThat(OperatorSemantics.supports(AgentOperator.CONTAINS, AgentFieldType.DECIMAL))
                .isFalse();
    }

    @Test
    void shouldRejectDecimalWithStartsWith() {
        assertThat(OperatorSemantics.supports(AgentOperator.STARTS_WITH, AgentFieldType.DECIMAL))
                .isFalse();
    }

    @Test
    void shouldRejectInstantWithContains() {
        assertThat(OperatorSemantics.supports(AgentOperator.CONTAINS, AgentFieldType.INSTANT))
                .isFalse();
    }

    @Test
    void shouldRejectInstantWithStartsWith() {
        assertThat(OperatorSemantics.supports(AgentOperator.STARTS_WITH, AgentFieldType.INSTANT))
                .isFalse();
    }

    @Test
    void shouldAllowDecimalWithEqInGtLt() {
        assertThat(OperatorSemantics.supports(AgentOperator.EQ, AgentFieldType.DECIMAL)).isTrue();
        assertThat(OperatorSemantics.supports(AgentOperator.IN, AgentFieldType.DECIMAL)).isTrue();
        assertThat(OperatorSemantics.supports(AgentOperator.GT, AgentFieldType.DECIMAL)).isTrue();
        assertThat(OperatorSemantics.supports(AgentOperator.LT, AgentFieldType.DECIMAL)).isTrue();
    }

    @Test
    void shouldAllowInstantWithEqInGtLt() {
        assertThat(OperatorSemantics.supports(AgentOperator.EQ, AgentFieldType.INSTANT)).isTrue();
        assertThat(OperatorSemantics.supports(AgentOperator.IN, AgentFieldType.INSTANT)).isTrue();
        assertThat(OperatorSemantics.supports(AgentOperator.GT, AgentFieldType.INSTANT)).isTrue();
        assertThat(OperatorSemantics.supports(AgentOperator.LT, AgentFieldType.INSTANT)).isTrue();
    }

    @Test
    void shouldAllowStringWithTextOperators() {
        assertThat(OperatorSemantics.supports(AgentOperator.EQ, AgentFieldType.STRING)).isTrue();
        assertThat(OperatorSemantics.supports(AgentOperator.IN, AgentFieldType.STRING)).isTrue();
        assertThat(OperatorSemantics.supports(AgentOperator.CONTAINS, AgentFieldType.STRING)).isTrue();
        assertThat(OperatorSemantics.supports(AgentOperator.CONTAINS_ANY, AgentFieldType.STRING)).isTrue();
        assertThat(OperatorSemantics.supports(AgentOperator.STARTS_WITH, AgentFieldType.STRING)).isTrue();
        assertThat(OperatorSemantics.supports(AgentOperator.STARTS_WITH_ANY, AgentFieldType.STRING)).isTrue();
    }
}
