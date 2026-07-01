package com.dylan.agent.capability.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.capability.CapabilityExecutionContext;
import com.dylan.agent.capability.CapabilityExecutionResult;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.model.ValidatedQueryPlan;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.exception.AgentQueryException;
import com.dylan.agent.mask.AddressFieldMasker;
import com.dylan.agent.mask.EmailFieldMasker;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.mask.IdCardFieldMasker;
import com.dylan.agent.mask.MobileFieldMasker;
import com.dylan.agent.mask.NoneFieldMasker;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;
import com.dylan.agent.planning.filter.QueryMergeEngine;
import com.dylan.agent.result.AgentResultProcessor;
import com.dylan.agent.security.AgentPermissionService;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

@DisplayName("QueryCapabilityHandler")
class QueryCapabilityHandlerTest {

    private QueryCapabilityHandler handler;
    private TestAdapter testAdapter;
    private AgentUserContext admin;

    @BeforeEach
    void setUp() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        var catalogView = DomainMetadataTestSupport.catalogView();
        var normalizer = new FilterNormalizer(properties);
        var constraints = new FieldConstraintValidator();
        var mergeEngine = new QueryMergeEngine(constraints);
        var queryPlanValidator = new QueryPlanValidator(
                properties, normalizer, constraints, mergeEngine, catalogView);
        var permissionService = new AgentPermissionService(properties, catalogView);
        var maskerRegistry = new FieldMaskerRegistry(List.of(new NoneFieldMasker(),
                new IdCardFieldMasker(), new MobileFieldMasker(),
                new EmailFieldMasker(), new AddressFieldMasker()));
        var resultProcessor = new AgentResultProcessor(permissionService, maskerRegistry);

        testAdapter = new TestAdapter();
        var adapterPortResolver = DomainMetadataTestSupport.adapterPortResolver(testAdapter, null);

        handler = new QueryCapabilityHandler(queryPlanValidator, permissionService,
                adapterPortResolver, resultProcessor);

        admin = new AgentUserContext("admin", Set.of("agent:admin", "agent:viewer"));
    }

    @Nested
    @DisplayName("validate")
    class Validate {

        @Test
        @DisplayName("返回 ValidatedQueryPlan")
        void shouldReturnValidatedQueryPlan() {
            var resp = queryResponse("position", AgentOperator.EQ, "HRM");
            var context = new CapabilityValidationContext(resp, "turn-001", null, admin);

            ValidatedQueryPlan plan = handler.validate(context);

            assertThat(plan.intent()).isEqualTo(AgentIntent.QUERY);
            assertThat(plan.domain()).isEqualTo("employee");
            assertThat(plan.query().getFilters()).hasSize(1);
        }

        @Test
        @DisplayName("非法 QUERY plan 由 QueryPlanValidator 拒绝")
        void shouldDelegateToValidator() {
            var resp = new PlanGenerateResponse();
            resp.setRequestId("turn-001");
            AgentPlan plan = new AgentPlan();
            plan.setPlanVersion("1.0");
            plan.setIntent(AgentIntent.QUERY);
            plan.setDomain("employee");
            plan.setQuery(null);
            resp.setPlan(plan);
            var context = new CapabilityValidationContext(resp, "turn-001", null, admin);

            assertThatThrownBy(() -> handler.validate(context))
                    .isInstanceOf(RuntimeException.class);
        }
    }

    @Nested
    @DisplayName("execute")
    class Execute {

        @Test
        @DisplayName("正常执行返回 CapabilityExecutionResult.queryResult")
        void shouldExecuteQuerySuccessfully() {
            var query = new ValidatedQuery(
                    List.of(), List.of("chineseName", "memberNo", "position"), 1, 20);
            var plan = new ValidatedQueryPlan("employee", query);
            var execCtx = new CapabilityExecutionContext("conv-1", "turn-001", "测试", admin, null);

            CapabilityExecutionResult result = handler.execute(execCtx, plan);

            assertThat(result.intent()).isEqualTo(AgentIntent.QUERY);
            assertThat(result.queryParameters()).isNotNull();
            assertThat(result.queryParameters().getDomain()).isEqualTo("employee");
            assertThat(result.queryResult()).isNotNull();
            assertThat(result.contextToPersist()).isNotNull();
            assertThat(((com.dylan.agent.api.runtime.RuntimeQueryContext) result.contextToPersist()).getDomain())
                    .isEqualTo("employee");
        }

        @Test
        @DisplayName("adapter 异常转为 AgentQueryException")
        void shouldConvertAdapterException() {
            testAdapter.throwException = true;
            var query = new ValidatedQuery(
                    List.of(), List.of("chineseName", "memberNo", "position"), 1, 20);
            var plan = new ValidatedQueryPlan("employee", query);
            var execCtx = new CapabilityExecutionContext("conv-1", "turn-001", "测试", admin, null);

            assertThatThrownBy(() -> handler.execute(execCtx, plan))
                    .isInstanceOf(AgentQueryException.class);
        }
    }

    private PlanGenerateResponse queryResponse(String field, AgentOperator op, String value) {
        PlanGenerateResponse resp = new PlanGenerateResponse();
        resp.setRequestId("turn-001");
        AgentPlan plan = new AgentPlan();
        plan.setPlanVersion("1.0");
        plan.setIntent(AgentIntent.QUERY);
        plan.setDomain("employee");
        AgentQuerySpec spec = new AgentQuerySpec();
        com.dylan.agent.api.plan.AgentFilter f = new com.dylan.agent.api.plan.AgentFilter();
        f.setField(field);
        f.setOperator(op);
        f.setValue(value);
        spec.setFilters(List.of(f));
        spec.setSelectFields(List.of("chineseName", "memberNo", "position"));
        spec.setPage(1);
        spec.setSize(20);
        plan.setQuery(spec);
        resp.setPlan(plan);
        return resp;
    }

    static class TestAdapter implements QueryableAdapter {
        boolean throwException;

        @Override
        public AdapterQueryResult query(ValidatedQuery query) {
            if (throwException) {
                throw new AgentAdapterException("adapter error", null);
            }
            return new AdapterQueryResult(List.of(), 5, true, 1, 20);
        }
    }
}
