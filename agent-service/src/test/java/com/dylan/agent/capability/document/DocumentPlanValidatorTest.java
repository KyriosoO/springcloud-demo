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
import com.dylan.agent.config.AgentProperties;
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
        assertThat(validated.request().getTopK()).isEqualTo(20);
        assertThat(validated.request().getRetrievalMode()).isEqualTo(DocumentRetrievalMode.HYBRID);
        assertThat(validated.request().getContextOptions()).isNotNull();
        assertThat(validated.request().getContextOptions().beforeChunks()).isEqualTo(1);
        assertThat(validated.request().getContextOptions().afterChunks()).isEqualTo(1);
        assertThat(validated.request().getContextOptions().maxContextChars()).isEqualTo(8000);
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
    void rejectsTopKAboveDocumentCandidateLimit() {
        DocumentAgentPlan plan = plan(DocumentPlanOperation.SEARCH, null);
        DocumentRetrievalOptions options = new DocumentRetrievalOptions();
        options.setTopK(21);
        plan.getDocument().setRetrievalOptions(options);

        assertThatThrownBy(() -> validator().validate(plan, context(DocumentCapabilityIds.SEARCH)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("bounds");
    }

    @Test
    void acceptsTopKAboveFinalEvidenceLimitForAnswerCandidates() {
        DocumentAgentPlan plan = plan(DocumentPlanOperation.ANSWER, true);
        DocumentRetrievalOptions options = new DocumentRetrievalOptions();
        options.setTopK(20);
        plan.getDocument().setRetrievalOptions(options);

        var validated = validator().validate(plan, context(DocumentCapabilityIds.ANSWER));

        assertThat(validated.request().getTopK()).isEqualTo(20);
    }

    @Test
    void appliesDomainDefaultRetrievalModeWhenPlanOmitsMode() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        addDefaultProfile(properties);
        properties.getDocument().getRetrievalModeByDomain().put("policy_document", DocumentRetrievalMode.VECTOR);
        var validator = new DocumentPlanValidator(
                properties,
                new FilterNormalizer(properties),
                new FieldConstraintValidator(),
                documentCatalogView());

        var validated = validator.validate(plan(DocumentPlanOperation.ANSWER, true),
                context(DocumentCapabilityIds.ANSWER));

        assertThat(validated.request().getRetrievalMode()).isEqualTo(DocumentRetrievalMode.VECTOR);
    }

    @Test
    void omitsContextWindowForSearchPlans() {
        var validated = validator().validate(plan(DocumentPlanOperation.SEARCH, null),
                context(DocumentCapabilityIds.SEARCH));

        assertThat(validated.request().getContextOptions()).isNull();
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
    void rejectsAclProtectedFieldsInBusinessFilters() {
        DocumentAgentPlan plan = plan(DocumentPlanOperation.SEARCH, null);
        AgentFilter filter = new AgentFilter();
        filter.setField("tenantId");
        filter.setOperator(AgentOperator.EQ);
        filter.setValue("tenant-1");
        plan.getDocument().setFilters(List.of(filter));

        assertThatThrownBy(() -> validator().validate(plan, context(DocumentCapabilityIds.SEARCH)))
                .isInstanceOf(RuntimeException.class)
                .hasMessageContaining("tenantId");
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
    void rejectsNonPositiveSummaryMaxChars() {
        DocumentAgentPlan plan = plan(DocumentPlanOperation.SUMMARIZE, true);
        DocumentSummaryScope scope = new DocumentSummaryScope();
        scope.setMaxSummaryChars(0);
        plan.getDocument().setSummaryScope(scope);

        assertThatThrownBy(() -> validator().validate(plan, context(DocumentCapabilityIds.SUMMARIZE)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("summaryScope");
    }

    @Test
    void rejectsSummarizeWithoutSummaryScope() {
        assertThatThrownBy(() -> validator().validate(plan(DocumentPlanOperation.SUMMARIZE, true),
                context(DocumentCapabilityIds.SUMMARIZE)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("summaryScope");
    }

    @Test
    void mergesSummaryDocumentIdsIntoProtectedFilter() {
        DocumentAgentPlan plan = plan(DocumentPlanOperation.SUMMARIZE, true);
        DocumentSummaryScope scope = new DocumentSummaryScope();
        scope.setDocumentIds(List.of(" doc-1 ", "doc-2", "doc-1"));
        plan.getDocument().setSummaryScope(scope);

        var validated = validator().validate(plan, context(DocumentCapabilityIds.SUMMARIZE));

        assertThat(validated.request().getFilters()).anySatisfy(filter -> {
            assertThat(filter.getField()).isEqualTo("documentId");
            assertThat(filter.getOperator()).isEqualTo(AgentOperator.IN);
            assertThat(filter.getValues()).containsExactly("doc-1", "doc-2");
        });
        assertThat(validated.request().getSummaryScope().getDocumentIds())
                .containsExactly("doc-1", "doc-2");
    }

    @Test
    void acceptsEmptySummaryDocumentIdsForTopicSummary() {
        DocumentAgentPlan plan = plan(DocumentPlanOperation.SUMMARIZE, true);
        DocumentSummaryScope scope = new DocumentSummaryScope();
        scope.setDocumentIds(List.of());
        plan.getDocument().setSummaryScope(scope);

        var validated = validator().validate(plan, context(DocumentCapabilityIds.SUMMARIZE));

        assertThat(validated.request().getFilters()).noneMatch(filter -> "documentId".equals(filter.getField()));
        assertThat(validated.request().getSummaryScope().getDocumentIds()).isEmpty();
    }

    @Test
    void rejectsBlankSummaryDocumentIds() {
        DocumentAgentPlan plan = plan(DocumentPlanOperation.SUMMARIZE, true);
        DocumentSummaryScope scope = new DocumentSummaryScope();
        scope.setDocumentIds(List.of("  "));
        plan.getDocument().setSummaryScope(scope);

        assertThatThrownBy(() -> validator().validate(plan, context(DocumentCapabilityIds.SUMMARIZE)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("documentIds");
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
    void appliesMaterialTypeRetrievalProfileAndFreezesIndexAlias() {
        var properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getRetrievalProfiles().put("policy-default",
                retrievalProfile("policy_document", null, "policy-default", "agent-doc-policy-read"));
        AgentProperties.RetrievalProfileProperties tax = retrievalProfile(
                "policy_document", "tax_policy", "tax-v2", "agent-doc-tax-policy-read");
        tax.setKeywordK(31);
        tax.setExactK(32);
        tax.setPhraseK(33);
        tax.setVectorK(34);
        tax.setRrfK(35);
        tax.setNumCandidates(36);
        tax.setMaxChunksPerDocument(2);
        tax.setEmbeddingProvider("bge");
        tax.setEmbeddingModel("bge-large-zh-v2");
        tax.setEmbeddingDimension(1024);
        tax.setChannels(List.of("bm25", "exact", "phrase", "dense_vector"));
        tax.setChannelWeights(Map.of("BM25", 2.0d));
        tax.getRerank().setEnabled(true);
        tax.getRerank().setTopN(12);
        properties.getDocument().getRetrievalProfiles().put("tax-v2", tax);
        var validator = new DocumentPlanValidator(
                properties,
                new FilterNormalizer(properties),
                new FieldConstraintValidator(),
                documentCatalogView());
        DocumentAgentPlan plan = plan(DocumentPlanOperation.ANSWER, true);
        DocumentRetrievalOptions options = new DocumentRetrievalOptions();
        options.setMaterialType("tax_policy");
        plan.getDocument().setRetrievalOptions(options);

        var validated = validator.validate(plan, context(DocumentCapabilityIds.ANSWER));

        assertThat(validated.request().getMaterialType()).isEqualTo("tax_policy");
        assertThat(validated.request().getRetrievalProfile()).isEqualTo("tax-v2");
        assertThat(validated.request().getProfileVersion()).startsWith("pv-");
        assertThat(validated.request().getIndexAlias()).isEqualTo("agent-doc-tax-policy-read");
        assertThat(validated.request().getHybridOptions().keywordK()).isEqualTo(31);
        assertThat(validated.request().getHybridOptions().exactK()).isEqualTo(32);
        assertThat(validated.request().getHybridOptions().phraseK()).isEqualTo(33);
        assertThat(validated.request().getHybridOptions().vectorK()).isEqualTo(34);
        assertThat(validated.request().getHybridOptions().rrfK()).isEqualTo(35);
        assertThat(validated.request().getHybridOptions().numCandidates()).isEqualTo(36);
        assertThat(validated.request().getHybridOptions().maxChunksPerDocument()).isEqualTo(2);
        assertThat(validated.request().getHybridOptions().channels())
                .containsExactly("BM25", "EXACT", "PHRASE", "DENSE_VECTOR");
        assertThat(validated.request().getHybridOptions().channelWeights()).containsEntry("BM25", 2.0d);
        assertThat(validated.request().getHybridOptions().embeddingProvider()).isEqualTo("bge");
        assertThat(validated.request().getHybridOptions().embeddingModel()).isEqualTo("bge-large-zh-v2");
        assertThat(validated.request().getHybridOptions().embeddingDimension()).isEqualTo(1024);
        assertThat(validated.request().getHybridOptions().rerankEnabled()).isTrue();
        assertThat(validated.request().getHybridOptions().rerankTopN()).isEqualTo(12);
    }

    @Test
    void rejectsRetrievalChannelsOutsideResolvedProfile() {
        var properties = DomainMetadataTestSupport.agentProperties();
        AgentProperties.RetrievalProfileProperties profile = retrievalProfile(
                "policy_document", "tax_policy", "tax-v2", "agent-doc-tax-policy-read");
        profile.setChannels(List.of("BM25", "EXACT"));
        properties.getDocument().getRetrievalProfiles().put("tax-v2", profile);
        var validator = new DocumentPlanValidator(
                properties,
                new FilterNormalizer(properties),
                new FieldConstraintValidator(),
                documentCatalogView());
        DocumentAgentPlan plan = plan(DocumentPlanOperation.SEARCH, null);
        DocumentRetrievalOptions options = new DocumentRetrievalOptions();
        options.setMaterialType("tax_policy");
        options.setRetrievalChannels(List.of("BM25", "DENSE_VECTOR"));
        plan.getDocument().setRetrievalOptions(options);

        assertThatThrownBy(() -> validator.validate(plan, context(DocumentCapabilityIds.SEARCH)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("retrievalChannels");
    }

    @Test
    void rejectsUnknownRequestedRetrievalProfile() {
        DocumentAgentPlan plan = plan(DocumentPlanOperation.SEARCH, null);
        DocumentRetrievalOptions options = new DocumentRetrievalOptions();
        options.setRetrievalProfile("missing-profile");
        plan.getDocument().setRetrievalOptions(options);

        assertThatThrownBy(() -> validator().validate(plan, context(DocumentCapabilityIds.SEARCH)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("retrievalProfile");
    }

    @Test
    void requestLevelRerankCanOnlyDisableProfileRerank() {
        var properties = DomainMetadataTestSupport.agentProperties();
        AgentProperties.RetrievalProfileProperties profile = retrievalProfile(
                "policy_document", "tax_policy", "tax-v2", "agent-doc-tax-policy-read");
        profile.getRerank().setEnabled(true);
        properties.getDocument().getRetrievalProfiles().put("tax-v2", profile);
        var validator = new DocumentPlanValidator(
                properties,
                new FilterNormalizer(properties),
                new FieldConstraintValidator(),
                documentCatalogView());
        DocumentAgentPlan plan = plan(DocumentPlanOperation.ANSWER, true);
        DocumentRetrievalOptions options = new DocumentRetrievalOptions();
        options.setMaterialType("tax_policy");
        options.setRerankEnabled(false);
        plan.getDocument().setRetrievalOptions(options);

        var validated = validator.validate(plan, context(DocumentCapabilityIds.ANSWER));

        assertThat(validated.request().getHybridOptions().rerankEnabled()).isFalse();
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
        addDefaultProfile(properties);
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
        DomainMetadataProperties.FieldProperties documentId = field("documentId");
        domain.setFields(Map.of("sourceType", sourceType, "title", title, "documentId", documentId));
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

    private AgentProperties.RetrievalProfileProperties retrievalProfile(
            String domain,
            String materialType,
            String profile,
            String indexAlias) {
        AgentProperties.RetrievalProfileProperties properties =
                new AgentProperties.RetrievalProfileProperties();
        properties.setDomain(domain);
        properties.setMaterialTypes(List.of(materialType == null ? "policy" : materialType));
        properties.setRetrievalProfile(profile);
        properties.setIndexAlias(indexAlias);
        return properties;
    }

    private void addDefaultProfile(AgentProperties properties) {
        properties.getDocument().getRetrievalProfiles().put("policy-default",
                retrievalProfile("policy_document", "policy", "policy-default", "agent-doc-policy-read"));
    }

}
