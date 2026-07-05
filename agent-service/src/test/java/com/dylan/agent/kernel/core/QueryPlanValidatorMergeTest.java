package com.dylan.agent.kernel.core;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.enums.QueryContextMode;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.capability.query.QueryPlanValidator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.invocation.model.CancellationSource;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;
import com.dylan.agent.kernel.port.model.ExecutionValidationProjection;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.context.model.ContextRecordKey;
import com.dylan.agent.metadata.context.model.ContextSnapshot;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;
import com.dylan.agent.planning.filter.QueryMergeEngine;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class QueryPlanValidatorMergeTest {

    private static final Instant NOW = Instant.parse("2026-07-01T00:00:00Z");

    @Test
    void mergePageOnlyInheritsPreviousQueryAndAppliesRequestedPage() {
        QueryPlanValidator validator = validator();

        var plan = queryPlan(QueryContextMode.MERGE, List.of(), null, 3, null, List.of());
        var result = validator.validate(plan, context(List.of(snapshot(previousPayload(45L, true, 3)))));

        assertThat(result.query().getFilters()).singleElement().satisfies(filter -> {
            assertThat(filter.getField()).isEqualTo("chineseName");
            assertThat(filter.getOperator()).isEqualTo(AgentOperator.CONTAINS);
            assertThat(filter.getValue()).isEqualTo("张");
        });
        assertThat(result.query().getSelectFields()).containsExactly("chineseName");
        assertThat(result.query().getPage()).isEqualTo(3);
        assertThat(result.query().getSize()).isEqualTo(20);
    }

    @Test
    void mergeRejectsPageBeyondExactTotalPagesWithSafeMessage() {
        QueryPlanValidator validator = validator();

        var plan = queryPlan(QueryContextMode.MERGE, List.of(), null, 4, null, List.of());

        assertThatThrownBy(() -> validator.validate(plan, context(List.of(snapshot(previousPayload(45L, true, 3))))))
                .isInstanceOf(KernelExecutionException.class)
                .satisfies(error -> {
                    KernelExecutionException ex = (KernelExecutionException) error;
                    assertThat(ex.errorCode()).isEqualTo(KernelErrorCode.PLAN_VALIDATION_FAILED);
                    assertThat(ex.safeMessage()).isEqualTo("请求页码超过当前结果总页数，请调整页码后重试。");
                });
    }

    @Test
    void existingButUnauthorizedSelectFieldReturnsFieldForbidden() {
        QueryPlanValidator validator = validator();
        var plan = queryPlan(QueryContextMode.REPLACE, List.of(filter("chineseName", "张")),
                List.of("phoneNo"), 1, 20, List.of());

        assertThatThrownBy(() -> validator.validate(plan, context(List.of())))
                .isInstanceOf(KernelExecutionException.class)
                .satisfies(error -> {
                    KernelExecutionException ex = (KernelExecutionException) error;
                    assertThat(ex.errorCode()).isEqualTo(KernelErrorCode.FIELD_FORBIDDEN);
                    assertThat(ex.safeMessage()).isEqualTo("没有权限访问请求的字段，请调整字段后重试。");
                });
    }

    private QueryPlanValidator validator() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        FieldConstraintValidator constraints = new FieldConstraintValidator();
        return new QueryPlanValidator(
                properties,
                new FilterNormalizer(properties),
                constraints,
                new QueryMergeEngine(constraints),
                DomainMetadataTestSupport.catalogView());
    }

    private ExecutionValidationContext context(List<ContextSnapshot> snapshots) {
        return new ExecutionValidationContext(
                "query.search",
                AgentPlanKind.QUERY,
                AgentDomainMode.REQUIRED,
                executionScope(),
                projection(),
                null,
                snapshots,
                NOW.plusSeconds(30),
                new CancellationSource().token());
    }

    private ExecutionScope executionScope() {
        return new ExecutionScope(
                "user:u-1",
                new DomainMetadataEvidence("catalog-v1", "adapter-v1", "availability", NOW),
                NOW,
                "perm-evidence-1",
                "perm-v1",
                "policy-v1",
                Set.of("query.search"),
                Set.of("employee"),
                Map.of(),
                Map.of(),
                Duration.ofSeconds(30),
                1,
                100,
                10_000);
    }

    private ExecutionValidationProjection projection() {
        return new ExecutionValidationProjection(
                AdapterRole.QUERYABLE,
                "employee",
                Map.of("chineseName", new ExecutionFieldRule(
                        "chineseName",
                        AgentFieldType.STRING,
                        Set.of(AgentOperator.EQ, AgentOperator.CONTAINS),
                        Set.of(),
                        100,
                        null,
                        null,
                        null)),
                List.of("chineseName"),
                100,
                100,
                "catalog-v1");
    }

    private ContextSnapshot snapshot(QueryCapabilityContextPayload payload) {
        return new ContextSnapshot(
                "ctx-1",
                "corr-1",
                new ContextRecordKey(
                        new ContextOwnerRef("conversation", "conv-1"),
                        new ConversationScope("conv-1"),
                        RuntimeContextType.QUERY),
                "query.search",
                "inv-prev",
                "employee",
                AgentExecutionContracts.QUERY_CONTEXT,
                AgentExecutionContracts.QUERY_CONTEXT,
                1,
                NOW.plusSeconds(60),
                "bundle-v1",
                "policy-v1",
                "perm-evidence-1",
                null,
                ExpectedContextVersion.version(1),
                payload);
    }

    private QueryCapabilityContextPayload previousPayload(
            Long total,
            Boolean totalExact,
            Integer totalPages) {
        return new QueryCapabilityContextPayload(
                List.of(filter("chineseName", "张")),
                List.of("chineseName"),
                1,
                20,
                total,
                totalExact,
                totalPages);
    }

    private QueryAgentPlan queryPlan(
            QueryContextMode contextMode,
            List<AgentFilter> filters,
            List<String> selectFields,
            Integer page,
            Integer size,
            List<String> removeFields) {
        AgentQuerySpec query = new AgentQuerySpec();
        query.setContextMode(contextMode);
        query.setFilters(filters);
        query.setSelectFields(selectFields);
        query.setPage(page);
        query.setSize(size);
        query.setRemoveFields(removeFields);

        QueryAgentPlan plan = new QueryAgentPlan();
        plan.setQuery(query);
        return plan;
    }

    private AgentFilter filter(String field, String value) {
        AgentFilter filter = new AgentFilter();
        filter.setField(field);
        filter.setOperator(AgentOperator.CONTAINS);
        filter.setValue(value);
        return filter;
    }
}
