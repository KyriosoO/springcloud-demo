package com.dylan.agent.capability.aggregate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.plan.AgentAggregateSpec;
import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.plan.AggregateMetricSpec;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

@DisplayName("AggregatePlanValidator")
class AggregatePlanValidatorTest {

    private AggregatePlanValidator validator;

    @BeforeEach
    void setUp() {
        var properties = DomainMetadataTestSupport.agentProperties();
        validator = new AggregatePlanValidator(
                properties,
                new FilterNormalizer(properties),
                new FieldConstraintValidator(),
                DomainMetadataTestSupport.catalogView());
    }

    @Test
    @DisplayName("COUNT(*) aggregate plan 通过")
    void shouldValidateCountStar() {
        var result = validator.validate(context(aggregateResponse(
                "transaction", AggregateFunction.COUNT, null)));

        assertThat(result.intent()).isEqualTo(AgentIntent.AGGREGATE);
        assertThat(result.domain()).isEqualTo("transaction");
        assertThat(result.aggregate().getMetrics()).hasSize(1);
    }

    @Test
    @DisplayName("SUM decimal field 通过")
    void shouldValidateSumDecimal() {
        var result = validator.validate(context(aggregateResponse(
                "transaction", AggregateFunction.SUM, "amount")));

        assertThat(result.aggregate().getMetrics().get(0).getField()).isEqualTo("amount");
    }

    @Test
    @DisplayName("unknown domain 拒绝")
    void shouldRejectUnknownDomain() {
        assertThatThrownBy(() -> validator.validate(context(aggregateResponse(
                "nonexistent", AggregateFunction.COUNT, null))))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("domain");
    }

    @Test
    @DisplayName("unknown groupBy field 拒绝")
    void shouldRejectUnknownGroupBy() {
        var resp = aggregateResponse("transaction", AggregateFunction.COUNT, null);
        resp.getPlan().getAggregate().setGroupByFields(List.of("unknownField"));

        assertThatThrownBy(() -> validator.validate(context(resp)))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("groupBy");
    }

    @Test
    @DisplayName("SUM 非 DECIMAL 拒绝")
    void shouldRejectSumOnNonDecimal() {
        assertThatThrownBy(() -> validator.validate(context(aggregateResponse(
                "transaction", AggregateFunction.SUM, "transId"))))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("DECIMAL");
    }

    @Test
    @DisplayName("maxRows 超过上限拒绝")
    void shouldRejectMaxRowsTooLarge() {
        var resp = aggregateResponse("transaction", AggregateFunction.COUNT, null);
        resp.getPlan().getAggregate().setMaxRows(200);

        assertThatThrownBy(() -> validator.validate(context(resp)))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("maxRows");
    }

    @Test
    @DisplayName("空 metrics 拒绝")
    void shouldRejectEmptyMetrics() {
        var resp = aggregateResponse("transaction", AggregateFunction.COUNT, null);
        resp.getPlan().getAggregate().setMetrics(List.of());

        assertThatThrownBy(() -> validator.validate(context(resp)))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("metric");
    }

    @Test
    @DisplayName("重复 alias 拒绝")
    void shouldRejectDuplicateAlias() {
        var resp = new PlanGenerateResponse();
        resp.setRequestId("turn-001");
        var plan = new AgentPlan();
        plan.setPlanVersion("1.0");
        plan.setIntent(AgentIntent.AGGREGATE);
        plan.setDomain("transaction");
        var spec = new AgentAggregateSpec();
        spec.setMetrics(List.of(metric("sameName", AggregateFunction.COUNT, null),
                metric("sameName", AggregateFunction.SUM, "amount")));
        plan.setAggregate(spec);
        resp.setPlan(plan);

        assertThatThrownBy(() -> validator.validate(context(resp)))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("alias");
    }

    @Test
    @DisplayName("D04 Catalog 未登记的 function 拒绝")
    void shouldRejectUnsupportedMetricFunction() {
        assertThatThrownBy(() -> validator.validate(context(aggregateResponse(
                "transaction", AggregateFunction.MIN, "transDate"))))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("MIN");
    }

    private CapabilityValidationContext context(PlanGenerateResponse resp) {
        return new CapabilityValidationContext(resp, "turn-001", null,
                new AgentUserContext("admin", Set.of("agent:admin")));
    }

    private PlanGenerateResponse aggregateResponse(
            String domain, AggregateFunction func, String field) {
        var resp = new PlanGenerateResponse();
        resp.setRequestId("turn-001");
        var plan = new AgentPlan();
        plan.setPlanVersion("1.0");
        plan.setIntent(AgentIntent.AGGREGATE);
        plan.setDomain(domain);
        var spec = new AgentAggregateSpec();
        spec.setMetrics(List.of(metric("m1", func, field)));
        plan.setAggregate(spec);
        resp.setPlan(plan);
        return resp;
    }

    private AggregateMetricSpec metric(String alias, AggregateFunction func, String field) {
        var metric = new AggregateMetricSpec();
        metric.setAlias(alias);
        metric.setFunction(func);
        metric.setField(field);
        return metric;
    }
}
