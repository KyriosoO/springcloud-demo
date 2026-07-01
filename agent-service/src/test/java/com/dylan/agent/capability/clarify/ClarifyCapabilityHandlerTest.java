package com.dylan.agent.capability.clarify;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.plan.ClarifySpec;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.capability.CapabilityExecutionContext;
import com.dylan.agent.capability.CapabilityExecutionResult;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.model.ValidatedClarifyPlan;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

@DisplayName("ClarifyCapabilityHandler")
class ClarifyCapabilityHandlerTest {

    private ClarifyCapabilityHandler handler;
    private AgentUserContext user;

    @BeforeEach
    void setUp() {
        var validator = new ClarifyPlanValidator(DomainMetadataTestSupport.catalogView());
        handler = new ClarifyCapabilityHandler(validator);
        user = new AgentUserContext("user", Set.of("agent:admin"));
    }

    @Nested
    @DisplayName("validate")
    class Validate {

        @Test
        @DisplayName("返回 ValidatedClarifyPlan")
        void shouldReturnValidatedClarifyPlan() {
            var resp = clarifyResponse(null, "请问你想查询什么？");
            var ctx = new CapabilityValidationContext(resp, "turn-001", null, user);

            ValidatedClarifyPlan plan = handler.validate(ctx);

            assertThat(plan.intent()).isEqualTo(AgentIntent.CLARIFY);
            assertThat(plan.question()).isEqualTo("请问你想查询什么？");
        }
    }

    @Nested
    @DisplayName("execute")
    class Execute {

        @Test
        @DisplayName("返回 CapabilityExecutionResult.clarify")
        void shouldReturnClarifyResult() {
            var plan = new ValidatedClarifyPlan(null, "请提供查询条件");
            var execCtx = new CapabilityExecutionContext("conv-1", "turn-001", "测试", user, null);

            CapabilityExecutionResult result = handler.execute(execCtx, plan);

            assertThat(result.intent()).isEqualTo(AgentIntent.CLARIFY);
            assertThat(result.assistantMessage()).isEqualTo("请提供查询条件");
            assertThat(result.queryParameters()).isNull();
            assertThat(result.queryResult()).isNull();
            assertThat(result.contextToPersist()).isNull();
        }
    }

    // --- helpers ---

    private PlanGenerateResponse clarifyResponse(String domain, String question) {
        PlanGenerateResponse resp = new PlanGenerateResponse();
        resp.setRequestId("turn-001");
        AgentPlan plan = new AgentPlan();
        plan.setPlanVersion("1.0");
        plan.setIntent(AgentIntent.CLARIFY);
        plan.setDomain(domain);
        ClarifySpec clarify = new ClarifySpec();
        clarify.setQuestion(question);
        plan.setClarify(clarify);
        resp.setPlan(plan);
        return resp;
    }

}
