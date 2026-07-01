package com.dylan.agent.capability.model;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;

@DisplayName("ValidatedQueryPlan")
class ValidatedQueryPlanTest {

    @Test
    @DisplayName("intent 固定为 QUERY")
    void shouldReturnQueryIntent() {
        var plan = new ValidatedQueryPlan("employee",
                new ValidatedQuery(List.of(), List.of(), 1, 20));
        assertThat(plan.intent()).isEqualTo(AgentIntent.QUERY);
    }

    @Test
    @DisplayName("auditSummary 包含 domain 和 filter 数量")
    void shouldContainDomainAndFilterCount() {
        var filter = new ValidatedFilter("position", AgentOperator.EQ, "HRM", List.of());
        var plan = new ValidatedQueryPlan("employee",
                new ValidatedQuery(List.of(filter), List.of("chineseName"), 1, 20));
        assertThat(plan.auditSummary()).contains("QUERY domain=employee", "filters=1");
    }
}
