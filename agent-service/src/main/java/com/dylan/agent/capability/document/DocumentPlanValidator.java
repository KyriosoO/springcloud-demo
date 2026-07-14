package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedSort;
import com.dylan.agent.adapter.api.document.ValidatedDocumentCallerFilter;
import com.dylan.agent.adapter.api.document.DocumentContextOptions;
import com.dylan.agent.api.contract.runtime.plan.DocumentAgentPlan;
import com.dylan.agent.api.plan.AgentDocumentSpec;
import com.dylan.agent.api.plan.DocumentGenerationFailurePolicy;
import com.dylan.agent.api.plan.DocumentGenerationOptions;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentRetrievalOptions;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import com.dylan.agent.api.plan.DocumentSummaryScope;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.capability.document.profile.DocumentFeaturePolicy;
import com.dylan.agent.capability.document.profile.DocumentPlanningProfileProjection;
import com.dylan.agent.capability.document.profile.DocumentProfileProjectionDigest;
import com.dylan.agent.capability.query.QueryPlanValidator;
import com.dylan.agent.kernel.core.ExecutionValidationContext;
import com.dylan.agent.kernel.validator.CapabilityPlanValidator;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;

import java.util.List;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.Objects;
import java.text.Normalizer;

public class DocumentPlanValidator
        implements CapabilityPlanValidator<DocumentAgentPlan, ValidatedDocumentPlan> {

    private final FilterNormalizer filterNormalizer;
    private final FieldConstraintValidator fieldConstraintValidator;

    public DocumentPlanValidator(
            FilterNormalizer filterNormalizer,
            FieldConstraintValidator fieldConstraintValidator) {
        this.filterNormalizer = Objects.requireNonNull(filterNormalizer, "filterNormalizer must not be null");
        this.fieldConstraintValidator = Objects.requireNonNull(
                fieldConstraintValidator, "fieldConstraintValidator must not be null");
    }

    @Override
    public ValidatedDocumentPlan validate(DocumentAgentPlan rawPlan, ExecutionValidationContext context) {
        Objects.requireNonNull(rawPlan, "rawPlan must not be null");
        Objects.requireNonNull(context, "context must not be null");
        if (!(rawPlan instanceof DocumentRawPlan trustedPlan)) {
            throw new IllegalArgumentException("server-bound DocumentRawPlan required");
        }
        String domain = context.domainProjection().domain()
                .orElseThrow(() -> new IllegalArgumentException("DOCUMENT requires domain projection"));
        DocumentProfileBinding profileBinding = trustedPlan.getProfileBinding();
        DocumentPlanningProfileProjection profile = trustedPlan.getServerProfileProjection();
        var scope = context.executionScope();
        if (!profileBinding.invocationId().equals(scope.invocationId())
                || !profileBinding.requestCorrelationId().equals(scope.requestCorrelationId())
                || !profileBinding.agentProfileRef().equals(scope.agentProfileRef())
                || !profileBinding.resourceLimitReference().equals(scope.resourceLimits().reference())
                || !profileBinding.registrationIdentity().equals(scope.resourceLimits().reference().registrationIdentity())
                || !profileBinding.profileProjectionDigest().equals(DocumentProfileProjectionDigest.compute(profile))
                || !profile.domain().equals(domain)
                || !profileBinding.documentProfileVersion().equals(profile.documentProfileVersion())) {
            throw new IllegalArgumentException("document frozen profile binding mismatch");
        }
        AgentDocumentSpec document = Objects.requireNonNull(rawPlan.getDocument(), "document must not be null");
        DocumentPlanOperation operation = Objects.requireNonNull(document.getOperation(), "document operation must not be null");
        validateCapability(operation, context.capabilityId());
        if (!profile.allowedOperations().contains(operation)) {
            throw new IllegalArgumentException("Runtime document operation is outside the frozen profile projection");
        }
        var limits = context.resourceLimits().require(
                com.dylan.agent.api.contract.common.AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT,
                com.dylan.agent.adapter.api.document.DocumentResourceLimit.class);
        String queryText = normalizeQueryText(document.getQueryText(), limits.input().maxQueryChars());
        List<ValidatedFilter> filters = filterNormalizer.normalizeAll(
                document.getFilters(), context.domainProjection().fieldRules());
        if (filters.size() > limits.input().maxCallerFilterCount()) {
            throw new IllegalArgumentException("document caller filter count exceeds effective limit");
        }
        QueryPlanValidator.validateKernelFilters(filters, context);
        if (filters.stream().map(ValidatedFilter::getField)
                .map(field -> new com.dylan.agent.metadata.domain.port.CanonicalFieldRef(domain, field))
                .anyMatch(field -> !profile.searchableFields().contains(field))) {
            throw new IllegalArgumentException("document filter field is outside the frozen profile projection");
        }
        if (!filters.isEmpty()) {
            fieldConstraintValidator.validateFinalQuery(filters, context.domainProjection().fieldRules());
        }
        List<ValidatedSort> sorts = QueryPlanValidator.toValidatedSorts(document.getSorts());
        QueryPlanValidator.validateKernelSorts(sorts, context);
        if (sorts.stream().map(ValidatedSort::getField)
                .map(field -> new com.dylan.agent.metadata.domain.port.CanonicalFieldRef(domain, field))
                .anyMatch(field -> !profile.searchableFields().contains(field))) {
            throw new IllegalArgumentException("document sort field is outside the frozen profile projection");
        }

        DocumentRetrievalOptions options = document.getRetrievalOptions();
        int topK = bounded(
                options == null || options.getTopK() == null ? defaultCandidateSize(operation, limits) : options.getTopK(),
                1,
                limits.retrieval().maxReturnedDocuments());
        int page = options == null || options.getPage() == null ? 1 : options.getPage();
        int size = bounded(
                options == null || options.getSize() == null ? topK : options.getSize(),
                1,
                limits.retrieval().maxReturnedDocuments());
        if (page <= 0) {
            throw new IllegalArgumentException("document page must be positive");
        }
        validateSummaryScope(operation, document.getSummaryScope(), limits);
        DocumentSummaryScope summaryScope = normalizedSummaryScope(operation, document.getSummaryScope());
        List<ValidatedFilter> effectiveFilters = mergeSummaryScopeFilters(operation, summaryScope, filters);
        if (operation != DocumentPlanOperation.SEARCH
                && Boolean.FALSE.equals(document.getCitationRequired())) {
            throw new IllegalArgumentException("document citations are required for ANSWER/SUMMARIZE");
        }
        boolean citationRequired = operation != DocumentPlanOperation.SEARCH
                || Boolean.TRUE.equals(document.getCitationRequired());
        com.dylan.agent.adapter.api.document.DocumentCorpusKey selectedCorpus = selectedCorpus(profile, options);
        DocumentRetrievalMode retrievalMode = retrievalMode(profile);
        DocumentChannelProfileProjection channelProjection = profile.channelProjection();
        DocumentGenerationOptions generationOptions = validateGenerationOptions(
                operation, document.getGenerationOptions(), limits, profile);
        ValidatedDocumentExecutionParameters parameters = new ValidatedDocumentExecutionParameters(
                operation,
                queryText,
                effectiveFilters.stream().map(this::toDocumentCallerFilter).toList(),
                sorts,
                topK,
                page,
                size,
                summaryScope,
                citationRequired,
                retrievalMode,
                channelProjection,
                contextOptions(operation, limits, profile));
        DocumentExecutionProfileProjection executionProfile = new DocumentExecutionProfileProjection(
                profile.profileName(), profile.documentProfileVersion(),
                profileBinding.profileProjectionDigest(), selectedCorpus, operation,
                profile.allowedChannels(), profile.requiredChannels(), profile.channelWeights(),
                profile.fusionPolicy(), profile.dedupPolicy(), profile.contextPolicy(),
                profile.rewritePolicy(), profile.embeddingPolicy(), profile.rerankPolicy(),
                profile.generationPolicy(), profile.searchableFields(), profile.returnableFields());
        return new ValidatedDocumentPlan(
                context.capabilityId(), domain, selectedCorpus, parameters, generationOptions, executionProfile);
    }

    private ValidatedDocumentCallerFilter toDocumentCallerFilter(ValidatedFilter filter){
        return new ValidatedDocumentCallerFilter(filter.getField(),
                ValidatedDocumentCallerFilter.Operator.valueOf(filter.getOperator().name()),filter.getValue(),filter.getValues());
    }

    private int defaultCandidateSize(DocumentPlanOperation operation, com.dylan.agent.adapter.api.document.DocumentResourceLimit limits) {
        return switch (operation) {
            case ANSWER, SUMMARIZE -> Math.min(20, limits.retrieval().maxReturnedDocuments());
            case SEARCH -> Math.min(5, limits.retrieval().maxReturnedDocuments());
        };
    }

    private DocumentContextOptions contextOptions(
            DocumentPlanOperation operation,
            com.dylan.agent.adapter.api.document.DocumentResourceLimit limits,
            DocumentPlanningProfileProjection profile) {
        if (operation == DocumentPlanOperation.SEARCH) {
            return null;
        }
        return new DocumentContextOptions(
                profile.contextPolicy().beforeChunks(),
                profile.contextPolicy().afterChunks(),
                limits.output().maxContextChars());
    }

    private DocumentRetrievalMode retrievalMode(DocumentPlanningProfileProjection profile) {
        boolean keyword = profile.allowedChannels().contains(
                com.dylan.agent.adapter.api.document.DocumentRetrievalChannel.BM25);
        boolean vector = profile.allowedChannels().contains(
                com.dylan.agent.adapter.api.document.DocumentRetrievalChannel.DENSE_VECTOR);
        if (keyword && vector) return DocumentRetrievalMode.HYBRID;
        if (vector) return DocumentRetrievalMode.VECTOR;
        return DocumentRetrievalMode.KEYWORD;
    }

    private DocumentGenerationOptions validateGenerationOptions(
            DocumentPlanOperation operation,
            DocumentGenerationOptions options,
            com.dylan.agent.adapter.api.document.DocumentResourceLimit limits,
            DocumentPlanningProfileProjection profile) {
        if (operation == DocumentPlanOperation.SEARCH) {
            if (options != null) {
                throw new IllegalArgumentException("SEARCH does not accept generation options");
            }
            return null;
        }
        if (options == null) {
            if (profile.generationPolicy() == DocumentFeaturePolicy.REQUIRED) {
                throw new IllegalArgumentException("required document generation must be requested");
            }
            return null;
        }
        boolean requested = Boolean.TRUE.equals(options.getEnabled());
        if (requested && profile.generationPolicy() == DocumentFeaturePolicy.DISABLED) {
            throw new IllegalArgumentException("document generation is disabled by frozen profile");
        }
        if (!requested && profile.generationPolicy() == DocumentFeaturePolicy.REQUIRED) {
            throw new IllegalArgumentException("required document generation must be requested");
        }
        if (!requested) {
            DocumentGenerationOptions disabled = new DocumentGenerationOptions();
            disabled.setEnabled(false);
            return disabled;
        }
        int operationOutputLimit = operation == DocumentPlanOperation.SUMMARIZE
                ? limits.output().maxSummaryChars()
                : limits.output().maxGeneratedChars();
        int maxOutputChars = options.getMaxOutputChars() == null
                ? operationOutputLimit
                : options.getMaxOutputChars();
        if (maxOutputChars <= 0 || maxOutputChars > operationOutputLimit) {
            throw new IllegalArgumentException("document generation maxOutputChars out of bounds");
        }
        DocumentGenerationOptions validated = new DocumentGenerationOptions();
        validated.setEnabled(true);
        validated.setMaxOutputChars(maxOutputChars);
        validated.setFailurePolicy(options.getFailurePolicy() == null
                ? DocumentGenerationFailurePolicy.FALLBACK_EXTRACTIVE : options.getFailurePolicy());
        return validated;
    }

    private com.dylan.agent.adapter.api.document.DocumentCorpusKey selectedCorpus(
            DocumentPlanningProfileProjection profile,
            DocumentRetrievalOptions options) {
        String materialType = options == null ? null : options.getMaterialType();
        if (materialType != null && !materialType.isBlank()) {
            return profile.allowedCorpora().stream()
                    .filter(corpus -> corpus.materialType().equals(materialType))
                    .findFirst()
                    .orElseThrow(() -> new IllegalArgumentException(
                            "Runtime document materialType is outside the frozen profile projection"));
        }
        if (profile.allowedCorpora().size() != 1) {
            throw new IllegalArgumentException("Runtime document materialType is required for a multi-corpus profile");
        }
        return profile.allowedCorpora().get(0);
    }

    private void validateSummaryScope(DocumentPlanOperation operation, DocumentSummaryScope summaryScope, com.dylan.agent.adapter.api.document.DocumentResourceLimit limits) {
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
                || summaryScope.getMaxSummaryChars() > limits.output().maxSummaryChars())) {
            throw new IllegalArgumentException("document summaryScope maxSummaryChars out of bounds");
        }
        if (documentIds.size() > limits.retrieval().maxReturnedDocuments()) {
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

    private String normalizeQueryText(String queryText, int maxQueryChars) {
        if (queryText == null || queryText.isBlank()) {
            throw new IllegalArgumentException("document queryText must not be blank");
        }
        validateUnicodeAndControls(queryText);
        String normalized = Normalizer.normalize(queryText, Normalizer.Form.NFKC)
                .trim().replaceAll("\\s+", " ");
        if (normalized.isBlank()) {
            throw new IllegalArgumentException("document queryText must not be blank");
        }
        if (normalized.codePointCount(0, normalized.length()) > maxQueryChars) {
            throw new IllegalArgumentException("document queryText is too long");
        }
        return normalized;
    }

    private static void validateUnicodeAndControls(String value) {
        for (int index = 0; index < value.length();) {
            char current = value.charAt(index);
            if (Character.isHighSurrogate(current)) {
                if (index + 1 >= value.length() || !Character.isLowSurrogate(value.charAt(index + 1))) {
                    throw new IllegalArgumentException("document queryText contains invalid Unicode");
                }
            } else if (Character.isLowSurrogate(current)) {
                throw new IllegalArgumentException("document queryText contains invalid Unicode");
            }
            int codePoint = value.codePointAt(index);
            if (Character.isISOControl(codePoint) && !Character.isWhitespace(codePoint)) {
                throw new IllegalArgumentException("document queryText contains control characters");
            }
            index += Character.charCount(codePoint);
        }
    }

    private static int bounded(int value, int min, int max) {
        if (value < min || value > max) {
            throw new IllegalArgumentException("document size out of bounds");
        }
        return value;
    }
}
