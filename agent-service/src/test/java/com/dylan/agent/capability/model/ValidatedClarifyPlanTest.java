package com.dylan.agent.capability.model;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.enums.AgentIntent;

@DisplayName("ValidatedClarifyPlan")
class ValidatedClarifyPlanTest {

    @Test
    @DisplayName("intent 固定为 CLARIFY")
    void shouldReturnClarifyIntent() {
        var plan = new ValidatedClarifyPlan(null, "question");
        assertThat(plan.intent()).isEqualTo(AgentIntent.CLARIFY);
    }

    @Test
    @DisplayName("domain 可为 null")
    void shouldAllowNullDomain() {
        var plan = new ValidatedClarifyPlan(null, "question");
        assertThat(plan.domain()).isNull();
    }

    @Test
    @DisplayName("domain 非空时返回")
    void shouldReturnDomain() {
        var plan = new ValidatedClarifyPlan("employee", "question");
        assertThat(plan.domain()).isEqualTo("employee");
    }

    @Test
    @DisplayName("auditSummary domain 为 null 时返回 CLARIFY")
    void shouldReturnClarifyOnlyWhenDomainNull() {
        var plan = new ValidatedClarifyPlan(null, "question");
        assertThat(plan.auditSummary()).isEqualTo("CLARIFY");
    }

    @Test
    @DisplayName("auditSummary domain 非空时包含 domain")
    void shouldContainDomain() {
        var plan = new ValidatedClarifyPlan("employee", "question");
        assertThat(plan.auditSummary()).isEqualTo("CLARIFY domain=employee");
    }
}
