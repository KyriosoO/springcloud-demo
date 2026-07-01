package com.dylan.agent.kernel.core;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.plan.AggregateAgentPlan;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.plan.AgentAggregateSpec;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.api.plan.AggregateMetricSpec;
import com.dylan.agent.capability.aggregate.AggregatePlanValidator;
import com.dylan.agent.capability.query.QueryPlanValidator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.invocation.model.CancellationSource;
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

class KernelValidatorBudgetTest {

    private static final Instant NOW = Instant.parse("2026-07-01T00:00:00Z");

    @Test
    void queryValidatorUsesMinimumOfGlobalProjectionAndExecutionScopeBudgets() {
        QueryPlanValidator validator = queryValidator();

        QueryAgentPlan defaultSizePlan = queryPlan(null);
        ValidatedQuery defaulted = validator.validate(defaultSizePlan, context(AgentPlanKind.QUERY)).query();

        assertThat(defaulted.getSize()).isEqualTo(5);

        assertThatThrownBy(() -> validator.validate(queryPlan(6), context(AgentPlanKind.QUERY)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("pagination");
    }

    @Test
    void aggregateValidatorUsesMinimumOfGlobalProjectionAndExecutionScopeBudgets() {
        AggregatePlanValidator validator = aggregateValidator();

        AggregateAgentPlan defaultRowsPlan = aggregatePlan(null);
        ValidatedAggregateQuery defaulted =
                validator.validate(defaultRowsPlan, context(AgentPlanKind.AGGREGATE)).aggregate();

        assertThat(defaulted.getMaxRows()).isEqualTo(5);

        assertThatThrownBy(() -> validator.validate(aggregatePlan(6), context(AgentPlanKind.AGGREGATE)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("maxRows");
    }

    private QueryPlanValidator queryValidator() {
        AgentProperties properties = properties();
        var catalogView = DomainMetadataTestSupport.catalogView();
        FieldConstraintValidator constraints = new FieldConstraintValidator();
        return new QueryPlanValidator(
                properties,
                new FilterNormalizer(properties),
                constraints,
                new QueryMergeEngine(constraints),
                catalogView);
    }

    private AggregatePlanValidator aggregateValidator() {
        AgentProperties properties = properties();
        var catalogView = DomainMetadataTestSupport.catalogView();
        return new AggregatePlanValidator(
                properties,
                new FilterNormalizer(properties),
                new FieldConstraintValidator(),
                catalogView);
    }

    private AgentProperties properties() {
        AgentProperties properties = new AgentProperties();
        AgentProperties.QueryProperties query = new AgentProperties.QueryProperties();
        query.setDefaultSize(20);
        query.setMaxSize(100);
        query.setMaxResultWindow(10_000);
        query.setMaxFilters(5);
        query.setMaxInValues(20);
        query.setMaxFilterValueLength(256);
        properties.setQuery(query);

        AgentProperties.AggregateProperties aggregate = new AgentProperties.AggregateProperties();
        aggregate.setDefaultMaxRows(20);
        aggregate.setMaxMaxRows(100);
        properties.setAggregate(aggregate);
        return properties;
    }

    private ExecutionValidationContext context(AgentPlanKind planKind) {
        return new ExecutionValidationContext(
                planKind == AgentPlanKind.QUERY ? "query.search" : "aggregate.compute",
                planKind,
                AgentDomainMode.REQUIRED,
                executionScope(),
                projection(),
                null,
                List.of(),
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
                Set.of("query.search", "aggregate.compute"),
                Set.of("employee"),
                Map.of(),
                Map.of(),
                Duration.ofSeconds(30),
                1,
                5,
                10_000);
    }

    private ExecutionValidationProjection projection() {
        return new ExecutionValidationProjection(
                AdapterRole.QUERYABLE,
                "employee",
                Map.of(
                        "name", new ExecutionFieldRule(
                                "name",
                                AgentFieldType.STRING,
                                Set.of(AgentOperator.EQ),
                                Set.of(),
                                100,
                                null,
                                null,
                                null),
                        "amount", new ExecutionFieldRule(
                                "amount",
                                AgentFieldType.DECIMAL,
                                Set.of(AgentOperator.EQ),
                                Set.of(AggregateFunction.SUM),
                                null,
                                18,
                                2,
                                null)),
                List.of("name"),
                10,
                10,
                "catalog-v1");
    }

    private QueryAgentPlan queryPlan(Integer size) {
        AgentFilter filter = new AgentFilter();
        filter.setField("name");
        filter.setOperator(AgentOperator.EQ);
        filter.setValue("Alice");

        AgentQuerySpec query = new AgentQuerySpec();
        query.setFilters(List.of(filter));
        query.setSelectFields(List.of("name"));
        query.setPage(1);
        query.setSize(size);

        QueryAgentPlan plan = new QueryAgentPlan();
        plan.setQuery(query);
        return plan;
    }

    private AggregateAgentPlan aggregatePlan(Integer maxRows) {
        AggregateMetricSpec metric = new AggregateMetricSpec();
        metric.setAlias("total");
        metric.setFunction(AggregateFunction.COUNT);

        AgentAggregateSpec aggregate = new AgentAggregateSpec();
        aggregate.setMetrics(List.of(metric));
        aggregate.setMaxRows(maxRows);

        AggregateAgentPlan plan = new AggregateAgentPlan();
        plan.setAggregate(aggregate);
        return plan;
    }
}
