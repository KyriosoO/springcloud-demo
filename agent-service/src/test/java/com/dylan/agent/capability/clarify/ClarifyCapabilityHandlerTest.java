package com.dylan.agent.capability.clarify;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.plan.ClarifySpec;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.capability.CapabilityExecutionContext;
import com.dylan.agent.capability.CapabilityExecutionResult;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.model.ValidatedClarifyPlan;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.model.MaskType;

@DisplayName("ClarifyCapabilityHandler")
class ClarifyCapabilityHandlerTest {

    private ClarifyCapabilityHandler handler;
    private AgentUserContext user;

    @BeforeEach
    void setUp() {
        var properties = testProperties();
        var validator = new ClarifyPlanValidator(properties);
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

    private AgentProperties testProperties() {
        AgentProperties p = new AgentProperties();
        p.setIntentRoles(Map.of(
                AgentIntent.QUERY, Set.of("agent:viewer", "agent:admin"),
                AgentIntent.CLARIFY, Set.of("agent:viewer", "agent:admin")));

        AgentProperties.RuntimeProperties rt = new AgentProperties.RuntimeProperties();
        rt.setBaseUrl("http://localhost:9230");
        rt.setSharedKey("test-key-at-least-16");
        rt.setConnectTimeout(java.time.Duration.ofSeconds(2));
        rt.setReadTimeout(java.time.Duration.ofSeconds(15));
        p.setRuntime(rt);

        AgentProperties.ConversationProperties c = new AgentProperties.ConversationProperties();
        c.setRecentTurnLimit(6); c.setRetentionDays(7); c.setCleanupDelay(java.time.Duration.ofHours(1));
        p.setConversation(c);

        AgentProperties.QueryProperties q = new AgentProperties.QueryProperties();
        q.setDefaultSize(20); q.setMaxSize(100); q.setMaxResultWindow(10000);
        q.setMaxFilters(5); q.setMaxInValues(20); q.setMaxFilterValueLength(256);
        q.setMaxDownstreamResponseBytes(2097152);
        p.setQuery(q);

        AgentProperties.DomainProperties emp = new AgentProperties.DomainProperties();
        emp.setAliases(List.of("员工", "employee"));
        emp.setAccessRoles(Set.of("agent:viewer", "agent:admin"));
        emp.setDefaultSelectFields(List.of("chineseName", "memberNo", "position"));
        java.util.Map<String, AgentProperties.FieldProperties> fields = new java.util.HashMap<>();
        fields.put("chineseName", makeFp(Set.of(AgentOperator.EQ)));
        emp.setFields(fields);
        p.setDomains(Map.of("employee", emp));
        return p;
    }

    private AgentProperties.FieldProperties makeFp(Set<AgentOperator> ops) {
        AgentProperties.FieldProperties fp = new AgentProperties.FieldProperties();
        fp.setAliases(List.of()); fp.setType(AgentFieldType.STRING);
        fp.setOperators(ops);
        fp.setFilterRoles(Set.of("agent:viewer", "agent:admin"));
        fp.setDisplayRoles(Set.of("agent:viewer", "agent:admin"));
        fp.setMask(MaskType.NONE);
        return fp;
    }
}
