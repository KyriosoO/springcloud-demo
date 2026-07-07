package com.dylan.agent.metadata.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import org.junit.jupiter.api.Test;
import org.springframework.context.support.GenericApplicationContext;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.document.AdapterDocumentResult;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPortImpl;
import com.dylan.agent.metadata.domain.internal.DomainMetadataProperties;
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

    @Test
    void documentRetrievableUsesPageSizeLimit() {
        GenericApplicationContext context = documentContext();
        DomainMetadataStore store = documentStore(context);
        var port = new DomainMetadataPortImpl(store, context, DomainMetadataTestSupport.TEST_CLOCK);
        var evidence = store.current().evidence();
        CanonicalFieldRef title = new CanonicalFieldRef("company_policy", "title");
        PlanningEffectiveScope scope = new PlanningEffectiveScope(
                Set.of("document.search"),
                Set.of("company_policy"),
                Map.of(title, new PlanningEffectiveScope.FieldAccess(
                        true,
                        true,
                        Set.of(AgentOperator.CONTAINS),
                        Set.of(),
                        Optional.of(MaskType.NONE))),
                Set.of(),
                Set.of(),
                AgentCapabilityRiskLevel.READ_ONLY,
                AgentCapabilityExecutionMode.IMMEDIATE,
                Duration.ofSeconds(30),
                1,
                7,
                100,
                10_000);

        var schema = port.planSchema(
                AdapterRole.DOCUMENT_RETRIEVABLE,
                "company_policy",
                scope,
                evidence,
                DEADLINE);

        assertThat(schema.getMaxSize()).isEqualTo(7);
        assertThat(schema.getDefaultSize()).isEqualTo(7);
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

    private GenericApplicationContext documentContext() {
        GenericApplicationContext context = new GenericApplicationContext();
        context.registerBean("documentAgentAdapter", TestDocumentAdapter.class, TestDocumentAdapter::new);
        context.refresh();
        return context;
    }

    private DomainMetadataStore documentStore(GenericApplicationContext context) {
        return new DomainMetadataStore(DomainMetadataPropertiesValidator.build(
                documentProperties(),
                context.getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class),
                DomainMetadataTestSupport.TEST_CLOCK));
    }

    private DomainMetadataProperties documentProperties() {
        DomainMetadataProperties properties = new DomainMetadataProperties();
        properties.setCatalogVersion("catalog-document-test");
        properties.setAdapterRegistrationVersion("adapter-document-test");
        properties.setDomains(Map.of("company_policy", documentDomain()));
        DomainMetadataProperties.RegistrationProperties registration =
                new DomainMetadataProperties.RegistrationProperties();
        registration.setRegistrationId("company-policy-document");
        registration.setRole(AdapterRole.DOCUMENT_RETRIEVABLE.value());
        registration.setDomain("company_policy");
        registration.setPortType(DocumentRetrievableAdapter.class);
        registration.setPortBeanName("documentAgentAdapter");
        registration.setCatalogVersion("catalog-document-test");
        registration.setRegistrationVersion("adapter-document-test");
        properties.setRegistrations(List.of(registration));
        return properties;
    }

    private DomainMetadataProperties.DomainProperties documentDomain() {
        DomainMetadataProperties.DomainProperties domain = new DomainMetadataProperties.DomainProperties();
        domain.setAliases(List.of("公司政策", "company_policy"));
        domain.setDescription("Company policy document corpus.");
        Map<String, DomainMetadataProperties.FieldProperties> fields = new LinkedHashMap<>();
        fields.put("title", documentField("title", AgentFieldType.STRING));
        fields.put("effectiveDate", documentField("effectiveDate", AgentFieldType.INSTANT));
        domain.setFields(fields);
        domain.setDefaultSelectFieldsByRole(Map.of(
                AdapterRole.DOCUMENT_RETRIEVABLE.value(), List.of("title")));
        DomainMetadataProperties.RoleCapabilityProperties capability =
                new DomainMetadataProperties.RoleCapabilityProperties();
        capability.setFields(Set.of("title", "effectiveDate"));
        capability.setSortFields(Set.of("effectiveDate"));
        capability.setOperatorsByField(Map.of(
                "title", Set.of(AgentOperator.CONTAINS),
                "effectiveDate", Set.of(AgentOperator.GT, AgentOperator.LT, AgentOperator.EQ)));
        capability.setMaxPageSize(20);
        capability.setMaxResultRows(50);
        domain.setRoleCapabilities(Map.of(AdapterRole.DOCUMENT_RETRIEVABLE.value(), capability));
        return domain;
    }

    private DomainMetadataProperties.FieldProperties documentField(String field, AgentFieldType type) {
        DomainMetadataProperties.FieldProperties properties = new DomainMetadataProperties.FieldProperties();
        properties.setAliases(List.of(field));
        properties.setDescription(field + " field");
        properties.setType(type);
        if (type == AgentFieldType.INSTANT) {
            properties.setValueFormat("ISO-8601 datetime with timezone");
        }
        return properties;
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

    private static final class TestDocumentAdapter implements DocumentRetrievableAdapter {
        @Override
        public AdapterDocumentResult retrieve(DocumentRetrievalRequest request) {
            return new AdapterDocumentResult();
        }
    }
}
