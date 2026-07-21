package com.dylan.agent.metadata.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.document.AdapterDocumentRetrievalResult;
import com.dylan.agent.adapter.api.document.DocumentRetrievalCommand;
import com.dylan.agent.adapter.api.operation.CapabilityOperationOutcome;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.context.support.GenericApplicationContext;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.io.FileSystemResource;

import com.dylan.agent.metadata.domain.internal.DomainMetadataPropertiesValidator;
import com.dylan.agent.metadata.domain.internal.DomainMetadataProperties;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

class DomainMetadataPropertiesValidatorTest {

    @Test
    void rejectsUnknownRoleCapabilityFields() {
        var properties = DomainMetadataTestSupport.properties();
        properties.getDomains().get("employee")
                .getRoleCapabilities().get("QUERYABLE")
                .setFields(Set.of("missingField"));

        assertThatThrownBy(() -> DomainMetadataPropertiesValidator.build(
                properties,
                context().getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class),
                DomainMetadataTestSupport.TEST_CLOCK))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("unknown field");
    }

    @Test
    void acceptsDocumentRetrievableDomain() {
        var properties = documentProperties();

        var bundle = DomainMetadataPropertiesValidator.build(
                properties,
                documentContext().getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class),
                DomainMetadataTestSupport.TEST_CLOCK);

        assertThat(bundle.catalog().supportsRole("company_policy", AdapterRole.DOCUMENT_RETRIEVABLE)).isTrue();
        assertThat(bundle.registrations().find(AdapterRole.DOCUMENT_RETRIEVABLE, "company_policy")).isPresent();
    }

    @Test
    void documentDomainFixtureDoesNotUseUnsupportedFieldTypesOrLegacySnippetName() throws Exception {
        String yaml = Files.readString(Path.of(
                "..", "config-service", "src", "main", "resources", "config", "agent-service.yml"),
                StandardCharsets.UTF_8);

        assertThat(yaml).doesNotContain(
                "type: DATE", "type: INTEGER", "contentSnippet",
                "        port-type:", "        catalog-version:");
        assertThat(yaml).contains("company_policy:", "tax_policy:", "knowledge_base:", "literature:", "snippet:");
    }

    @Test
    void productionDomainMetadataYamlPassesTheSameCandidateGate() throws Exception {
        Path yamlPath = Path.of(
                "..", "config-service", "src", "main", "resources", "config", "agent-service.yml");
        StandardEnvironment environment = new StandardEnvironment();
        new YamlPropertySourceLoader().load("agent-service", new FileSystemResource(yamlPath))
                .forEach(source -> environment.getPropertySources().addLast(source));
        DomainMetadataProperties properties = Binder.get(environment)
                .bind("agent.domain-metadata", Bindable.of(DomainMetadataProperties.class))
                .orElseThrow(() -> new IllegalStateException("production domain metadata missing"));
        GenericApplicationContext context = context();
        context.registerBean("documentAgentAdapter", TestDocumentAdapter.class, TestDocumentAdapter::new);

        var bundle = DomainMetadataPropertiesValidator.build(
                properties,
                context.getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class),
                DomainMetadataTestSupport.TEST_CLOCK);

        assertThat(bundle.catalog().domains()).containsKeys(
                "employee", "transaction", "company_policy", "tax_policy", "knowledge_base", "literature");
        assertThat(bundle.registrations().sortedRegistrations()).hasSize(8);
    }

    @Test
    void canonicalDigestsIgnoreMapAndRegistrationOrderButPreserveAliasOrder() {
        var first = DomainMetadataTestSupport.properties();
        var reordered = DomainMetadataTestSupport.properties();
        var reversedDomains = new LinkedHashMap<String, DomainMetadataProperties.DomainProperties>();
        reordered.getDomains().entrySet().stream().sorted(Map.Entry.<String, DomainMetadataProperties.DomainProperties>comparingByKey().reversed())
                .forEach(entry -> reversedDomains.put(entry.getKey(), entry.getValue()));
        reordered.setDomains(reversedDomains);
        var reversedRegistrations = new ArrayList<>(reordered.getRegistrations());
        Collections.reverse(reversedRegistrations);
        reordered.setRegistrations(reversedRegistrations);
        GenericApplicationContext context = context();

        var firstBundle = DomainMetadataPropertiesValidator.build(
                first, context.getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class),
                DomainMetadataTestSupport.TEST_CLOCK);
        var reorderedBundle = DomainMetadataPropertiesValidator.build(
                reordered, context.getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class),
                DomainMetadataTestSupport.TEST_CLOCK);
        reordered.getDomains().get("employee").setAliases(List.of("employee", "员工"));
        var aliasChanged = DomainMetadataPropertiesValidator.build(
                reordered, context.getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class),
                DomainMetadataTestSupport.TEST_CLOCK);

        assertThat(reorderedBundle.staticEvidence()).isEqualTo(firstBundle.staticEvidence());
        assertThat(aliasChanged.catalog().canonicalDigest()).isNotEqualTo(firstBundle.catalog().canonicalDigest());
    }

    @Test
    void rejectsDuplicateAliasesRegistrationIdsAndCoverageGaps() {
        GenericApplicationContext context = context();
        var duplicateAlias = DomainMetadataTestSupport.properties();
        duplicateAlias.getDomains().get("employee").setAliases(List.of("employee", "employee"));
        assertThatThrownBy(() -> build(duplicateAlias, context))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("duplicate alias");

        var duplicateId = DomainMetadataTestSupport.properties();
        duplicateId.getRegistrations().get(1)
                .setRegistrationId(duplicateId.getRegistrations().get(0).getRegistrationId());
        assertThatThrownBy(() -> build(duplicateId, context))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("duplicate registrationId");

        var coverageGap = DomainMetadataTestSupport.properties();
        coverageGap.setRegistrations(coverageGap.getRegistrations().subList(1, coverageGap.getRegistrations().size()));
        assertThatThrownBy(() -> build(coverageGap, context))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("coverage");
    }

    @Test
    void rejectsIncompatibleAggregateFunctionsAndInvalidFieldShapes() {
        GenericApplicationContext context = context();
        var incompatibleFunction = DomainMetadataTestSupport.properties();
        incompatibleFunction.getDomains().get("transaction")
                .getRoleCapabilities().get("AGGREGATABLE")
                .setFunctionsByField(Map.of("transType", Set.of(com.dylan.agent.api.enums.AggregateFunction.SUM)));
        assertThatThrownBy(() -> build(incompatibleFunction, context))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("incompatible");

        var fieldBoundCount = DomainMetadataTestSupport.properties();
        fieldBoundCount.getDomains().get("transaction")
                .getRoleCapabilities().get("AGGREGATABLE")
                .setFunctionsByField(Map.of("amount", Set.of(com.dylan.agent.api.enums.AggregateFunction.COUNT)));
        assertThatThrownBy(() -> build(fieldBoundCount, context))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("incompatible");

        var invalidShape = DomainMetadataTestSupport.properties();
        invalidShape.getDomains().get("transaction").getFields().get("amount").setPrecision(2);
        invalidShape.getDomains().get("transaction").getFields().get("amount").setScale(3);
        assertThatThrownBy(() -> build(invalidShape, context))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("scale must not exceed precision");
    }

    @Test
    void rejectsAliasesThatResolveToDifferentCanonicalFacts() {
        GenericApplicationContext context = context();
        var fieldAliasCollision = DomainMetadataTestSupport.properties();
        fieldAliasCollision.getDomains().get("employee").getFields().get("chineseName")
                .setAliases(List.of("sharedAlias"));
        fieldAliasCollision.getDomains().get("employee").getFields().get("memberNo")
                .setAliases(List.of("sharedAlias"));
        assertThatThrownBy(() -> build(fieldAliasCollision, context))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("ambiguous field");

        var domainAliasCollision = DomainMetadataTestSupport.properties();
        domainAliasCollision.getDomains().get("employee").setAliases(List.of("sharedDomainAlias"));
        domainAliasCollision.getDomains().get("transaction").setAliases(List.of("sharedDomainAlias"));
        assertThatThrownBy(() -> build(domainAliasCollision, context))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("ambiguous domain");
    }

    private Object build(DomainMetadataProperties properties, GenericApplicationContext context) {
        return DomainMetadataPropertiesValidator.build(
                properties,
                context.getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class),
                DomainMetadataTestSupport.TEST_CLOCK);
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

    private DomainMetadataProperties documentProperties() {
        DomainMetadataProperties properties = new DomainMetadataProperties();
        properties.setCatalogVersion("catalog-test");
        properties.setAdapterRegistrationVersion("adapter-reg-test");
        properties.setDomains(Map.of("company_policy", documentDomain()));
        DomainMetadataProperties.RegistrationProperties registration =
                new DomainMetadataProperties.RegistrationProperties();
        registration.setRegistrationId("company-policy-document");
        registration.setRole(AdapterRole.DOCUMENT_RETRIEVABLE.value());
        registration.setDomain("company_policy");
        registration.setPortBeanName("documentAgentAdapter");
        registration.setRegistrationVersion("adapter-reg-test");
        properties.setRegistrations(List.of(registration));
        return properties;
    }

    private DomainMetadataProperties.DomainProperties documentDomain() {
        DomainMetadataProperties.DomainProperties domain = new DomainMetadataProperties.DomainProperties();
        domain.setAliases(List.of("公司政策", "company_policy"));
        domain.setDescription("Company policy document corpus for tests.");
        Map<String, DomainMetadataProperties.FieldProperties> fields = new LinkedHashMap<>();
        fields.put("title", field("title", AgentFieldType.STRING));
        fields.put("effectiveDate", field("effectiveDate", AgentFieldType.INSTANT));
        fields.put("page", field("page", AgentFieldType.DECIMAL));
        fields.put("snippet", field("snippet", AgentFieldType.STRING));
        domain.setFields(fields);
        domain.setDefaultSelectFieldsByRole(Map.of(
                AdapterRole.DOCUMENT_RETRIEVABLE.value(), List.of("title", "effectiveDate", "page", "snippet")));
        DomainMetadataProperties.RoleCapabilityProperties capability =
                new DomainMetadataProperties.RoleCapabilityProperties();
        capability.setFields(fields.keySet());
        capability.setSortFields(Set.of("effectiveDate", "title"));
        capability.setOperatorsByField(Map.of(
                "title", Set.of(AgentOperator.CONTAINS, AgentOperator.CONTAINS_ANY),
                "effectiveDate", Set.of(AgentOperator.GT, AgentOperator.LT, AgentOperator.EQ),
                "page", Set.of(AgentOperator.EQ, AgentOperator.GT, AgentOperator.LT),
                "snippet", Set.of(AgentOperator.CONTAINS, AgentOperator.CONTAINS_ANY)));
        domain.setRoleCapabilities(Map.of(AdapterRole.DOCUMENT_RETRIEVABLE.value(), capability));
        return domain;
    }

    private DomainMetadataProperties.FieldProperties field(String field, AgentFieldType type) {
        DomainMetadataProperties.FieldProperties properties = new DomainMetadataProperties.FieldProperties();
        properties.setAliases(List.of(field));
        properties.setDescription(field + " field");
        properties.setType(type);
        if (type == AgentFieldType.INSTANT) {
            properties.setValueFormat("ISO-8601 datetime with timezone");
        }
        if (type == AgentFieldType.DECIMAL) {
            properties.setValueFormat("plain decimal only, precision 10, scale 0, no exponent");
            properties.setPrecision(10);
            properties.setScale(0);
        }
        return properties;
    }

    private static class TestDocumentAdapter implements DocumentRetrievableAdapter {
        @Override
        public CapabilityOperationOutcome<AdapterDocumentRetrievalResult> retrieve(
                DocumentRetrievalCommand request,
                com.dylan.agent.adapter.api.operation.CapabilityOperationContext operationContext) {
            throw new AssertionError("metadata test adapter must not execute");
        }
    }
}
