package com.dylan.agent.capability.document;

import com.dylan.agent.api.contract.runtime.plan.DocumentAgentPlan;
import com.dylan.agent.adapter.api.operation.ResourceLimitReference;
import com.dylan.agent.api.plan.*;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.capability.document.profile.DocumentPlanningProfileProjector;
import com.dylan.agent.capability.document.profile.DocumentProfileProjectionDigest;
import com.dylan.agent.kernel.core.DocumentCapabilityHandlerTestSupport;
import com.dylan.agent.planning.filter.*;
import org.junit.jupiter.api.Test;
import java.util.List;
import com.fasterxml.jackson.databind.ObjectMapper;
import static org.assertj.core.api.Assertions.*;

class DocumentPlanValidatorTest {
    @Test
    void freezesExactProfileAndUsesTypedResourceLimits() {
        DocumentPlanValidator validator = validator();
        var context = DocumentCapabilityHandlerTestSupport.validationContext("document.search", "policy_document");
        ValidatedDocumentPlan validated = validator.validate(plan("policy_document", 30, context), context);

        assertThat(validated.profile().profileName()).isEqualTo("tax-policy-v3");
        assertThat(validated.selectedCorpus().materialType()).isEqualTo("policy_document");
        assertThat(validated.parameters().topK()).isEqualTo(30);
        assertThat(validated.parameters().normalizedQuery()).isNotBlank();
    }

    @Test
    void rejectsUnknownCorpusAndCountAboveEffectiveLimit() {
        DocumentPlanValidator validator = validator();
        var context = DocumentCapabilityHandlerTestSupport.validationContext("document.search", "policy_document");
        assertThatThrownBy(() -> validator.validate(plan("other_material", 5, context), context))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("frozen profile projection");
        assertThatThrownBy(() -> validator.validate(plan("policy_document", 31, context), context))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void normalizesNfkcWhitespaceAndCountsUnicodeCodePoints() {
        DocumentPlanValidator validator = validator();
        var context = DocumentCapabilityHandlerTestSupport.validationContext("document.search", "policy_document");
        DocumentAgentPlan raw = plan("policy_document", 5, context);
        raw.getDocument().setQueryText("  税收\tＡ😀  优惠  ");

        ValidatedDocumentPlan validated = validator.validate(raw, context);

        assertThat(validated.parameters().normalizedQuery()).isEqualTo("税收 A😀 优惠");
    }

    @Test
    void rejectsControlInvalidUnicodeAndSearchGenerationOptions() {
        DocumentPlanValidator validator = validator();
        var context = DocumentCapabilityHandlerTestSupport.validationContext("document.search", "policy_document");
        DocumentAgentPlan control = plan("policy_document", 5, context);
        control.getDocument().setQueryText("税收\u0000优惠");
        assertThatThrownBy(() -> validator.validate(control, context))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("control");

        DocumentAgentPlan invalidUnicode = plan("policy_document", 5, context);
        invalidUnicode.getDocument().setQueryText("税收\uD83D优惠");
        assertThatThrownBy(() -> validator.validate(invalidUnicode, context))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("Unicode");

        DocumentAgentPlan generation = plan("policy_document", 5, context);
        generation.getDocument().setGenerationOptions(new com.dylan.agent.api.plan.DocumentGenerationOptions());
        assertThatThrownBy(() -> validator.validate(generation, context))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("SEARCH");
    }

    private static DocumentPlanValidator validator() {
        AgentProperties agentProperties = new AgentProperties();
        AgentProperties.QueryProperties query = new AgentProperties.QueryProperties();
        query.setMaxFilters(20); query.setMaxInValues(100); query.setMaxFilterValueLength(500);
        agentProperties.setQuery(query);
        return new DocumentPlanValidator(new FilterNormalizer(agentProperties), new FieldConstraintValidator());
    }

    private static DocumentAgentPlan plan(String materialType, int topK,
                                          com.dylan.agent.kernel.core.ExecutionValidationContext context) {
        DocumentRetrievalOptions options = new DocumentRetrievalOptions();
        options.setMaterialType(materialType); options.setTopK(topK);
        AgentDocumentSpec spec = new AgentDocumentSpec();
        spec.setOperation(DocumentPlanOperation.SEARCH); spec.setQueryText("税收优惠"); spec.setRetrievalOptions(options);
        DocumentAgentPlan plan = new DocumentAgentPlan(); plan.setDocument(spec);
        var assets = DocumentProfileTestSupport.assets();
        var selection = DocumentProfileTestSupport.selection(assets, DocumentPlanOperation.SEARCH);
        var scope = context.executionScope();
        ResourceLimitReference reference = scope.resourceLimits().reference();
        var limits = context.resourceLimits().require(
                com.dylan.agent.api.contract.common.AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT,
                com.dylan.agent.adapter.api.document.DocumentResourceLimit.class);
        var profile = new DocumentPlanningProfileProjector().project(
                selection, limits, DocumentCapabilityIds.SEARCH);
        DocumentProfileBinding binding = new DocumentProfileBinding(scope.invocationId(), scope.requestCorrelationId(),
                reference.registrationIdentity(), scope.agentProfileRef(), profile.documentProfileVersion(),
                reference, DocumentProfileProjectionDigest.compute(profile));
        return new DocumentRawPlan(plan, binding, profile, new ObjectMapper());
    }
}
