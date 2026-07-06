package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedSort;
import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.api.contract.runtime.plan.DocumentAgentPlan;
import com.dylan.agent.api.plan.AgentDocumentSpec;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentRetrievalOptions;
import com.dylan.agent.api.plan.DocumentSummaryScope;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.capability.query.QueryPlanValidator;
import com.dylan.agent.kernel.core.ExecutionValidationContext;
import com.dylan.agent.kernel.validator.CapabilityPlanValidator;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView.DomainView;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;

import java.util.List;
import java.util.Objects;

public class DocumentPlanValidator
        implements CapabilityPlanValidator<DocumentAgentPlan, ValidatedDocumentPlan> {

    private final AgentProperties properties;
    private final FilterNormalizer filterNormalizer;
    private final FieldConstraintValidator fieldConstraintValidator;
    private final DomainCatalogView domainCatalogView;

    public DocumentPlanValidator(
            AgentProperties properties,
            FilterNormalizer filterNormalizer,
            FieldConstraintValidator fieldConstraintValidator,
            DomainCatalogView domainCatalogView) {
        this.properties = Objects.requireNonNull(properties, "properties must not be null");
        this.filterNormalizer = Objects.requireNonNull(filterNormalizer, "filterNormalizer must not be null");
        this.fieldConstraintValidator = Objects.requireNonNull(
                fieldConstraintValidator, "fieldConstraintValidator must not be null");
        this.domainCatalogView = Objects.requireNonNull(domainCatalogView, "domainCatalogView must not be null");
    }

    @Override
    public ValidatedDocumentPlan validate(DocumentAgentPlan rawPlan, ExecutionValidationContext context) {
        Objects.requireNonNull(rawPlan, "rawPlan must not be null");
        Objects.requireNonNull(context, "context must not be null");
        String domain = context.domainProjection().domain()
                .orElseThrow(() -> new IllegalArgumentException("DOCUMENT requires domain projection"));
        AgentDocumentSpec document = Objects.requireNonNull(rawPlan.getDocument(), "document must not be null");
        DocumentPlanOperation operation = Objects.requireNonNull(document.getOperation(), "document operation must not be null");
        validateCapability(operation, context.capabilityId());
        String queryText = normalizeQueryText(document.getQueryText());
        DomainView documentDomain = domainCatalogView.requireDomain(domain, AdapterRole.DOCUMENT_RETRIEVABLE);
        List<ValidatedFilter> filters = filterNormalizer.normalizeAll(document.getFilters(), documentDomain);
        QueryPlanValidator.validateKernelFilters(filters, context);
        if (!filters.isEmpty()) {
            fieldConstraintValidator.validateFinalQuery(filters, documentDomain);
        }
        List<ValidatedSort> sorts = QueryPlanValidator.toValidatedSorts(document.getSorts());
        QueryPlanValidator.validateKernelSorts(sorts, context);

        DocumentRetrievalOptions options = document.getRetrievalOptions();
        int topK = bounded(
                options == null || options.getTopK() == null ? properties.getDocument().getDefaultSize() : options.getTopK(),
                1,
                maxDocumentSize(context));
        int page = options == null || options.getPage() == null ? 1 : options.getPage();
        int size = bounded(
                options == null || options.getSize() == null ? topK : options.getSize(),
                1,
                maxDocumentSize(context));
        if (page <= 0) {
            throw new IllegalArgumentException("document page must be positive");
        }
        validateSummaryScope(operation, document.getSummaryScope());
        if (operation != DocumentPlanOperation.SEARCH
                && Boolean.FALSE.equals(document.getCitationRequired())) {
            throw new IllegalArgumentException("document citations are required for ANSWER/SUMMARIZE");
        }
        boolean citationRequired = operation != DocumentPlanOperation.SEARCH
                || Boolean.TRUE.equals(document.getCitationRequired());
        DocumentRetrievalRequest request = new DocumentRetrievalRequest(
                operation,
                domain,
                queryText,
                filters,
                sorts,
                topK,
                page,
                size,
                document.getSummaryScope(),
                citationRequired);
        return new ValidatedDocumentPlan(context.capabilityId(), domain, request);
    }

    private void validateSummaryScope(DocumentPlanOperation operation, DocumentSummaryScope summaryScope) {
        if (operation != DocumentPlanOperation.SUMMARIZE) {
            return;
        }
        if (summaryScope == null) {
            throw new IllegalArgumentException("document summaryScope is required for SUMMARIZE");
        }
        if (summaryScope.getMaxSummaryChars() != null
                && summaryScope.getMaxSummaryChars() > properties.getDocument().getMaxSummaryChars()) {
            throw new IllegalArgumentException("document summaryScope maxSummaryChars out of bounds");
        }
        if (summaryScope.getDocumentIds() != null
                && summaryScope.getDocumentIds().size() > properties.getDocument().getMaxEvidenceCount()) {
            throw new IllegalArgumentException("document summaryScope documentIds out of bounds");
        }
    }

    private void validateCapability(DocumentPlanOperation operation, String capabilityId) {
        String expected = switch (operation) {
            case SEARCH -> DocumentCapabilityIds.SEARCH;
            case ANSWER -> DocumentCapabilityIds.ANSWER;
            case SUMMARIZE -> DocumentCapabilityIds.SUMMARIZE;
        };
        if (!expected.equals(capabilityId)) {
            throw new IllegalArgumentException("document operation does not match capabilityId");
        }
    }

    private String normalizeQueryText(String queryText) {
        if (queryText == null || queryText.isBlank()) {
            throw new IllegalArgumentException("document queryText must not be blank");
        }
        String normalized = queryText.trim();
        if (normalized.length() > properties.getDocument().getMaxQueryTextLength()) {
            throw new IllegalArgumentException("document queryText is too long");
        }
        return normalized;
    }

    private int maxDocumentSize(ExecutionValidationContext context) {
        int max = properties.getDocument().getMaxEvidenceCount();
        max = Math.min(max, properties.getDocument().getMaxSize());
        max = Math.min(max, context.domainProjection().maxPageSize());
        max = Math.min(max, context.executionScope().maxResultRows());
        return max;
    }

    private static int bounded(int value, int min, int max) {
        if (value < min || value > max) {
            throw new IllegalArgumentException("document size out of bounds");
        }
        return value;
    }
}
