package com.dylan.agent.kernel.core;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.enums.QueryContextMode;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.api.plan.AgentSortSpec;
import com.dylan.agent.capability.query.QueryPlanValidator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.invocation.model.CancellationSource;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;
import com.dylan.agent.kernel.port.model.ExecutionValidationProjection;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
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

class QueryPlanValidatorTest {

    private static final Instant NOW = Instant.parse("2026-07-01T00:00:00Z");

    @Test
    void acceptsWhitelistedSorts() {
        var result = validator().validate(plan(List.of(sort("chineseName", "desc"))), context(Set.of("chineseName")));

        assertThat(result.query().getSorts()).singleElement().satisfies(sort -> {
            assertThat(sort.getField()).isEqualTo("chineseName");
            assertThat(sort.getDirection()).isEqualTo("DESC");
        });
    }

    @Test
    void rejectsUnknownSortField() {
        assertThatThrownBy(() -> validator().validate(plan(List.of(sort("unknown", "ASC"))), context(Set.of("chineseName"))))
                .isInstanceOf(KernelExecutionException.class)
                .satisfies(error -> assertThat(((KernelExecutionException) error).errorCode())
                        .isEqualTo(KernelErrorCode.FIELD_FORBIDDEN));
    }

    @Test
    void rejectsForbiddenSortField() {
        assertThatThrownBy(() -> validator().validate(plan(List.of(sort("phoneNo", "ASC"))), context(Set.of("chineseName"))))
                .isInstanceOf(KernelExecutionException.class)
                .satisfies(error -> assertThat(((KernelExecutionException) error).errorCode())
                        .isEqualTo(KernelErrorCode.FIELD_FORBIDDEN));
    }

    @Test
    void rejectsSortFieldOutsideSortWhitelist() {
        assertThatThrownBy(() -> validator().validate(plan(List.of(sort("chineseName", "ASC"))), context(Set.of())))
                .isInstanceOf(KernelExecutionException.class)
                .satisfies(error -> assertThat(((KernelExecutionException) error).errorCode())
                        .isEqualTo(KernelErrorCode.PLAN_VALIDATION_FAILED));
    }

    @Test
    void rejectsDuplicateSortField() {
        assertThatThrownBy(() -> validator().validate(
                plan(List.of(sort("chineseName", "ASC"), sort("chineseName", "DESC"))),
                context(Set.of("chineseName"))))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("invalid query sorts");
    }

    @Test
    void rejectsInvalidSortDirection() {
        assertThatThrownBy(() -> validator().validate(plan(List.of(sort("chineseName", "DOWN"))), context(Set.of("chineseName"))))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("invalid query sorts");
    }

    private QueryPlanValidator validator() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        FieldConstraintValidator constraints = new FieldConstraintValidator();
        return new QueryPlanValidator(
                properties,
                new FilterNormalizer(properties),
                constraints,
                new QueryMergeEngine(constraints));
    }

    private ExecutionValidationContext context(Set<String> sortFields) {
        return new ExecutionValidationContext(
                "query.search",
                AgentPlanKind.QUERY,
                AgentDomainMode.REQUIRED,
                executionScope(),
                new ExecutionValidationProjection(
                        AdapterRole.QUERYABLE,
                        "employee",
                        Map.of("chineseName", rule("chineseName")),
                        List.of("chineseName"),
                        sortFields,
                        "catalog-v1"),
                null,
                List.of(),
                NOW.plusSeconds(30),
                new CancellationSource().token());
    }

    private ExecutionScope executionScope() {
        return com.dylan.agent.testsupport.ExecutionScopeTestFactory.create(
                "user:u-1",
                com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence("catalog-v1", "adapter-v1", "availability", NOW),
                NOW,
                "perm-evidence-1",
                "perm-v1",
                "policy-v1",
                Set.of("query.search"),
                Set.of("employee"),
                Map.of(),
                Map.of(),
                com.dylan.agent.kernel.resource.StandardResourceLimits
                        .testEffective(100, 100, 10_000));
    }

    private QueryAgentPlan plan(List<AgentSortSpec> sorts) {
        AgentQuerySpec query = new AgentQuerySpec();
        query.setContextMode(QueryContextMode.REPLACE);
        query.setFilters(List.of(filter("chineseName", "张")));
        query.setSorts(sorts);
        QueryAgentPlan plan = new QueryAgentPlan();
        plan.setQuery(query);
        return plan;
    }

    private ExecutionFieldRule rule(String field) {
        return new ExecutionFieldRule(
                field,
                AgentFieldType.STRING,
                Set.of(AgentOperator.EQ, AgentOperator.CONTAINS),
                Set.of(),
                100,
                null,
                null,
                null);
    }

    private AgentFilter filter(String field, String value) {
        AgentFilter filter = new AgentFilter();
        filter.setField(field);
        filter.setOperator(AgentOperator.CONTAINS);
        filter.setValue(value);
        return filter;
    }

    private AgentSortSpec sort(String field, String direction) {
        AgentSortSpec sort = new AgentSortSpec();
        sort.setField(field);
        sort.setDirection(direction);
        return sort;
    }
}
