package com.dylan.agent.capability.clarify;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

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
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.api.plan.ClarifySpec;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.model.ValidatedClarifyPlan;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.model.MaskType;

@DisplayName("ClarifyPlanValidator")
class ClarifyPlanValidatorTest {

    private ClarifyPlanValidator validator;
    private AgentProperties properties;

    @BeforeEach
    void setUp() {
        properties = testProperties();
        validator = new ClarifyPlanValidator(properties);
    }

    @Nested
    @DisplayName("CLARIFY 正常场景")
    class ClarifySuccess {

        @Test
        @DisplayName("domain 为空可通过")
        void shouldAllowNullDomain() {
            PlanGenerateResponse resp = clarifyResponse(null, "请问你想查询什么？");

            ValidatedClarifyPlan plan = validator.validate(ctx(resp));

            assertThat(plan.intent()).isEqualTo(AgentIntent.CLARIFY);
            assertThat(plan.domain()).isNull();
            assertThat(plan.question()).isEqualTo("请问你想查询什么？");
        }

        @Test
        @DisplayName("domain 非空且存在于配置中可通过")
        void shouldAllowValidDomain() {
            PlanGenerateResponse resp = clarifyResponse("employee", "请提供员工查询条件");

            ValidatedClarifyPlan plan = validator.validate(ctx(resp));

            assertThat(plan.domain()).isEqualTo("employee");
            assertThat(plan.question()).isEqualTo("请提供员工查询条件");
        }

        @Test
        @DisplayName("question 前后空格被 trim")
        void shouldTrimQuestion() {
            PlanGenerateResponse resp = clarifyResponse(null, "  请问你想查询什么？  ");

            ValidatedClarifyPlan plan = validator.validate(ctx(resp));

            assertThat(plan.question()).isEqualTo("请问你想查询什么？");
        }
    }

    @Nested
    @DisplayName("CLARIFY 拒绝场景")
    class ClarifyRejection {

        @Test
        @DisplayName("非 CLARIFY plan 拒绝")
        void shouldRejectNonClarifyPlan() {
            PlanGenerateResponse resp = queryResponse();
            assertThatThrownBy(() -> validator.validate(ctx(resp)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("必须为 CLARIFY");
        }

        @Test
        @DisplayName("缺少 clarify 字段拒绝")
        void shouldRejectMissingClarify() {
            PlanGenerateResponse resp = new PlanGenerateResponse();
            resp.setRequestId("turn-001");
            AgentPlan plan = new AgentPlan();
            plan.setPlanVersion("1.0");
            plan.setIntent(AgentIntent.CLARIFY);
            plan.setClarify(null);
            resp.setPlan(plan);

            assertThatThrownBy(() -> validator.validate(ctx(resp)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("缺少 clarify");
        }

        @Test
        @DisplayName("clarify question 为空拒绝")
        void shouldRejectEmptyQuestion() {
            ClarifySpec clarify = new ClarifySpec();
            clarify.setQuestion("");
            PlanGenerateResponse resp = clarifyResponseWithQuestion(clarify);

            assertThatThrownBy(() -> validator.validate(ctx(resp)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("question");
        }

        @Test
        @DisplayName("clarify question 超过 500 字符拒绝")
        void shouldRejectTooLongQuestion() {
            ClarifySpec clarify = new ClarifySpec();
            clarify.setQuestion("A".repeat(501));
            PlanGenerateResponse resp = clarifyResponseWithQuestion(clarify);

            assertThatThrownBy(() -> validator.validate(ctx(resp)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("question");
        }

        @Test
        @DisplayName("携带 query 字段拒绝")
        void shouldRejectClarifyWithQuery() {
            PlanGenerateResponse resp = new PlanGenerateResponse();
            resp.setRequestId("turn-001");
            AgentPlan plan = new AgentPlan();
            plan.setPlanVersion("1.0");
            plan.setIntent(AgentIntent.CLARIFY);
            ClarifySpec clarify = new ClarifySpec();
            clarify.setQuestion("test");
            plan.setClarify(clarify);
            AgentQuerySpec query = new AgentQuerySpec();
            query.setFilters(List.of());
            plan.setQuery(query);
            resp.setPlan(plan);

            assertThatThrownBy(() -> validator.validate(ctx(resp)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("query");
        }

        @Test
        @DisplayName("携带 aggregate 字段拒绝")
        void shouldRejectClarifyWithAggregate() {
            PlanGenerateResponse resp = clarifyResponse("employee", "test");
            com.dylan.agent.api.plan.AgentAggregateSpec aggregate = new com.dylan.agent.api.plan.AgentAggregateSpec();
            aggregate.setMetrics(List.of());
            resp.getPlan().setAggregate(aggregate);

            assertThatThrownBy(() -> validator.validate(ctx(resp)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("aggregate");
        }

        @Test
        @DisplayName("domain 非空但不存在于配置中拒绝")
        void shouldRejectUnknownDomain() {
            PlanGenerateResponse resp = clarifyResponse("nonexistent", "请问你想查询什么？");

            assertThatThrownBy(() -> validator.validate(ctx(resp)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("domain");
        }
    }

    // --- helpers ---

    private CapabilityValidationContext ctx(PlanGenerateResponse resp) {
        return new CapabilityValidationContext(resp, "turn-001", null,
                new AgentUserContext("user", Set.of("agent:admin")));
    }

    private PlanGenerateResponse clarifyResponse(String domain, String question) {
        ClarifySpec clarify = new ClarifySpec();
        clarify.setQuestion(question);
        return clarifyResponseWithSpec(domain, clarify);
    }

    private PlanGenerateResponse clarifyResponseWithQuestion(ClarifySpec clarify) {
        return clarifyResponseWithSpec(null, clarify);
    }

    private PlanGenerateResponse clarifyResponseWithSpec(String domain, ClarifySpec clarify) {
        PlanGenerateResponse resp = new PlanGenerateResponse();
        resp.setRequestId("turn-001");
        AgentPlan plan = new AgentPlan();
        plan.setPlanVersion("1.0");
        plan.setIntent(AgentIntent.CLARIFY);
        plan.setDomain(domain);
        plan.setClarify(clarify);
        resp.setPlan(plan);
        return resp;
    }

    private PlanGenerateResponse queryResponse() {
        PlanGenerateResponse resp = new PlanGenerateResponse();
        resp.setRequestId("turn-001");
        AgentPlan plan = new AgentPlan();
        plan.setPlanVersion("1.0");
        plan.setIntent(AgentIntent.QUERY);
        plan.setDomain("employee");
        AgentQuerySpec spec = new AgentQuerySpec();
        spec.setFilters(List.of());
        plan.setQuery(spec);
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
        q.setMaxFilters(5); q.setMaxInValues(20); q.setMaxFilterValueLength(256); q.setMaxDownstreamResponseBytes(2097152);
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
        fp.setAliases(List.of());
        fp.setType(AgentFieldType.STRING);
        fp.setOperators(ops);
        fp.setFilterRoles(Set.of("agent:viewer", "agent:admin"));
        fp.setDisplayRoles(Set.of("agent:viewer", "agent:admin"));
        fp.setMask(MaskType.NONE);
        return fp;
    }
}
