package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.document.AdapterDocumentResult;
import com.dylan.agent.api.contract.runtime.plan.DocumentAgentPlan;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AgentDocumentSpec;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentGenerationOptions;
import com.dylan.agent.api.plan.DocumentRetrievalOptions;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import com.dylan.agent.api.plan.DocumentSummaryScope;
import com.dylan.agent.invocation.model.CancellationSource;
import com.dylan.agent.kernel.core.ExecutionValidationContext;
import com.dylan.agent.kernel.core.ExecutionValidationContextTestSupport;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;
import com.dylan.agent.kernel.port.model.ExecutionValidationProjection;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView;
import com.dylan.agent.metadata.domain.internal.DomainMetadataProperties;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPropertiesValidator;
import com.dylan.agent.metadata.domain.internal.DomainMetadataStore;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentPlanValidatorTest {

    private static final Instant NOW = Instant.parse("2026-07-01T00:00:00Z");

    @Test
    void acceptsDocumentAnswerPlanWithCitationRequired() {
        var validated = validator().validate(plan(DocumentPlanOperation.ANSWER, true),
                context(DocumentCapabilityIds.ANSWER));

        assertThat(validated.request().getOperation()).isEqualTo(DocumentPlanOperation.ANSWER);
        assertThat(validated.request().getQueryText()).isEqualTo("查询休假政策");
        assertThat(validated.request().isCitationRequired()).isTrue();
        assertThat(validated.request().getTopK()).isEqualTo(5);
    }

    @Test
    void rejectsOperationCapabilityMismatch() {
        assertThatThrownBy(() -> validator().validate(plan(DocumentPlanOperation.ANSWER, true),
                context(DocumentCapabilityIds.SEARCH)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("operation");
    }

    @Test
    void rejectsAnswerWithoutCitation() {
        assertThatThrownBy(() -> validator().validate(plan(DocumentPlanOperation.ANSWER, false),
                context(DocumentCapabilityIds.ANSWER)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("citations");
    }

    @Test
    void rejectsTopKAboveEvidenceLimit() {
        DocumentAgentPlan plan = plan(DocumentPlanOperation.SEARCH, null);
        DocumentRetrievalOptions options = new DocumentRetrievalOptions();
        options.setTopK(9);
        plan.getDocument().setRetrievalOptions(options);

        assertThatThrownBy(() -> validator().validate(plan, context(DocumentCapabilityIds.SEARCH)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("bounds");
    }

    @Test
    void rejectsWhenExecutionScopeAllowsNoRows() {
        assertThatThrownBy(() -> validator().validate(plan(DocumentPlanOperation.SEARCH, null),
                context(DocumentCapabilityIds.SEARCH, 0)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("bounds");
    }

    @Test
    void rejectsInvalidMultiValueFilterShape() {
        DocumentAgentPlan plan = plan(DocumentPlanOperation.SEARCH, null);
        AgentFilter filter = new AgentFilter();
        filter.setField("sourceType");
        filter.setOperator(AgentOperator.CONTAINS_ANY);
        filter.setValue("policy");
        plan.getDocument().setFilters(List.of(filter));

        assertThatThrownBy(() -> validator().validate(plan, context(DocumentCapabilityIds.SEARCH)))
                .hasMessageContaining("不允许 value");
    }

    @Test
    void rejectsSummaryScopeAboveConfiguredLimit() {
        DocumentAgentPlan plan = plan(DocumentPlanOperation.SUMMARIZE, true);
        DocumentSummaryScope scope = new DocumentSummaryScope();
        scope.setMaxSummaryChars(2_001);
        plan.getDocument().setSummaryScope(scope);

        assertThatThrownBy(() -> validator().validate(plan, context(DocumentCapabilityIds.SUMMARIZE)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("summaryScope");
    }

    @Test
    void rejectsHybridOptionsOutOfBounds() {
        DocumentAgentPlan plan = plan(DocumentPlanOperation.ANSWER, true);
        DocumentRetrievalOptions options = new DocumentRetrievalOptions();
        options.setRetrievalMode(DocumentRetrievalMode.HYBRID);
        options.setKeywordK(10_001);
        plan.getDocument().setRetrievalOptions(options);

        assertThatThrownBy(() -> validator().validate(plan, context(DocumentCapabilityIds.ANSWER)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("bounds");
    }

    @Test
    void acceptsHybridCandidatePoolLargerThanFinalPageSize() {
        DocumentAgentPlan plan = plan(DocumentPlanOperation.ANSWER, true);
        DocumentRetrievalOptions options = new DocumentRetrievalOptions();
        options.setRetrievalMode(DocumentRetrievalMode.HYBRID);
        options.setKeywordK(100);
        options.setVectorK(100);
        plan.getDocument().setRetrievalOptions(options);

        var validated = validator().validate(plan, context(DocumentCapabilityIds.ANSWER));

        assertThat(validated.request().getTopK()).isLessThan(100);
        assertThat(validated.request().getHybridOptions().keywordK()).isEqualTo(100);
        assertThat(validated.request().getHybridOptions().vectorK()).isEqualTo(100);
    }

    @Test
    void acceptsGenerationOptionsWithinBudget() {
        DocumentAgentPlan plan = plan(DocumentPlanOperation.ANSWER, true);
        DocumentGenerationOptions options = new DocumentGenerationOptions();
        options.setEnabled(true);
        options.setMaxOutputChars(1200);
        plan.getDocument().setGenerationOptions(options);

        var validated = validator().validate(plan, context(DocumentCapabilityIds.ANSWER));

        assertThat(validated.generationOptions()).isPresent();
        assertThat(validated.generationOptions().orElseThrow().getMaxOutputChars()).isEqualTo(1200);
    }

    private DocumentPlanValidator validator() {
        var properties = DomainMetadataTestSupport.agentProperties();
        return new DocumentPlanValidator(
                properties,
                new FilterNormalizer(properties),
                new FieldConstraintValidator(),
                documentCatalogView());
    }

    private DocumentAgentPlan plan(DocumentPlanOperation operation, Boolean citationRequired) {
        AgentDocumentSpec spec = new AgentDocumentSpec();
        spec.setOperation(operation);
        spec.setQueryText(" 查询休假政策 ");
        spec.setCitationRequired(citationRequired);
        DocumentAgentPlan plan = new DocumentAgentPlan();
        plan.setDocument(spec);
        return plan;
    }

    private ExecutionValidationContext context(String capabilityId) {
        return context(capabilityId, 20);
    }

    private ExecutionValidationContext context(String capabilityId, int maxResultRows) {
        return ExecutionValidationContextTestSupport.documentContext(
                capabilityId,
                executionScope(maxResultRows),
                new ExecutionValidationProjection(
                        AdapterRole.DOCUMENT_RETRIEVABLE,
                        "policy_document",
                        Map.of("sourceType", rule("sourceType")),
                        List.of("sourceType"),
                        Set.of("sourceType"),
                        20,
                        20,
                        "catalog-v1"),
                NOW.plusSeconds(30),
                new CancellationSource().token());
    }

    private ExecutionScope executionScope(int maxResultRows) {
        return new ExecutionScope(
                "user:u-1",
                new DomainMetadataEvidence("catalog-v1", "adapter-v1", "availability", NOW),
                NOW,
                "perm-evidence-1",
                "perm-v1",
                "policy-v1",
                Set.of(DocumentCapabilityIds.SEARCH, DocumentCapabilityIds.ANSWER, DocumentCapabilityIds.SUMMARIZE),
                Set.of("policy_document"),
                Map.of("policy_document", Set.of("sourceType")),
                Map.of(),
                Duration.ofSeconds(30),
                1,
                maxResultRows,
                10_000);
    }

    private ExecutionFieldRule rule(String field) {
        return new ExecutionFieldRule(
                field,
                AgentFieldType.STRING,
                Set.of(AgentOperator.EQ, AgentOperator.CONTAINS,
                        AgentOperator.CONTAINS_ANY, AgentOperator.STARTS_WITH_ANY, AgentOperator.IN),
                Set.of(),
                100,
                null,
                null,
                null);
    }

    private DomainCatalogView documentCatalogView() {
        DomainMetadataProperties properties = DomainMetadataTestSupport.properties();
        Map<String, DomainMetadataProperties.DomainProperties> domains =
                new LinkedHashMap<>(properties.getDomains());
        domains.put("policy_document", documentDomain());
        properties.setDomains(domains);
        var registrations = new ArrayList<>(properties.getRegistrations());
        registrations.add(documentRegistration());
        properties.setRegistrations(registrations);
        DocumentRetrievableAdapter documentAdapter = request -> new AdapterDocumentResult();
        return new DomainCatalogView(new DomainMetadataStore(DomainMetadataPropertiesValidator.build(
                properties,
                Map.of(
                        "employeeAgentAdapter", new DomainMetadataTestSupport.QueryableAggregatableAdapter(),
                        "transactionAgentAdapter", new DomainMetadataTestSupport.QueryableAggregatableAdapter(),
                        "documentAgentAdapter", documentAdapter),
                DomainMetadataTestSupport.TEST_CLOCK)));
    }

    private DomainMetadataProperties.DomainProperties documentDomain() {
        DomainMetadataProperties.DomainProperties domain = new DomainMetadataProperties.DomainProperties();
        domain.setAliases(List.of("政策文档", "policy_document"));
        domain.setDescription("Policy document records for tests.");
        DomainMetadataProperties.FieldProperties sourceType = field("sourceType");
        DomainMetadataProperties.FieldProperties title = field("title");
        domain.setFields(Map.of("sourceType", sourceType, "title", title));
        domain.setDefaultSelectFieldsByRole(Map.of(
                AdapterRole.DOCUMENT_RETRIEVABLE.value(), List.of("sourceType")));
        DomainMetadataProperties.RoleCapabilityProperties capability =
                new DomainMetadataProperties.RoleCapabilityProperties();
        capability.setFields(Set.of("sourceType", "title"));
        capability.setSortFields(Set.of("sourceType"));
        capability.setOperatorsByField(Map.of(
                "sourceType", Set.of(AgentOperator.EQ, AgentOperator.CONTAINS,
                        AgentOperator.CONTAINS_ANY, AgentOperator.STARTS_WITH_ANY, AgentOperator.IN),
                "title", Set.of(AgentOperator.EQ, AgentOperator.CONTAINS)));
        capability.setMaxPageSize(20);
        capability.setMaxResultRows(20);
        domain.setRoleCapabilities(Map.of(AdapterRole.DOCUMENT_RETRIEVABLE.value(), capability));
        return domain;
    }

    private DomainMetadataProperties.FieldProperties field(String name) {
        DomainMetadataProperties.FieldProperties field = new DomainMetadataProperties.FieldProperties();
        field.setAliases(List.of(name));
        field.setDescription(name + " field");
        field.setType(AgentFieldType.STRING);
        field.setMaxLength(100);
        return field;
    }

    private DomainMetadataProperties.RegistrationProperties documentRegistration() {
        DomainMetadataProperties.RegistrationProperties registration =
                new DomainMetadataProperties.RegistrationProperties();
        registration.setRegistrationId("policy-document-retrievable");
        registration.setRole(AdapterRole.DOCUMENT_RETRIEVABLE.value());
        registration.setDomain("policy_document");
        registration.setPortType(DocumentRetrievableAdapter.class);
        registration.setPortBeanName("documentAgentAdapter");
        registration.setCatalogVersion("catalog-test");
        registration.setRegistrationVersion("adapter-reg-test");
        return registration;
    }

}
