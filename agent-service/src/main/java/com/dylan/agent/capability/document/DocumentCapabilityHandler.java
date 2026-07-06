package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.adapter.api.document.AdapterDocumentResult;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.api.plan.DocumentGenerationFailurePolicy;
import com.dylan.agent.api.plan.DocumentGenerationOptions;
import com.dylan.agent.api.context.DocumentCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import com.dylan.agent.api.response.AgentDocumentCitation;
import com.dylan.agent.api.response.AgentDocumentCitationVerification;
import com.dylan.agent.api.response.AgentDocumentCoverage;
import com.dylan.agent.api.response.AgentDocumentHit;
import com.dylan.agent.api.response.AgentDocumentParameters;
import com.dylan.agent.api.response.AgentDocumentResult;
import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.api.response.AgentQuerySortParameter;
import com.dylan.agent.api.response.DocumentAgentResultPayload;
import com.dylan.agent.api.response.DocumentGenerationStatus;
import com.dylan.agent.capability.document.embedding.DocumentEmbeddingPort;
import com.dylan.agent.capability.document.embedding.DocumentEmbeddingRequest;
import com.dylan.agent.capability.document.embedding.DocumentEmbeddingResult;
import com.dylan.agent.capability.document.embedding.DisabledDocumentEmbeddingPort;
import com.dylan.agent.capability.document.generation.CitationVerificationResult;
import com.dylan.agent.capability.document.generation.DocumentCitationVerifier;
import com.dylan.agent.capability.document.generation.DocumentContextBudget;
import com.dylan.agent.capability.document.generation.DocumentContextPackRequest;
import com.dylan.agent.capability.document.generation.DocumentEvidenceContextPacker;
import com.dylan.agent.capability.document.generation.DocumentEvidencePreSecurityFilter;
import com.dylan.agent.capability.document.generation.DocumentGenerationPort;
import com.dylan.agent.capability.document.generation.DocumentGenerationRequest;
import com.dylan.agent.capability.document.generation.DocumentGenerationResult;
import com.dylan.agent.capability.document.generation.DisabledDocumentGenerationPort;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.kernel.core.ExecutionContext;
import com.dylan.agent.kernel.handler.CapabilityHandler;
import com.dylan.agent.kernel.handler.HandlerResult;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

public class DocumentCapabilityHandler
        implements CapabilityHandler<ValidatedDocumentPlan, DocumentAgentResultPayload> {

    private final AgentProperties properties;
    private final DocumentEmbeddingPort embeddingPort;
    private final DocumentEvidencePreSecurityFilter preSecurityFilter;
    private final DocumentEvidenceContextPacker contextPacker;
    private final DocumentGenerationPort generationPort;
    private final DocumentCitationVerifier citationVerifier;

    public DocumentCapabilityHandler() {
        this(new AgentProperties(),
                new DisabledDocumentEmbeddingPort(),
                new DocumentEvidencePreSecurityFilter(),
                new DocumentEvidenceContextPacker(),
                new DisabledDocumentGenerationPort(),
                new DocumentCitationVerifier());
    }

    public DocumentCapabilityHandler(
            AgentProperties properties,
            DocumentEmbeddingPort embeddingPort,
            DocumentEvidencePreSecurityFilter preSecurityFilter,
            DocumentEvidenceContextPacker contextPacker,
            DocumentGenerationPort generationPort,
            DocumentCitationVerifier citationVerifier) {
        this.properties = Objects.requireNonNull(properties, "properties must not be null");
        this.embeddingPort = Objects.requireNonNull(embeddingPort, "embeddingPort must not be null");
        this.preSecurityFilter = Objects.requireNonNull(preSecurityFilter, "preSecurityFilter must not be null");
        this.contextPacker = Objects.requireNonNull(contextPacker, "contextPacker must not be null");
        this.generationPort = Objects.requireNonNull(generationPort, "generationPort must not be null");
        this.citationVerifier = Objects.requireNonNull(citationVerifier, "citationVerifier must not be null");
    }

    @Override
    public HandlerResult<DocumentAgentResultPayload> execute(
            ValidatedDocumentPlan plan,
            ExecutionContext context) {
        DocumentRetrievableAdapter adapter = context.requireAdapter(DocumentRetrievableAdapter.class);
        DocumentRetrievalRequest retrievalRequest = withQueryVectorIfNeeded(plan, context);
        AdapterDocumentResult adapterResult = adapter.retrieve(retrievalRequest);
        DocumentAgentResultPayload payload = new DocumentAgentResultPayload(
                toParameters(plan),
                toResult(plan, adapterResult));
        applyGenerationIfEnabled(plan, retrievalRequest, adapterResult, payload.getDocumentResult(), context);
        return HandlerResult.of(payload, List.of(toContextWrite(plan, adapterResult)));
    }

    private DocumentRetrievalRequest withQueryVectorIfNeeded(ValidatedDocumentPlan plan, ExecutionContext context) {
        DocumentRetrievalRequest request = plan.request();
        DocumentRetrievalMode mode = request.getRetrievalMode();
        if (mode == DocumentRetrievalMode.KEYWORD) {
            return request;
        }
        if (!properties.getDocument().getEmbedding().isEnabled()) {
            if (mode == DocumentRetrievalMode.HYBRID) {
                return copyRequest(request, DocumentRetrievalMode.KEYWORD, List.of());
            }
            throw new IllegalStateException("document vector retrieval requires enabled embedding");
        }
        var embedding = embedOrFallback(plan, context, mode);
        if (embedding == null) {
            return copyRequest(request, DocumentRetrievalMode.KEYWORD, List.of());
        }
        if (embedding.queryVector() == null || embedding.queryVector().isEmpty()) {
            if (mode == DocumentRetrievalMode.HYBRID) {
                return copyRequest(request, DocumentRetrievalMode.KEYWORD, List.of());
            }
            throw new IllegalStateException("document embedding returned empty queryVector");
        }
        int configuredDimension = properties.getDocument().getEmbedding().getDimension();
        if (configuredDimension > 0 && embedding.dimension() != configuredDimension) {
            throw new IllegalStateException("document embedding dimension mismatch");
        }
        return copyRequest(request, mode, embedding.queryVector());
    }

    private DocumentEmbeddingResult embedOrFallback(
            ValidatedDocumentPlan plan,
            ExecutionContext context,
            DocumentRetrievalMode mode) {
        DocumentRetrievalRequest request = plan.request();
        try {
            return embeddingPort.embed(new DocumentEmbeddingRequest(
                    context.invocationId(),
                    request.getQueryText(),
                    request.getDomain(),
                    properties.getDocument().getEmbedding().getModel(),
                    context.absoluteDeadline()));
        } catch (RuntimeException ex) {
            if (mode == DocumentRetrievalMode.HYBRID) {
                return null;
            }
            throw ex;
        }
    }

    private DocumentRetrievalRequest copyRequest(
            DocumentRetrievalRequest source,
            DocumentRetrievalMode mode,
            List<Double> queryVector) {
        return new DocumentRetrievalRequest(
                source.getOperation(),
                source.getDomain(),
                source.getQueryText(),
                source.getFilters(),
                source.getSorts(),
                source.getTopK(),
                source.getPage(),
                source.getSize(),
                source.getSummaryScope(),
                source.isCitationRequired(),
                mode,
                queryVector,
                source.getHybridOptions(),
                source.getContextOptions());
    }

    private static AgentDocumentParameters toParameters(ValidatedDocumentPlan plan) {
        AgentDocumentParameters parameters = new AgentDocumentParameters();
        parameters.setDomain(plan.domain().orElseThrow());
        parameters.setOperation(plan.request().getOperation().name());
        parameters.setQueryText(plan.request().getQueryText());
        parameters.setFilters(plan.request().getFilters().stream()
                .map(DocumentCapabilityHandler::toFilterParameter)
                .toList());
        parameters.setSorts(plan.request().getSorts().stream()
                .map(sort -> {
                    AgentQuerySortParameter parameter = new AgentQuerySortParameter();
                    parameter.setField(sort.getField());
                    parameter.setDirection(sort.getDirection());
                    return parameter;
                })
                .toList());
        parameters.setTopK(plan.request().getTopK());
        parameters.setSummaryScope(plan.request().getSummaryScope() == null ? null : "CUSTOM");
        return parameters;
    }

    private static AgentDocumentResult toResult(ValidatedDocumentPlan plan, AdapterDocumentResult adapterResult) {
        AdapterDocumentResult safeResult = adapterResult == null ? new AdapterDocumentResult() : adapterResult;
        List<AdapterDocumentEvidence> hits = nonNullEvidence(safeResult.getHits());
        List<AdapterDocumentEvidence> citations = resolvedCitations(safeResult);
        AgentDocumentResult result = new AgentDocumentResult();
        result.setHits(hits.stream().map(DocumentCapabilityHandler::toHit).toList());
        result.setCitations(citations.stream().map(DocumentCapabilityHandler::toCitation).toList());
        result.setPartial(safeResult.isPartial());
        result.setCandidateAnswerText(safeResult.getCandidateAnswerText());
        result.setCandidateSummaryText(safeResult.getCandidateSummaryText());
        result.setCandidateSummaryBullets(safeResult.getCandidateSummaryBullets());
        result.setGenerationStatus(DocumentGenerationStatus.DISABLED);
        AgentDocumentCoverage coverage = new AgentDocumentCoverage();
        coverage.setRequestedDocumentCount(
                safeResult.getRequestedDocumentCount() > 0 ? safeResult.getRequestedDocumentCount() : plan.request().getTopK());
        coverage.setCoveredDocumentCount(safeResult.getCoveredDocumentCount());
        coverage.setEvidenceCount(citations.size());
        coverage.setTruncated(citations.size() > plan.request().getTopK());
        result.setCoverage(coverage);
        return result;
    }

    private void applyGenerationIfEnabled(
            ValidatedDocumentPlan plan,
            DocumentRetrievalRequest retrievalRequest,
            AdapterDocumentResult adapterResult,
            AgentDocumentResult result,
            ExecutionContext context) {
        if (retrievalRequest.getOperation() == com.dylan.agent.api.plan.DocumentPlanOperation.SEARCH) {
            result.setGenerationStatus(DocumentGenerationStatus.SKIPPED);
            return;
        }
        DocumentGenerationOptions options = plan.generationOptions().orElse(null);
        boolean requested = options != null && Boolean.TRUE.equals(options.getEnabled());
        if (!properties.getDocument().getGeneration().isEnabled() || !requested) {
            result.setGenerationStatus(DocumentGenerationStatus.DISABLED);
            return;
        }
        List<AdapterDocumentEvidence> filteredEvidence = preSecurityFilter.filter(
                resolvedCitations(adapterResult),
                context.executionScope(),
                retrievalRequest.getDomain());
        if (filteredEvidence.isEmpty()) {
            result.setGenerationStatus(DocumentGenerationStatus.SKIPPED);
            return;
        }
        DocumentContextBudget budget = new DocumentContextBudget(
                properties.getDocument().getGeneration().getMaxContextChars(),
                properties.getDocument().getGeneration().getMaxEvidenceChars(),
                properties.getDocument().getMaxEvidenceCount(),
                resolveMaxOutputChars(options));
        var evidencePackage = contextPacker.pack(new DocumentContextPackRequest(plan, filteredEvidence, context, budget));
        try {
            DocumentGenerationResult generated = generationPort.generate(new DocumentGenerationRequest(
                    retrievalRequest.getOperation(),
                    retrievalRequest.getQueryText(),
                    evidencePackage,
                    budget.maxOutputChars(),
                    context.absoluteDeadline()));
            CitationVerificationResult verification = citationVerifier.verify(generated, evidencePackage);
            result.setCitationVerification(toApiVerification(verification));
            result.setGroundingStatus(verification.status());
            if (verification.invalidCitationIds().isEmpty()) {
                result.setCandidateAnswerText(generated.answerText());
                result.setCandidateSummaryText(generated.summaryText());
                result.setCandidateSummaryBullets(generated.summaryBullets());
                result.setGenerationStatus(DocumentGenerationStatus.SUCCEEDED);
            } else {
                fallbackOrFail(result, options, verification.fallbackReason());
            }
        } catch (RuntimeException ex) {
            fallbackOrFail(result, options, ex.getClass().getSimpleName());
        }
    }

    private int resolveMaxOutputChars(DocumentGenerationOptions options) {
        return options.getMaxOutputChars() == null
                ? properties.getDocument().getGeneration().getMaxOutputChars()
                : options.getMaxOutputChars();
    }

    private void fallbackOrFail(AgentDocumentResult result, DocumentGenerationOptions options, String reason) {
        AgentDocumentCitationVerification verification = result.getCitationVerification();
        if (verification == null) {
            verification = new AgentDocumentCitationVerification();
            verification.setInvalidCitationIds(List.of());
            verification.setFallbackReason(reason);
            result.setCitationVerification(verification);
        }
        if (options.getFailurePolicy() == DocumentGenerationFailurePolicy.REFUSE) {
            result.setGenerationStatus(DocumentGenerationStatus.FAILED);
        } else {
            result.setGenerationStatus(DocumentGenerationStatus.FALLBACK);
        }
    }

    private AgentDocumentCitationVerification toApiVerification(CitationVerificationResult verification) {
        AgentDocumentCitationVerification api = new AgentDocumentCitationVerification();
        api.setStatus(verification.status());
        api.setRemovedClaimCount(verification.removedClaimCount());
        api.setInvalidCitationIds(verification.invalidCitationIds());
        api.setFallbackReason(verification.fallbackReason());
        return api;
    }

    private static ContextWriteCandidate toContextWrite(ValidatedDocumentPlan plan, AdapterDocumentResult adapterResult) {
        AdapterDocumentResult safeResult = adapterResult == null ? new AdapterDocumentResult() : adapterResult;
        List<String> citationIds = resolvedCitations(safeResult).stream()
                .map(DocumentCapabilityHandler::citationId)
                .filter(Objects::nonNull)
                .toList();
        return new ContextWriteCandidate(
                RuntimeContextType.DOCUMENT,
                AgentExecutionContracts.DOCUMENT_CONTEXT,
                new DocumentCapabilityContextPayload(
                        plan.request().getOperation().name(),
                        plan.domain().orElseThrow(),
                        plan.request().getQueryText(),
                        plan.request().getFilters().stream()
                                .map(DocumentCapabilityHandler::toAgentFilter)
                                .toList(),
                        citationIds,
                        plan.request().getTopK()));
    }

    private static AgentDocumentHit toHit(AdapterDocumentEvidence evidence) {
        AgentDocumentHit hit = new AgentDocumentHit();
        hit.setDocumentId(evidence.getDocumentId());
        hit.setTitle(evidence.getTitle());
        hit.setSourceType(evidence.getSourceType());
        hit.setSnippet(evidence.getSnippet());
        hit.setScore(evidence.getScore());
        String citationId = citationId(evidence);
        hit.setCitationIds(citationId == null ? List.of() : List.of(citationId));
        return hit;
    }

    private static AgentDocumentCitation toCitation(AdapterDocumentEvidence evidence) {
        AgentDocumentCitation citation = new AgentDocumentCitation();
        citation.setCitationId(citationId(evidence));
        citation.setDocumentId(evidence.getDocumentId());
        citation.setTitle(evidence.getTitle());
        citation.setSection(evidence.getSection());
        citation.setPage(evidence.getPage());
        citation.setSourceUri(evidence.getSourceUri());
        citation.setSnippet(evidence.getSnippet());
        citation.setChunkIndex(evidence.getChunkIndex());
        citation.setCharStart(evidence.getCharStart());
        citation.setCharEnd(evidence.getCharEnd());
        return citation;
    }

    private static String citationId(AdapterDocumentEvidence evidence) {
        if (evidence == null) {
            return null;
        }
        if (evidence.getChunkId() != null && !evidence.getChunkId().isBlank()) {
            return evidence.getChunkId();
        }
        return evidence.getDocumentId();
    }

    private static List<AdapterDocumentEvidence> resolvedCitations(AdapterDocumentResult result) {
        if (result.getCitations() == null) {
            return nonNullEvidence(result.getHits());
        }
        return nonNullEvidence(result.getCitations());
    }

    private static List<AdapterDocumentEvidence> nonNullEvidence(List<AdapterDocumentEvidence> values) {
        return nullToEmpty(values).stream()
                .filter(Objects::nonNull)
                .toList();
    }

    private static AgentQueryFilterParameter toFilterParameter(ValidatedFilter filter) {
        AgentQueryFilterParameter parameter = new AgentQueryFilterParameter();
        parameter.setField(filter.getField());
        parameter.setOperator(filter.getOperator());
        parameter.setValue(filter.getValue());
        parameter.setValues(filter.getValues().isEmpty() ? null : filter.getValues());
        return parameter;
    }

    private static AgentFilter toAgentFilter(ValidatedFilter filter) {
        AgentFilter agentFilter = new AgentFilter();
        agentFilter.setField(filter.getField());
        agentFilter.setOperator(filter.getOperator());
        agentFilter.setValue(filter.getValue());
        agentFilter.setValues(filter.getValues());
        return agentFilter;
    }

    private static <T> List<T> nullToEmpty(List<T> values) {
        return values == null ? List.of() : values;
    }
}
