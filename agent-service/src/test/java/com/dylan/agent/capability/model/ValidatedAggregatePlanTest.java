package com.dylan.agent.capability.model;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AggregateFunction;

@DisplayName("ValidatedAggregatePlan")
class ValidatedAggregatePlanTest {

    private final ValidatedAggregatePlan plan = new ValidatedAggregatePlan("transaction",
            new ValidatedAggregateQuery(List.of(),
                    List.of(new ValidatedAggregateMetric("total", AggregateFunction.COUNT, null)),
                    List.of("transType"), null, 20));

    @Test
    @DisplayName("intent 固定为 AGGREGATE")
    void shouldReturnAggregateIntent() {
        assertThat(plan.intent()).isEqualTo(AgentIntent.AGGREGATE);
    }

    @Test
    @DisplayName("auditSummary 包含 domain 和 metrics/group 计数")
    void shouldContainSummary() {
        assertThat(plan.auditSummary()).contains("AGGREGATE domain=transaction", "metrics=1", "groups=1");
    }
}
