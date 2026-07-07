package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedSort;
import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.api.contract.runtime.plan.DocumentAgentPlan;
import com.dylan.agent.api.plan.AgentDocumentSpec;
import com.dylan.agent.api.plan.DocumentGenerationFailurePolicy;
import com.dylan.agent.api.plan.DocumentGenerationOptions;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentRetrievalOptions;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import com.dylan.agent.api.plan.DocumentSummaryScope;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.capability.query.QueryPlanValidator;
import com.dylan.agent.kernel.core.ExecutionValidationContext;
import com.dylan.agent.kernel.validator.CapabilityPlanValidator;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView.DomainView;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;
import com.dylan.agent.adapter.api.document.DocumentHybridOptions;

import java.util.List;
import java.util.ArrayList;
import java.util.LinkedHashSet;
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
        DocumentSummaryScope summaryScope = normalizedSummaryScope(operation, document.getSummaryScope());
        List<ValidatedFilter> effectiveFilters = mergeSummaryScopeFilters(operation, summaryScope, filters);
        if (operation != DocumentPlanOperation.SEARCH
                && Boolean.FALSE.equals(document.getCitationRequired())) {
            throw new IllegalArgumentException("document citations are required for ANSWER/SUMMARIZE");
        }
        boolean citationRequired = operation != DocumentPlanOperation.SEARCH
                || Boolean.TRUE.equals(document.getCitationRequired());
        DocumentRetrievalMode retrievalMode = options == null || options.getRetrievalMode() == null
                ? DocumentRetrievalMode.KEYWORD
                : options.getRetrievalMode();
        DocumentHybridOptions hybridOptions = hybridOptions(options);
        DocumentGenerationOptions generationOptions = validateGenerationOptions(document.getGenerationOptions());
        DocumentRetrievalRequest request = new DocumentRetrievalRequest(
                operation,
                domain,
                queryText,
                effectiveFilters,
                sorts,
                topK,
                page,
                size,
                summaryScope,
                citationRequired,
                retrievalMode,
                List.of(),
                hybridOptions,
                null);
        return new ValidatedDocumentPlan(context.capabilityId(), domain, request, generationOptions);
    }

    private DocumentHybridOptions hybridOptions(DocumentRetrievalOptions options) {
        var hybrid = properties.getDocument().getHybrid();
        int keywordK = bounded(options == null || options.getKeywordK() == null ? hybrid.getKeywordK() : options.getKeywordK(),
                1, 10_000);
        int vectorK = bounded(options == null || options.getVectorK() == null ? hybrid.getVectorK() : options.getVectorK(),
                1, 10_000);
        int rrfK = bounded(options == null || options.getRrfK() == null ? hybrid.getRrfK() : options.getRrfK(),
                1, 1000);
        int numCandidates = bounded(
                options == null || options.getNumCandidates() == null ? hybrid.getNumCandidates() : options.getNumCandidates(),
                1,
                10_000);
        return new DocumentHybridOptions(keywordK, vectorK, rrfK, numCandidates);
    }

    private DocumentGenerationOptions validateGenerationOptions(DocumentGenerationOptions options) {
        if (options == null) {
            return null;
        }
        int maxOutputChars = options.getMaxOutputChars() == null
                ? properties.getDocument().getGeneration().getMaxOutputChars()
                : options.getMaxOutputChars();
        if (maxOutputChars <= 0 || maxOutputChars > properties.getDocument().getGeneration().getMaxOutputChars()) {
            throw new IllegalArgumentException("document generation maxOutputChars out of bounds");
        }
        if (options.getFailurePolicy() == null) {
            options.setFailurePolicy(DocumentGenerationFailurePolicy.FALLBACK_EXTRACTIVE);
        }
        return options;
    }

    private void validateSummaryScope(DocumentPlanOperation operation, DocumentSummaryScope summaryScope) {
        if (operation != DocumentPlanOperation.SUMMARIZE) {
            return;
        }
        if (summaryScope == null) {
            throw new IllegalArgumentException("document summaryScope is required for SUMMARIZE");
        }
        List<String> documentIds = normalizedSummaryDocumentIds(summaryScope);
        if (summaryScope.getDocumentIds() != null
                && !summaryScope.getDocumentIds().isEmpty()
                && documentIds.isEmpty()) {
            throw new IllegalArgumentException("document summaryScope documentIds must not be blank");
        }
        if (summaryScope.getMaxSummaryChars() != null
                && (summaryScope.getMaxSummaryChars() <= 0
                || summaryScope.getMaxSummaryChars() > properties.getDocument().getMaxSummaryChars())) {
            throw new IllegalArgumentException("document summaryScope maxSummaryChars out of bounds");
        }
        if (documentIds.size() > properties.getDocument().getMaxEvidenceCount()) {
            throw new IllegalArgumentException("document summaryScope documentIds out of bounds");
        }
    }

    private List<ValidatedFilter> mergeSummaryScopeFilters(
            DocumentPlanOperation operation,
            DocumentSummaryScope summaryScope,
            List<ValidatedFilter> filters) {
        if (operation != DocumentPlanOperation.SUMMARIZE || summaryScope == null) {
            return filters;
        }
        List<String> documentIds = normalizedSummaryDocumentIds(summaryScope);
        if (documentIds.isEmpty()) {
            return filters;
        }
        if (filters.stream().anyMatch(filter -> "documentId".equals(filter.getField()))) {
            throw new IllegalArgumentException("document summaryScope documentIds cannot be combined with documentId filters");
        }
        List<ValidatedFilter> effective = new ArrayList<>(filters);
        effective.add(new ValidatedFilter("documentId", AgentOperator.IN, null, documentIds));
        return List.copyOf(effective);
    }

    private static List<String> normalizedSummaryDocumentIds(DocumentSummaryScope summaryScope) {
        if (summaryScope == null || summaryScope.getDocumentIds() == null) {
            return List.of();
        }
        LinkedHashSet<String> ids = new LinkedHashSet<>();
        summaryScope.getDocumentIds().stream()
                .filter(Objects::nonNull)
                .map(String::trim)
                .filter(value -> !value.isBlank())
                .forEach(ids::add);
        return List.copyOf(ids);
    }

    private static DocumentSummaryScope normalizedSummaryScope(
            DocumentPlanOperation operation,
            DocumentSummaryScope source) {
        if (operation != DocumentPlanOperation.SUMMARIZE || source == null) {
            return source;
        }
        DocumentSummaryScope target = new DocumentSummaryScope();
        target.setDocumentIds(source.getDocumentIds() == null ? null : normalizedSummaryDocumentIds(source));
        target.setTimeRange(source.getTimeRange());
        target.setSectionHints(source.getSectionHints() == null ? null : List.copyOf(source.getSectionHints()));
        target.setMaxSummaryChars(source.getMaxSummaryChars());
        return target;
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
