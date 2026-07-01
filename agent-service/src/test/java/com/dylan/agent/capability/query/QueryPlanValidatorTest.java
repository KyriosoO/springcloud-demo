package com.dylan.agent.capability.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.enums.QueryContextMode;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.api.runtime.RuntimeQueryContext;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.model.ValidatedQueryPlan;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;
import com.dylan.agent.planning.filter.QueryMergeEngine;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

@DisplayName("QueryPlanValidator")
class QueryPlanValidatorTest {

    private QueryPlanValidator validator;
    private AgentProperties properties;

    @BeforeEach
    void setUp() {
        properties = DomainMetadataTestSupport.agentProperties();
        var normalizer = new FilterNormalizer(properties);
        var constraints = new FieldConstraintValidator();
        var mergeEngine = new QueryMergeEngine(constraints);
        validator = new QueryPlanValidator(
                properties, normalizer, constraints, mergeEngine,
                DomainMetadataTestSupport.catalogView());
    }

    @Nested
    @DisplayName("QUERY 正常场景")
    class QuerySuccess {

        @Test
        @DisplayName("position EQ HRM 通过校验")
        void shouldValidatePositionEq() {
            PlanGenerateResponse resp = queryResponse("position", AgentOperator.EQ, "HRM",
                    List.of("chineseName", "memberNo", "position"), 1, 20);
            ValidatedQueryPlan plan = validator.validate(ctx(resp, null));
            assertThat(plan.intent()).isEqualTo(AgentIntent.QUERY);
            assertThat(plan.query().getFilters().get(0).getField()).isEqualTo("position");
            assertThat(plan.query().getFilters().get(0).getOperator()).isEqualTo(AgentOperator.EQ);
            assertThat(plan.query().getFilters().get(0).getValue()).isEqualTo("HRM");
            assertThat(plan.query().getSelectFields()).containsExactly("chineseName", "memberNo", "position");
            assertThat(plan.query().getPage()).isEqualTo(1);
            assertThat(plan.query().getSize()).isEqualTo(20);
        }

        @Test
        @DisplayName("page/size 未指定时使用默认值")
        void shouldDefaultPageAndSize() {
            PlanGenerateResponse resp = queryResponse("position", AgentOperator.EQ, "HRM",
                    List.of("chineseName"), null, null);
            ValidatedQueryPlan plan = validator.validate(ctx(resp, null));
            assertThat(plan.query().getPage()).isEqualTo(1);
            assertThat(plan.query().getSize()).isEqualTo(properties.getQuery().getDefaultSize());
        }

        @Test
        @DisplayName("MERGE 可在已有 GT 基础上增加 LT")
        void shouldAllowUpperRangeMergedWithExistingLowerRange() {
            RuntimeQueryContext previous = previousQuery(
                    List.of(filter("amount", AgentOperator.GT, "100")));
            PlanGenerateResponse resp = mergeResponse(
                    List.of(filter("amount", AgentOperator.LT, "1000")));

            ValidatedQueryPlan plan = validator.validate(ctx(resp, previous));

            assertThat(plan.query().getFilters())
                    .extracting(f -> f.getOperator())
                    .containsExactly(AgentOperator.GT, AgentOperator.LT);
        }

        @Test
        @DisplayName("selectFields 可为 null，使用默认字段")
        void shouldDefaultSelectFieldsWhenNull() {
            PlanGenerateResponse resp = queryResponse("position", AgentOperator.EQ, "HRM",
                    null, 1, 20);
            ValidatedQueryPlan plan = validator.validate(ctx(resp, null));
            assertThat(plan.query().getSelectFields())
                    .containsExactly("chineseName", "memberNo", "position");
        }
    }

    @Nested
    @DisplayName("QUERY 拒绝场景")
    class QueryRejection {

        @Test
        @DisplayName("非 QUERY plan 拒绝")
        void shouldRejectNonQueryPlan() {
            PlanGenerateResponse resp = clarifyResponse("transaction", "请提供查询条件");
            assertThatThrownBy(() -> validator.validate(ctx(resp, null)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("必须为 QUERY");
        }

        @Test
        @DisplayName("缺少 query 字段拒绝")
        void shouldRejectMissingQuery() {
            PlanGenerateResponse resp = new PlanGenerateResponse();
            resp.setRequestId("turn-001");
            AgentPlan plan = new AgentPlan();
            plan.setPlanVersion("1.0");
            plan.setIntent(AgentIntent.QUERY);
            plan.setDomain("employee");
            plan.setQuery(null);
            resp.setPlan(plan);

            assertThatThrownBy(() -> validator.validate(ctx(resp, null)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("缺少 query");
        }

        @Test
        @DisplayName("同时携带 clarify 拒绝")
        void shouldRejectQueryWithClarify() {
            PlanGenerateResponse resp = queryResponse("position", AgentOperator.EQ, "HRM",
                    List.of("chineseName"), 1, 20);
            com.dylan.agent.api.plan.ClarifySpec clarify = new com.dylan.agent.api.plan.ClarifySpec();
            clarify.setQuestion("test");
            resp.getPlan().setClarify(clarify);

            assertThatThrownBy(() -> validator.validate(ctx(resp, null)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("clarify");
        }

        @Test
        @DisplayName("同时携带 aggregate 拒绝")
        void shouldRejectQueryWithAggregate() {
            PlanGenerateResponse resp = queryResponse("position", AgentOperator.EQ, "HRM",
                    List.of("chineseName"), 1, 20);
            com.dylan.agent.api.plan.AgentAggregateSpec aggregate = new com.dylan.agent.api.plan.AgentAggregateSpec();
            aggregate.setMetrics(List.of());
            resp.getPlan().setAggregate(aggregate);

            assertThatThrownBy(() -> validator.validate(ctx(resp, null)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("aggregate");
        }

        @Test
        @DisplayName("domain 不存在拒绝")
        void shouldRejectUnknownDomain() {
            PlanGenerateResponse resp = queryResponse("position", AgentOperator.EQ, "HRM",
                    List.of("chineseName"), 1, 20);
            resp.getPlan().setDomain("nonexistent");

            assertThatThrownBy(() -> validator.validate(ctx(resp, null)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("domain");
        }

        @Test
        @DisplayName("QUERY 无 filter 拒绝")
        void shouldRejectQueryWithoutFilters() {
            PlanGenerateResponse resp = new PlanGenerateResponse();
            resp.setRequestId("turn-001");
            AgentPlan plan = new AgentPlan();
            plan.setPlanVersion("1.0");
            plan.setIntent(AgentIntent.QUERY);
            plan.setDomain("employee");
            AgentQuerySpec spec = new AgentQuerySpec();
            spec.setFilters(List.of());
            spec.setPage(1);
            spec.setSize(20);
            plan.setQuery(spec);
            resp.setPlan(plan);

            assertThatThrownBy(() -> validator.validate(ctx(resp, null)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("过滤条件");
        }

        @Test
        @DisplayName("page 小于 1 拒绝")
        void shouldRejectPageLessThanOne() {
            PlanGenerateResponse resp = queryResponse("position", AgentOperator.EQ, "HRM",
                    List.of("chineseName"), 0, 20);
            assertThatThrownBy(() -> validator.validate(ctx(resp, null)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("page");
        }

        @Test
        @DisplayName("size 超出最大值拒绝")
        void shouldRejectSizeExceedsMax() {
            PlanGenerateResponse resp = queryResponse("position", AgentOperator.EQ, "HRM",
                    List.of("chineseName"), 1, 200);
            assertThatThrownBy(() -> validator.validate(ctx(resp, null)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("size");
        }

        @Test
        @DisplayName("REPLACE 不允许 removeFields")
        void shouldRejectRemoveFieldsInReplace() {
            PlanGenerateResponse resp = queryResponse("position", AgentOperator.EQ, "HRM",
                    List.of("chineseName"), 1, 20);
            resp.getPlan().getQuery().setRemoveFields(List.of("position"));

            assertThatThrownBy(() -> validator.validate(ctx(resp, null)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("removeFields");
        }

        @Test
        @DisplayName("MERGE 无 previousQuery 拒绝")
        void shouldRejectMergeWithoutPreviousQuery() {
            PlanGenerateResponse resp = new PlanGenerateResponse();
            resp.setRequestId("turn-001");
            AgentPlan plan = new AgentPlan();
            plan.setPlanVersion("1.0");
            plan.setIntent(AgentIntent.QUERY);
            plan.setDomain("employee");
            AgentQuerySpec spec = new AgentQuerySpec();
            spec.setContextMode(QueryContextMode.MERGE);
            spec.setFilters(List.of(filter("position", AgentOperator.EQ, "HRM")));
            plan.setQuery(spec);
            resp.setPlan(plan);

            assertThatThrownBy(() -> validator.validate(ctx(resp, null)))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("MERGE");
        }
    }

    // --- helpers ---

    private CapabilityValidationContext ctx(PlanGenerateResponse resp, RuntimeQueryContext previousQuery) {
        return new CapabilityValidationContext(resp, "turn-001", previousQuery,
                new AgentUserContext("user", Set.of("agent:admin")));
    }

    private PlanGenerateResponse queryResponse(String field, AgentOperator op,
                                                String value, List<String> selectFields,
                                                Integer page, Integer size) {
        return queryResponse(List.of(filter(field, op, value)), selectFields, page, size);
    }

    private PlanGenerateResponse queryResponse(List<AgentFilter> filters) {
        return queryResponse(filters, List.of("chineseName", "memberNo", "position"), 1, 20);
    }

    private PlanGenerateResponse queryResponse(List<AgentFilter> filters,
                                                List<String> selectFields, Integer page, Integer size) {
        PlanGenerateResponse resp = new PlanGenerateResponse();
        resp.setRequestId("turn-001");
        AgentPlan plan = new AgentPlan();
        plan.setPlanVersion("1.0");
        plan.setIntent(AgentIntent.QUERY);
        plan.setDomain("employee");
        AgentQuerySpec spec = new AgentQuerySpec();
        spec.setContextMode(QueryContextMode.REPLACE);
        spec.setFilters(filters);
        spec.setSelectFields(selectFields);
        spec.setPage(page);
        spec.setSize(size);
        plan.setQuery(spec);
        resp.setPlan(plan);
        return resp;
    }

    private PlanGenerateResponse mergeResponse(List<AgentFilter> filters) {
        PlanGenerateResponse resp = queryResponse(filters);
        resp.getPlan().getQuery().setContextMode(QueryContextMode.MERGE);
        return resp;
    }

    private PlanGenerateResponse clarifyResponse(String domain, String question) {
        PlanGenerateResponse resp = new PlanGenerateResponse();
        resp.setRequestId("turn-001");
        AgentPlan plan = new AgentPlan();
        plan.setPlanVersion("1.0");
        plan.setIntent(AgentIntent.CLARIFY);
        plan.setDomain(domain);
        com.dylan.agent.api.plan.ClarifySpec clarify = new com.dylan.agent.api.plan.ClarifySpec();
        clarify.setQuestion(question);
        plan.setClarify(clarify);
        resp.setPlan(plan);
        return resp;
    }

    private AgentFilter filter(String field, AgentOperator op, String value) {
        AgentFilter f = new AgentFilter();
        f.setField(field);
        f.setOperator(op);
        f.setValue(value);
        return f;
    }

    private RuntimeQueryContext previousQuery(List<AgentFilter> filters) {
        RuntimeQueryContext ctx = new RuntimeQueryContext();
        ctx.setSourceTurnId("turn-000");
        ctx.setDomain("employee");
        ctx.setFilters(filters);
        ctx.setSelectFields(List.of("chineseName", "memberNo", "position"));
        ctx.setPage(1);
        ctx.setSize(20);
        return ctx;
    }

}
