package com.dylan.agent.capability.aggregate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.AggregatableAdapterRegistry;
import com.dylan.agent.adapter.api.AdapterAggregateResult;
import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.plan.AgentAggregateSpec;
import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.plan.AggregateMetricSpec;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.model.ValidatedAggregatePlan;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;

@DisplayName("AggregatePlanValidator")
class AggregatePlanValidatorTest {

    private AggregatePlanValidator validator;
    private AgentProperties properties;

    @BeforeEach
    void setUp() {
        properties = testProperties();
        var normalizer = new FilterNormalizer(properties);
        var constraints = new FieldConstraintValidator();
        var registry = new AggregatableAdapterRegistry(List.of(new TestAggregateAdapter()));
        validator = new AggregatePlanValidator(properties, normalizer, constraints, registry);
    }

    @Nested
    @DisplayName("正常场景")
    class Success {

        @Test
        @DisplayName("AGGREGATE plan 正常通过")
        void shouldValidateAggregatePlan() {
            var resp = aggregateResponse("transaction", AggregateFunction.COUNT, null);
            var ctx = new CapabilityValidationContext(resp, "turn-001", null, admin());

            ValidatedAggregatePlan plan = validator.validate(ctx);

            assertThat(plan.intent()).isEqualTo(AgentIntent.AGGREGATE);
            assertThat(plan.domain()).isEqualTo("transaction");
            assertThat(plan.aggregate().getMetrics()).hasSize(1);
        }

        @Test
        @DisplayName("COUNT 无 field 通过")
        void shouldAllowCountWithoutField() {
            var resp = aggregateResponse("transaction", AggregateFunction.COUNT, null);
            var ctx = new CapabilityValidationContext(resp, "turn-001", null, admin());

            var plan = validator.validate(ctx);

            assertThat(plan.aggregate().getMetrics().get(0).getFunction())
                    .isEqualTo(AggregateFunction.COUNT);
        }
    }

    @Nested
    @DisplayName("拒绝场景")
    class Rejection {

        @Test
        @DisplayName("非 AGGREGATE plan 拒绝")
        void shouldRejectNonAggregatePlan() {
            var resp = new PlanGenerateResponse();
            resp.setRequestId("turn-001");
            var plan = new AgentPlan();
            plan.setPlanVersion("1.0");
            plan.setIntent(AgentIntent.QUERY);
            plan.setDomain("transaction");
            resp.setPlan(plan);

            var ctx = new CapabilityValidationContext(resp, "turn-001", null, admin());
            assertThatThrownBy(() -> validator.validate(ctx))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("AGGREGATE");
        }

        @Test
        @DisplayName("缺少 aggregate 字段拒绝")
        void shouldRejectMissingAggregate() {
            var resp = new PlanGenerateResponse();
            resp.setRequestId("turn-001");
            var plan = new AgentPlan();
            plan.setPlanVersion("1.0");
            plan.setIntent(AgentIntent.AGGREGATE);
            plan.setDomain("transaction");
            plan.setAggregate(null);
            resp.setPlan(plan);

            var ctx = new CapabilityValidationContext(resp, "turn-001", null, admin());
            assertThatThrownBy(() -> validator.validate(ctx))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("aggregate");
        }

        @Test
        @DisplayName("同时携带 query 拒绝")
        void shouldRejectAggregateWithQuery() {
            var resp = aggregateResponse("transaction", AggregateFunction.COUNT, null);
            var querySpec = new com.dylan.agent.api.plan.AgentQuerySpec();
            querySpec.setFilters(List.of());
            resp.getPlan().setQuery(querySpec);

            var ctx = new CapabilityValidationContext(resp, "turn-001", null, admin());
            assertThatThrownBy(() -> validator.validate(ctx))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("query");
        }

        @Test
        @DisplayName("unknown domain 拒绝")
        void shouldRejectUnknownDomain() {
            var resp = aggregateResponse("nonexistent", AggregateFunction.COUNT, null);
            var ctx = new CapabilityValidationContext(resp, "turn-001", null, admin());
            assertThatThrownBy(() -> validator.validate(ctx))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("domain");
        }

        @Test
        @DisplayName("unknown groupBy field 拒绝")
        void shouldRejectUnknownGroupBy() {
            var resp = aggregateResponse("transaction", AggregateFunction.COUNT, null);
            resp.getPlan().getAggregate().setGroupByFields(List.of("unknownField"));

            var ctx = new CapabilityValidationContext(resp, "turn-001", null, admin());
            assertThatThrownBy(() -> validator.validate(ctx))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("groupBy");
        }

        @Test
        @DisplayName("SUM 非 DECIMAL 拒绝")
        void shouldRejectSumOnNonDecimal() {
            var resp = aggregateResponse("transaction", AggregateFunction.SUM, "transId");
            var ctx = new CapabilityValidationContext(resp, "turn-001", null, admin());
            assertThatThrownBy(() -> validator.validate(ctx))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("DECIMAL");
        }

        @Test
        @DisplayName("maxRows 超限拒绝")
        void shouldRejectMaxRowsExceedsMax() {
            var resp = aggregateResponse("transaction", AggregateFunction.COUNT, null);
            resp.getPlan().getAggregate().setMaxRows(200);

            var ctx = new CapabilityValidationContext(resp, "turn-001", null, admin());
            assertThatThrownBy(() -> validator.validate(ctx))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("maxRows");
        }

        @Test
        @DisplayName("metrics 为空拒绝")
        void shouldRejectEmptyMetrics() {
            var resp = aggregateResponse("transaction", AggregateFunction.COUNT, null);
            resp.getPlan().getAggregate().setMetrics(List.of());

            var ctx = new CapabilityValidationContext(resp, "turn-001", null, admin());
            assertThatThrownBy(() -> validator.validate(ctx))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("metric");
        }

        @Test
        @DisplayName("metric alias 重复拒绝")
        void shouldRejectDuplicateAlias() {
            var resp = new PlanGenerateResponse();
            resp.setRequestId("turn-001");
            var plan = new AgentPlan();
            plan.setPlanVersion("1.0");
            plan.setIntent(AgentIntent.AGGREGATE);
            plan.setDomain("transaction");
            var spec = new AgentAggregateSpec();
            var m1 = new AggregateMetricSpec();
            m1.setAlias("sameName"); m1.setFunction(AggregateFunction.COUNT);
            var m2 = new AggregateMetricSpec();
            m2.setAlias("sameName"); m2.setFunction(AggregateFunction.SUM);
            m2.setField("amount");
            spec.setMetrics(List.of(m1, m2));
            plan.setAggregate(spec);
            resp.setPlan(plan);

            var ctx = new CapabilityValidationContext(resp, "turn-001", null, admin());
            assertThatThrownBy(() -> validator.validate(ctx))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("alias");
        }

        @Test
        @DisplayName("Adapter 不支持的 groupBy 字段拒绝")
        void shouldRejectAdapterUnsupportedGroupBy() {
            var resp = aggregateResponse("transaction", AggregateFunction.COUNT, null);
            resp.getPlan().getAggregate().setGroupByFields(List.of("transId"));

            var ctx = new CapabilityValidationContext(resp, "turn-001", null, admin());
            assertThatThrownBy(() -> validator.validate(ctx))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("Adapter")
                    .hasMessageContaining("groupBy");
        }

        @Test
        @DisplayName("Adapter 不支持的 metric function 拒绝")
        void shouldRejectAdapterUnsupportedMetricFunction() {
            var resp = aggregateResponse("transaction", AggregateFunction.MIN, "transDate");

            var ctx = new CapabilityValidationContext(resp, "turn-001", null, admin());
            assertThatThrownBy(() -> validator.validate(ctx))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("Adapter")
                    .hasMessageContaining("MIN");
        }
    }

    // --- helpers ---

    private AgentUserContext admin() {
        return new AgentUserContext("admin", Set.of("agent:admin"));
    }

    private PlanGenerateResponse aggregateResponse(String domain, AggregateFunction func, String field) {
        var resp = new PlanGenerateResponse();
        resp.setRequestId("turn-001");
        var plan = new AgentPlan();
        plan.setPlanVersion("1.0");
        plan.setIntent(AgentIntent.AGGREGATE);
        plan.setDomain(domain);
        var spec = new AgentAggregateSpec();
        var metric = new AggregateMetricSpec();
        metric.setAlias("m1");
        metric.setFunction(func);
        metric.setField(field);
        spec.setMetrics(List.of(metric));
        plan.setAggregate(spec);
        resp.setPlan(plan);
        return resp;
    }

    private AgentProperties testProperties() {
        AgentProperties p = new AgentProperties();
        p.setIntentRoles(Map.of(
                AgentIntent.QUERY, Set.of("agent:admin"),
                AgentIntent.CLARIFY, Set.of("agent:admin"),
                AgentIntent.AGGREGATE, Set.of("agent:admin")));

        AgentProperties.RuntimeProperties rt = new AgentProperties.RuntimeProperties();
        rt.setBaseUrl("http://localhost"); rt.setSharedKey("test-key-at-least-16");
        rt.setConnectTimeout(java.time.Duration.ofSeconds(2)); rt.setReadTimeout(java.time.Duration.ofSeconds(15));
        rt.setMaxResponseBytes(65536);
        p.setRuntime(rt);

        AgentProperties.ConversationProperties c = new AgentProperties.ConversationProperties();
        c.setRecentTurnLimit(6); c.setRetentionDays(7); c.setCleanupDelay(java.time.Duration.ofHours(1));
        p.setConversation(c);

        AgentProperties.QueryProperties q = new AgentProperties.QueryProperties();
        q.setDefaultSize(20); q.setMaxSize(100); q.setMaxResultWindow(10000);
        q.setMaxFilters(5); q.setMaxInValues(20); q.setMaxFilterValueLength(256); q.setMaxDownstreamResponseBytes(2097152);
        p.setQuery(q);

        var agg = new AgentProperties.AggregateProperties();
        agg.setMaxMetrics(5);
        agg.setMaxGroupFields(2);
        agg.setDefaultMaxRows(20);
        agg.setMaxMaxRows(100);
        p.setAggregate(agg);

        var tx = new AgentProperties.DomainProperties();
        tx.setAliases(List.of("交易"));
        tx.setAccessRoles(Set.of("agent:admin"));
        tx.setDefaultSelectFields(List.of("transId", "amount"));
        Map<String, AgentProperties.FieldProperties> fields = new java.util.HashMap<>();
        fields.put("transId", fp(AgentFieldType.STRING, Set.of(AgentOperator.EQ)));
        fields.put("amount", fp(AgentFieldType.DECIMAL, Set.of(AgentOperator.EQ, AgentOperator.GT, AgentOperator.LT)));
        fields.get("amount").setDecimalPrecision(50);
        fields.get("amount").setDecimalScale(2);
        fields.put("transType", fp(AgentFieldType.STRING, Set.of(AgentOperator.EQ, AgentOperator.CONTAINS)));
        fields.put("transDate", fp(AgentFieldType.INSTANT, Set.of(AgentOperator.GT, AgentOperator.LT)));
        tx.setFields(fields);
        p.setDomains(Map.of("transaction", tx));
        return p;
    }

    private AgentProperties.FieldProperties fp(AgentFieldType type, Set<AgentOperator> ops) {
        var fp = new AgentProperties.FieldProperties();
        fp.setAliases(List.of()); fp.setType(type); fp.setOperators(ops);
        fp.setFilterRoles(Set.of("agent:admin")); fp.setDisplayRoles(Set.of("agent:admin"));
        fp.setMask(MaskType.NONE);
        return fp;
    }

    static class TestAggregateAdapter implements AggregatableAdapter {
        @Override public String domain() { return "transaction"; }
        @Override public Set<String> supportedAggregateFields() { return Set.of("transType", "amount", "transDate"); }
        @Override public Set<AggregateFunction> supportedFunctions(String field) {
            if ("amount".equals(field)) {
                return Set.of(AggregateFunction.SUM, AggregateFunction.AVG,
                        AggregateFunction.MIN, AggregateFunction.MAX);
            }
            return Set.of(AggregateFunction.COUNT);
        }
        @Override public AdapterAggregateResult aggregate(ValidatedAggregateQuery query) {
            return new AdapterAggregateResult(List.of(), false);
        }
    }
}
