package com.dylan.agent.metadata.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import org.junit.jupiter.api.Test;
import org.springframework.context.support.GenericApplicationContext;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPortImpl;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPropertiesValidator;
import com.dylan.agent.metadata.domain.internal.DomainMetadataStore;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.domain.port.CanonicalFunctionRef;
import com.dylan.agent.metadata.domain.port.DomainMetadataReferenceSet;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

class DomainMetadataPortImplTest {

    private static final Instant DEADLINE = Instant.parse("2026-07-02T00:01:00Z");

    @Test
    void executionProjectionDoesNotDefaultMissingAllowedFieldsToAllCatalogFields() {
        var port = port();
        var evidence = store().current().evidence();
        ExecutionScope scope = executionScope(evidence, Map.of());

        var projection = port.executionProjection(
                AdapterRole.QUERYABLE,
                "employee",
                scope,
                evidence,
                DEADLINE);

        assertThat(projection.fieldRules()).isEmpty();
        assertThat(projection.defaultSelectFields()).isEmpty();
    }

    @Test
    void executionProjectionUsesOnlyExecutionScopeAllowedFields() {
        var port = port();
        var evidence = store().current().evidence();
        ExecutionScope scope = executionScope(
                evidence,
                Map.of("employee", Set.of("chineseName")));

        var projection = port.executionProjection(
                AdapterRole.QUERYABLE,
                "employee",
                scope,
                evidence,
                DEADLINE);

        assertThat(projection.fieldRules()).containsOnlyKeys("chineseName");
        assertThat(projection.defaultSelectFields()).containsExactly("chineseName");
    }

    @Test
    void validateReferencesRejectsUnregisteredFunctionEvenForCount() {
        var port = port();
        CanonicalFieldRef field = new CanonicalFieldRef("employee", "chineseName");
        var refs = new DomainMetadataReferenceSet(
                Set.of(field),
                Set.of(),
                Set.of(new CanonicalFunctionRef(field, "COUNT")));

        assertThatThrownBy(() -> port.validateReferences(refs, DEADLINE))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("function");
    }

    @Test
    void validateReferencesRejectsUnknownFunctionIdWithStableError() {
        var port = port();
        CanonicalFieldRef field = new CanonicalFieldRef("employee", "chineseName");
        var refs = new DomainMetadataReferenceSet(
                Set.of(field),
                Set.of(),
                Set.of(new CanonicalFunctionRef(field, "UNKNOWN_FUNCTION")));

        assertThatThrownBy(() -> port.validateReferences(refs, DEADLINE))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("unknown function reference");
    }

    @Test
    void planSchemaMapsCanonicalFunctionIdsToD01AggregateFunctionEnum() {
        var port = port();
        var evidence = store().current().evidence();
        CanonicalFieldRef amount = new CanonicalFieldRef("transaction", "amount");
        PlanningEffectiveScope scope = new PlanningEffectiveScope(
                Set.of("aggregate.compute"),
                Set.of("transaction"),
                Map.of(amount, new PlanningEffectiveScope.FieldAccess(
                        true,
                        true,
                        Set.of(AgentOperator.EQ, AgentOperator.GT, AgentOperator.LT),
                        Set.of("sum", "avg", "min", "max"),
                        Optional.of(MaskType.NONE))),
                Set.of(),
                Set.of(),
                AgentCapabilityRiskLevel.READ_ONLY,
                AgentCapabilityExecutionMode.IMMEDIATE,
                Duration.ofSeconds(30),
                1,
                100,
                100,
                10_000);

        var schema = port.planSchema(
                AdapterRole.AGGREGATABLE,
                "transaction",
                scope,
                evidence,
                DEADLINE);

        assertThat(schema.getFields())
                .singleElement()
                .satisfies(field -> assertThat(field.getAggregateFunctions())
                        .containsExactly(AggregateFunction.AVG, AggregateFunction.MAX,
                                AggregateFunction.MIN, AggregateFunction.SUM));
    }

    private DomainMetadataPortImpl port() {
        return new DomainMetadataPortImpl(
                store(),
                context(),
                DomainMetadataTestSupport.TEST_CLOCK);
    }

    private DomainMetadataStore store() {
        return new DomainMetadataStore(DomainMetadataPropertiesValidator.build(
                DomainMetadataTestSupport.properties(),
                context().getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class),
                DomainMetadataTestSupport.TEST_CLOCK));
    }

    private GenericApplicationContext context() {
        GenericApplicationContext context = new GenericApplicationContext();
        context.registerBean("employeeAgentAdapter",
                DomainMetadataTestSupport.QueryableAggregatableAdapter.class,
                DomainMetadataTestSupport.QueryableAggregatableAdapter::new);
        context.registerBean("transactionAgentAdapter",
                DomainMetadataTestSupport.QueryableAggregatableAdapter.class,
                DomainMetadataTestSupport.QueryableAggregatableAdapter::new);
        context.refresh();
        return context;
    }

    private ExecutionScope executionScope(
            com.dylan.agent.metadata.domain.port.DomainMetadataEvidence evidence,
            Map<String, Set<String>> allowedFields) {
        return new ExecutionScope(
                "user:u-1",
                evidence,
                Instant.parse("2026-07-02T00:00:00Z"),
                "perm-evidence-1",
                "perm-v1",
                "policy-v1",
                Set.of("query.search"),
                Set.of("employee"),
                allowedFields,
                Map.of("employee.chineseName", MaskType.NONE),
                Duration.ofSeconds(30),
                1,
                100,
                10_000);
    }
}
