package com.dylan.agent.capability;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.exception.AgentPlanValidationException;

@DisplayName("CapabilityRouteResolver")
class CapabilityRouteResolverTest {

    private final CapabilityRouteResolver resolver = new CapabilityRouteResolver();

    @Test
    @DisplayName("null response 拒绝")
    void shouldRejectNullResponse() {
        assertThatThrownBy(() -> resolver.resolve(null, "req-1"))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("Plan 为空");
    }

    @Test
    @DisplayName("null plan 拒绝")
    void shouldRejectNullPlan() {
        PlanGenerateResponse resp = new PlanGenerateResponse();
        resp.setRequestId("req-1");
        resp.setPlan(null);

        assertThatThrownBy(() -> resolver.resolve(resp, "req-1"))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("Plan 为空");
    }

    @Test
    @DisplayName("requestId 不匹配时拒绝")
    void shouldRejectRequestIdMismatch() {
        PlanGenerateResponse resp = new PlanGenerateResponse();
        resp.setRequestId("req-1");
        AgentPlan plan = new AgentPlan();
        plan.setIntent(AgentIntent.QUERY);
        plan.setPlanVersion("1.0");
        resp.setPlan(plan);

        assertThatThrownBy(() -> resolver.resolve(resp, "req-2"))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("requestId 不匹配");
    }

    @Test
    @DisplayName("planVersion 非 1.0 拒绝")
    void shouldRejectInvalidPlanVersion() {
        PlanGenerateResponse resp = new PlanGenerateResponse();
        resp.setRequestId("req-1");
        AgentPlan plan = new AgentPlan();
        plan.setIntent(AgentIntent.QUERY);
        plan.setPlanVersion("2.0");
        resp.setPlan(plan);

        assertThatThrownBy(() -> resolver.resolve(resp, "req-1"))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("planVersion");
    }

    @Test
    @DisplayName("null intent 拒绝")
    void shouldRejectNullIntent() {
        PlanGenerateResponse resp = new PlanGenerateResponse();
        resp.setRequestId("req-1");
        AgentPlan plan = new AgentPlan();
        plan.setIntent(null);
        plan.setPlanVersion("1.0");
        resp.setPlan(plan);

        assertThatThrownBy(() -> resolver.resolve(resp, "req-1"))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("intent 为空");
    }

    @Test
    @DisplayName("QUERY intent 返回 QUERY")
    void shouldReturnQuery() {
        PlanGenerateResponse resp = new PlanGenerateResponse();
        resp.setRequestId("req-1");
        AgentPlan plan = new AgentPlan();
        plan.setIntent(AgentIntent.QUERY);
        plan.setPlanVersion("1.0");
        resp.setPlan(plan);

        AgentIntent intent = resolver.resolve(resp, "req-1");
        assertThat(intent).isEqualTo(AgentIntent.QUERY);
    }

    @Test
    @DisplayName("CLARIFY intent 返回 CLARIFY")
    void shouldReturnClarify() {
        PlanGenerateResponse resp = new PlanGenerateResponse();
        resp.setRequestId("req-1");
        AgentPlan plan = new AgentPlan();
        plan.setIntent(AgentIntent.CLARIFY);
        plan.setPlanVersion("1.0");
        resp.setPlan(plan);

        AgentIntent intent = resolver.resolve(resp, "req-1");
        assertThat(intent).isEqualTo(AgentIntent.CLARIFY);
    }
}
