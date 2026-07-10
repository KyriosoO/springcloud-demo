package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.adapter.api.document.AdapterDocumentResult;
import com.dylan.agent.adapter.api.document.AdapterDocumentRetrievalDiagnostics;
import com.dylan.agent.adapter.api.document.DocumentHybridOptions;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.adapter.api.document.generation.DocumentContextBudget;
import com.dylan.agent.adapter.api.document.generation.DocumentGenerationRequest;
import com.dylan.agent.adapter.api.document.generation.DocumentGenerationResult;
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
import com.dylan.agent.api.response.GroundingStatus;
import com.dylan.agent.capability.document.embedding.DocumentEmbeddingPort;
import com.dylan.agent.capability.document.embedding.DocumentEmbeddingRequest;
import com.dylan.agent.capability.document.embedding.DocumentEmbeddingResult;
import com.dylan.agent.capability.document.embedding.DisabledDocumentEmbeddingPort;
import com.dylan.agent.capability.document.acl.DisabledDocumentAclScopePort;
import com.dylan.agent.capability.document.acl.DocumentAclScopePort;
import com.dylan.agent.capability.document.acl.DocumentAclScopeRequest;
import com.dylan.agent.capability.document.generation.CitationVerificationResult;
import com.dylan.agent.capability.document.generation.DocumentCitationVerifier;
import com.dylan.agent.capability.document.generation.DocumentContextPackRequest;
import com.dylan.agent.capability.document.generation.DocumentEvidenceContextPacker;
import com.dylan.agent.capability.document.generation.DocumentEvidencePreSecurityFilter;
import com.dylan.agent.capability.document.generation.DocumentGenerationPort;
import com.dylan.agent.capability.document.generation.DisabledDocumentGenerationPort;
import com.dylan.agent.capability.document.rerank.DisabledDocumentRerankPort;
import com.dylan.agent.capability.document.rerank.DocumentRerankPort;
import com.dylan.agent.capability.document.rerank.DocumentRerankRequest;
import com.dylan.agent.capability.document.rewrite.DisabledDocumentQueryRewritePort;
import com.dylan.agent.capability.document.rewrite.DocumentQueryRewritePort;
import com.dylan.agent.capability.document.rewrite.DocumentRewriteRequest;
import com.dylan.agent.capability.document.rewrite.DocumentRewriteResponse;
import com.dylan.agent.capability.document.rewrite.QueryVariants;
import com.dylan.agent.capability.document.rewrite.RewriteCandidateNormalizer;
import com.dylan.agent.capability.document.security.DocumentRevocationGuard;
import com.dylan.agent.capability.document.security.DocumentRevocationDecision;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.kernel.core.ExecutionContext;
import com.dylan.agent.kernel.handler.CapabilityHandler;
import com.dylan.agent.kernel.handler.HandlerResult;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.math.BigDecimal;
import java.time.Duration;
import java.time.Instant;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public class DocumentCapabilityHandler
        implements CapabilityHandler<ValidatedDocumentPlan, DocumentAgentResultPayload> {

    private static final Logger log = LoggerFactory.getLogger(DocumentCapabilityHandler.class);
    private static final Set<String> RERANK_METADATA_ALLOWLIST = Set.of(
            "sourceType",
            "materialType",
            "retrievalProfile",
            "documentNo",
            "issuer",
            "taxType",
            "validityStatus",
            "effectiveDate",
            "channelRanks",
            "channelScores",
            "hitFields",
            "dedupGroupSize",
            "representativeChunk",
            "rerankScore",
            "rerankReasonCode");

    private final AgentProperties properties;
    private final DocumentEmbeddingPort embeddingPort;
    private final DocumentAclScopePort aclScopePort;
    private final DocumentRevocationGuard revocationGuard;
    private final DocumentEvidencePreSecurityFilter preSecurityFilter;
    private final DocumentEvidenceContextPacker contextPacker;
    private final DocumentGenerationPort generationPort;
    private final DocumentCitationVerifier citationVerifier;
    private final DocumentObservabilitySupport observabilitySupport;
    private final DocumentRerankPort rerankPort;
    private final DocumentQueryRewritePort rewritePort;
    private final RewriteCandidateNormalizer rewriteCandidateNormalizer;
    private final DocumentRuleExtractor ruleExtractor;

    public DocumentCapabilityHandler() {
        this(new AgentProperties(),
                new DisabledDocumentEmbeddingPort(),
                new DisabledDocumentAclScopePort(),
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
        this(properties,
                embeddingPort,
                new DisabledDocumentAclScopePort(),
                preSecurityFilter,
                contextPacker,
                generationPort,
                citationVerifier);
    }

    public DocumentCapabilityHandler(
            AgentProperties properties,
            DocumentEmbeddingPort embeddingPort,
            DocumentAclScopePort aclScopePort,
            DocumentEvidencePreSecurityFilter preSecurityFilter,
            DocumentEvidenceContextPacker contextPacker,
            DocumentGenerationPort generationPort,
            DocumentCitationVerifier citationVerifier) {
        this(properties,
                embeddingPort,
                aclScopePort,
                new DocumentRevocationGuard(properties),
                preSecurityFilter,
                contextPacker,
                generationPort,
                citationVerifier);
    }

    public DocumentCapabilityHandler(
            AgentProperties properties,
            DocumentEmbeddingPort embeddingPort,
            DocumentAclScopePort aclScopePort,
            DocumentRevocationGuard revocationGuard,
            DocumentEvidencePreSecurityFilter preSecurityFilter,
            DocumentEvidenceContextPacker contextPacker,
            DocumentGenerationPort generationPort,
            DocumentCitationVerifier citationVerifier) {
        this(properties,
                embeddingPort,
                aclScopePort,
                revocationGuard,
                preSecurityFilter,
                contextPacker,
                generationPort,
                citationVerifier,
                null,
                new DisabledDocumentRerankPort());
    }

    public DocumentCapabilityHandler(
            AgentProperties properties,
            DocumentEmbeddingPort embeddingPort,
            DocumentAclScopePort aclScopePort,
            DocumentRevocationGuard revocationGuard,
            DocumentEvidencePreSecurityFilter preSecurityFilter,
            DocumentEvidenceContextPacker contextPacker,
            DocumentGenerationPort generationPort,
            DocumentCitationVerifier citationVerifier,
            DocumentObservabilitySupport observabilitySupport) {
        this(properties,
                embeddingPort,
                aclScopePort,
                revocationGuard,
                preSecurityFilter,
                contextPacker,
                generationPort,
                citationVerifier,
                observabilitySupport,
                new DisabledDocumentRerankPort());
    }

    public DocumentCapabilityHandler(
            AgentProperties properties,
            DocumentEmbeddingPort embeddingPort,
            DocumentAclScopePort aclScopePort,
            DocumentRevocationGuard revocationGuard,
            DocumentEvidencePreSecurityFilter preSecurityFilter,
            DocumentEvidenceContextPacker contextPacker,
            DocumentGenerationPort generationPort,
            DocumentCitationVerifier citationVerifier,
            DocumentObservabilitySupport observabilitySupport,
            DocumentRerankPort rerankPort) {
        this(properties,
                embeddingPort,
                aclScopePort,
                revocationGuard,
                preSecurityFilter,
                contextPacker,
                generationPort,
                citationVerifier,
                observabilitySupport,
                rerankPort,
                new DisabledDocumentQueryRewritePort(),
                new RewriteCandidateNormalizer(),
                new DocumentRuleExtractor());
    }

    public DocumentCapabilityHandler(
            AgentProperties properties,
            DocumentEmbeddingPort embeddingPort,
            DocumentAclScopePort aclScopePort,
            DocumentRevocationGuard revocationGuard,
            DocumentEvidencePreSecurityFilter preSecurityFilter,
            DocumentEvidenceContextPacker contextPacker,
            DocumentGenerationPort generationPort,
            DocumentCitationVerifier citationVerifier,
            DocumentObservabilitySupport observabilitySupport,
            DocumentRerankPort rerankPort,
            DocumentQueryRewritePort rewritePort,
            RewriteCandidateNormalizer rewriteCandidateNormalizer,
            DocumentRuleExtractor ruleExtractor) {
        this.properties = Objects.requireNonNull(properties, "properties must not be null");
        this.embeddingPort = Objects.requireNonNull(embeddingPort, "embeddingPort must not be null");
        this.aclScopePort = Objects.requireNonNull(aclScopePort, "aclScopePort must not be null");
        this.revocationGuard = Objects.requireNonNull(revocationGuard, "revocationGuard must not be null");
        this.preSecurityFilter = Objects.requireNonNull(preSecurityFilter, "preSecurityFilter must not be null");
        this.contextPacker = Objects.requireNonNull(contextPacker, "contextPacker must not be null");
        this.generationPort = Objects.requireNonNull(generationPort, "generationPort must not be null");
        this.citationVerifier = Objects.requireNonNull(citationVerifier, "citationVerifier must not be null");
        this.observabilitySupport = observabilitySupport;
        this.rerankPort = Objects.requireNonNull(rerankPort, "rerankPort must not be null");
        this.rewritePort = Objects.requireNonNull(rewritePort, "rewritePort must not be null");
        this.rewriteCandidateNormalizer = Objects.requireNonNull(
                rewriteCandidateNormalizer, "rewriteCandidateNormalizer must not be null");
        this.ruleExtractor = Objects.requireNonNull(ruleExtractor, "ruleExtractor must not be null");
    }

    @Override
    public HandlerResult<DocumentAgentResultPayload> execute(
            ValidatedDocumentPlan plan,
            ExecutionContext context) {
        DocumentRetrievableAdapter adapter = context.requireAdapter(DocumentRetrievableAdapter.class);
        DocumentRetrievalRequest preparedRequest = buildQueryVariants(plan.request(), context);
        DocumentRetrievalRequest retrievalRequest = withAclScope(withQueryVectorIfNeeded(preparedRequest, context), context);
        long retrievalStarted = System.nanoTime();
        AdapterDocumentResult adapterResult;
        try {
            adapterResult = adapter.retrieve(retrievalRequest);
            adapterResult = applyRerankIfEnabled(retrievalRequest, adapterResult, context);
            recordRetrieval(retrievalRequest, "SUCCESS", retrievalStarted);
            recordRetrievalDiagnostics(retrievalRequest, adapterResult);
        } catch (RuntimeException ex) {
            recordRetrieval(retrievalRequest, "FAILED", retrievalStarted);
            throw ex;
        }
        DocumentAgentResultPayload payload = new DocumentAgentResultPayload(
                toParameters(plan),
                toResult(plan, adapterResult));
        applyGenerationIfEnabled(plan, retrievalRequest, adapterResult, payload.getDocumentResult(), context);
        return HandlerResult.of(payload, List.of(toContextWrite(plan, adapterResult)));
    }

    private DocumentRetrievalRequest buildQueryVariants(DocumentRetrievalRequest request, ExecutionContext context) {
        List<String> ruleKeywords = ruleExtractor.extract(
                request.getQueryText(),
                request.getDomain(),
                request.getMaterialType());
        DocumentRewriteResponse rewriteResponse = new DocumentRewriteResponse(List.of(), null, null);
        var rewrite = properties.getDocument().getRewrite();
        if (rewrite.isEnabled()) {
            try {
                rewriteResponse = rewritePort.rewrite(new DocumentRewriteRequest(
                        context.invocationId(),
                        request.getQueryText(),
                        request.getDomain(),
                        request.getMaterialType(),
                        rewrite.getLanguage(),
                        rewrite.getMaxCandidates(),
                        rewrite.getTimeout().toMillis(),
                        context.absoluteDeadline()));
                if (rewriteResponse == null) {
                    rewriteResponse = new DocumentRewriteResponse(List.of(), null, null);
                }
                recordProvider("rewrite", request.getOperation().name(), "SUCCESS");
            } catch (RuntimeException ex) {
                recordProvider("rewrite", request.getOperation().name(), "FAILED");
                log.warn("document rewrite degraded: invocationId={}, domain={}, reason={}",
                        context.invocationId(),
                        request.getDomain(),
                        ex.getClass().getSimpleName());
            }
        }
        QueryVariants variants = rewriteCandidateNormalizer.normalize(
                request.getQueryText(),
                ruleKeywords,
                rewriteResponse.candidates(),
                rewrite.getMaxCandidates(),
                rewrite.getMaxCandidateLength());
        if (variants.rejectedCount() > 0) {
            log.warn("document rewrite candidates rejected: invocationId={}, domain={}, rejectedCount={}, digest={}",
                    context.invocationId(),
                    request.getDomain(),
                    variants.rejectedCount(),
                    variants.rewriteCandidateDigest());
        }
        return copyRequest(
                request,
                request.getRetrievalMode(),
                request.getQueryVector(),
                variants.ruleKeywords(),
                variants.rewriteCandidates());
    }

    private DocumentRetrievalRequest withAclScope(DocumentRetrievalRequest request, ExecutionContext context) {
        DocumentRevocationDecision decision = revocationGuard.evaluate(
                request.getDomain(),
                null,
                request.getRetrievalProfile(),
                request.getProfileVersion(),
                request.getIndexAlias());
        if (decision.revoked()) {
            recordRevocation(decision);
            throw new IllegalStateException("document access revoked by "
                    + decision.source() + ":" + decision.target());
        }
        var scope = aclScopePort.resolve(new DocumentAclScopeRequest(
                context.invocationId(),
                context.executionScope().subjectRef(),
                request.getDomain(),
                request.getMaterialType(),
                request.getRetrievalProfile(),
                request.getProfileVersion(),
                request.getIndexAlias(),
                context.executionScope().currentPermissionEvidenceId(),
                context.executionScope().currentPermissionVersion(),
                context.absoluteDeadline()));
        if (scope.isExpiredAt(java.time.Instant.now())) {
            recordRevocation("ACL_SCOPE", "AUTHORITY");
            throw new IllegalStateException("document ACL scope is expired");
        }
        return request.withAclScope(
                scope,
                context.executionScope().currentPermissionEvidenceId(),
                context.executionScope().currentPermissionVersion());
    }

    private DocumentRetrievalRequest withQueryVectorIfNeeded(DocumentRetrievalRequest request, ExecutionContext context) {
        DocumentRetrievalMode mode = request.getRetrievalMode();
        DocumentHybridOptions options = request.getHybridOptions();
        boolean denseVectorRequired = mode == DocumentRetrievalMode.VECTOR
                || (mode == DocumentRetrievalMode.HYBRID
                && (options == null || options.requiresDenseVector()));
        if (!denseVectorRequired) {
            return request;
        }
        if (!properties.getDocument().getEmbedding().isEnabled()) {
            if (mode == DocumentRetrievalMode.HYBRID) {
                return downgradeHybridToKeyword(request, context, "EMBEDDING_DISABLED");
            }
            throw new IllegalStateException("document vector retrieval requires enabled embedding");
        }
        var embedding = embedOrFallback(request, context, mode);
        if (embedding == null) {
            return downgradeHybridToKeyword(request, context, "EMBEDDING_PROVIDER_FAILURE");
        }
        if (embedding.queryVector() == null || embedding.queryVector().isEmpty()) {
            if (mode == DocumentRetrievalMode.HYBRID) {
                return downgradeHybridToKeyword(request, context, "EMPTY_QUERY_VECTOR");
            }
            throw new IllegalStateException("document embedding returned empty queryVector");
        }
        int configuredDimension = expectedEmbeddingDimension(request);
        if (configuredDimension > 0
                && (embedding.dimension() != configuredDimension
                || embedding.queryVector().size() != configuredDimension)) {
            throw new IllegalStateException("document embedding dimension mismatch");
        }
        String configuredModel = expectedEmbeddingModel(request);
        if (configuredModel != null
                && !configuredModel.isBlank()
                && !configuredModel.equals(embedding.embeddingModel())) {
            throw new IllegalStateException("document embedding model mismatch");
        }
        if (embedding.queryVector().stream().anyMatch(value -> value == null || !Double.isFinite(value))) {
            throw new IllegalStateException("document embedding returned invalid queryVector");
        }
        return copyRequest(request, mode, embedding.queryVector());
    }

    private DocumentRetrievalRequest downgradeHybridToKeyword(
            DocumentRetrievalRequest request,
            ExecutionContext context,
            String reason) {
        DocumentHybridOptions options = request.getHybridOptions();
        log.warn("document hybrid retrieval degraded: invocationId={}, domain={}, requestedMode={}, "
                        + "effectiveMode={}, reason={}, topK={}, keywordK={}, vectorK={}, rrfK={}, numCandidates={}",
                context.invocationId(),
                request.getDomain(),
                DocumentRetrievalMode.HYBRID,
                DocumentRetrievalMode.KEYWORD,
                reason,
                request.getTopK(),
                options == null ? null : options.keywordK(),
                options == null ? null : options.vectorK(),
                options == null ? null : options.rrfK(),
                options == null ? null : options.numCandidates());
        return copyRequest(request, DocumentRetrievalMode.KEYWORD, List.of());
    }

    private DocumentEmbeddingResult embedOrFallback(
            DocumentRetrievalRequest request,
            ExecutionContext context,
            DocumentRetrievalMode mode) {
        try {
            if (deadlineExpired(context.absoluteDeadline())) {
                throw new IllegalStateException("document embedding deadline expired");
            }
            DocumentEmbeddingResult result = embeddingPort.embed(new DocumentEmbeddingRequest(
                    context.invocationId(),
                    request.getQueryText(),
                    queryVariants(request),
                    request.getDomain(),
                    expectedEmbeddingProvider(request),
                    expectedEmbeddingModel(request),
                    expectedEmbeddingModel(request),
                    expectedEmbeddingDimension(request),
                    context.absoluteDeadline()));
            recordProvider("embedding", mode.name(), "SUCCESS");
            return result;
        } catch (RuntimeException ex) {
            recordProvider("embedding", mode.name(), "FAILED");
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
        return copyRequest(source, mode, queryVector, source.getRuleKeywords(), source.getRewriteCandidates());
    }

    private DocumentRetrievalRequest copyRequest(
            DocumentRetrievalRequest source,
            DocumentRetrievalMode mode,
            List<Double> queryVector,
            List<String> ruleKeywords,
            List<String> rewriteCandidates) {
        return new DocumentRetrievalRequest(
                source.getOperation(),
                source.getDomain(),
                source.getMaterialType(),
                source.getRetrievalProfile(),
                source.getProfileVersion(),
                source.getIndexAlias(),
                source.getQueryText(),
                ruleKeywords,
                rewriteCandidates,
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
                source.getContextOptions(),
                source.getAclScope(),
                source.getPermissionEvidenceId(),
                source.getPermissionVersion());
    }

    private static List<String> queryVariants(DocumentRetrievalRequest request) {
        LinkedHashSet<String> variants = new LinkedHashSet<>();
        if (request.getQueryText() != null && !request.getQueryText().isBlank()) {
            variants.add(request.getQueryText().trim());
        }
        request.getRewriteCandidates().stream()
                .filter(Objects::nonNull)
                .map(String::trim)
                .filter(value -> !value.isBlank())
                .forEach(variants::add);
        return List.copyOf(variants);
    }

    private static String blankToDefault(String value, String defaultValue) {
        return value == null || value.isBlank() ? defaultValue : value.trim();
    }

    private String expectedEmbeddingProvider(DocumentRetrievalRequest request) {
        DocumentHybridOptions options = request.getHybridOptions();
        return blankToDefault(
                options == null ? null : options.embeddingProvider(),
                properties.getDocument().getEmbedding().getProvider());
    }

    private String expectedEmbeddingModel(DocumentRetrievalRequest request) {
        DocumentHybridOptions options = request.getHybridOptions();
        return blankToDefault(
                options == null ? null : options.embeddingModel(),
                properties.getDocument().getEmbedding().getModel());
    }

    private int expectedEmbeddingDimension(DocumentRetrievalRequest request) {
        DocumentHybridOptions options = request.getHybridOptions();
        if (options != null && options.embeddingDimension() > 0) {
            return options.embeddingDimension();
        }
        return properties.getDocument().getEmbedding().getDimension();
    }

    private AdapterDocumentResult applyRerankIfEnabled(
            DocumentRetrievalRequest request,
            AdapterDocumentResult adapterResult,
            ExecutionContext context) {
        DocumentHybridOptions options = request.getHybridOptions();
        if (options == null || !options.rerankEnabled()) {
            markRerankDiagnostics(adapterResult, "SKIPPED", "DISABLED");
            return adapterResult;
        }
        try {
            AdapterDocumentResult safeInput = safeRerankInput(adapterResult);
            if (nonNullEvidence(safeInput.getHits()).isEmpty()) {
                markRerankDiagnostics(adapterResult, "SKIPPED", "EMPTY_CANDIDATES");
                return adapterResult;
            }
            AdapterDocumentResult reranked = rerankPort.rerank(new DocumentRerankRequest(
                    context.invocationId(),
                    request.getDomain(),
                    request.getMaterialType(),
                    request.getRetrievalProfile(),
                    request.getQueryText(),
                    options.rerankTopN(),
                    safeInput,
                    context.absoluteDeadline()));
            if (reranked == null || nonNullEvidence(reranked.getHits()).isEmpty()) {
                markRerankDiagnostics(adapterResult, "SKIPPED", "EMPTY_RERANK_RESULT");
                return adapterResult;
            }
            AdapterDocumentResult result = mergeRerankResult(adapterResult, reranked);
            markRerankDiagnostics(result, "SUCCEEDED", null);
            return result;
        } catch (RuntimeException ex) {
            log.warn("document rerank skipped: invocationId={}, domain={}, profile={}, reason={}",
                    context.invocationId(),
                    request.getDomain(),
                    request.getRetrievalProfile(),
                    ex.getClass().getSimpleName());
            markRerankDiagnostics(adapterResult, "SKIPPED", ex.getClass().getSimpleName());
            return adapterResult;
        }
    }

    private static void markRerankDiagnostics(
            AdapterDocumentResult result,
            String status,
            String skippedReason) {
        if (result == null) {
            return;
        }
        AdapterDocumentRetrievalDiagnostics diagnostics = result.getRetrievalDiagnostics();
        if (diagnostics == null) {
            diagnostics = new AdapterDocumentRetrievalDiagnostics();
            result.setRetrievalDiagnostics(diagnostics);
        }
        diagnostics.setRerankStatus(status);
        diagnostics.setRerankSkippedReason(skippedReason);
    }

    private static AdapterDocumentResult safeRerankInput(AdapterDocumentResult source) {
        AdapterDocumentResult safe = copyResultShell(source);
        List<AdapterDocumentEvidence> hits = nonNullEvidence(source == null ? null : source.getHits()).stream()
                .map(DocumentCapabilityHandler::safeRerankEvidence)
                .toList();
        safe.setHits(hits);
        safe.setCitations(hits);
        return safe;
    }

    private static AdapterDocumentEvidence safeRerankEvidence(AdapterDocumentEvidence source) {
        AdapterDocumentEvidence target = new AdapterDocumentEvidence();
        target.setDocumentId(source.getDocumentId());
        target.setChunkId(source.getChunkId());
        target.setTitle(source.getTitle());
        target.setSourceType(source.getSourceType());
        target.setSection(source.getSection());
        target.setPage(source.getPage());
        target.setSourceUri(source.getSourceUri());
        target.setSnippet(source.getSnippet());
        target.setChunkIndex(source.getChunkIndex());
        target.setCharStart(source.getCharStart());
        target.setCharEnd(source.getCharEnd());
        target.setKeywordRank(source.getKeywordRank());
        target.setVectorRank(source.getVectorRank());
        target.setRrfScore(source.getRrfScore());
        target.setRetrievalChannels(source.getRetrievalChannels());
        target.setScore(source.getScore());
        target.setMetadata(safeRerankMetadata(source.getMetadata()));
        return target;
    }

    private static Map<String, Object> safeRerankMetadata(Map<String, Object> metadata) {
        if (metadata == null || metadata.isEmpty()) {
            return Map.of();
        }
        Map<String, Object> safe = new LinkedHashMap<>();
        metadata.forEach((key, value) -> {
            if (key != null && RERANK_METADATA_ALLOWLIST.contains(key)) {
                safe.put(key, value);
            }
        });
        return safe;
    }

    private static AdapterDocumentResult mergeRerankResult(
            AdapterDocumentResult original,
            AdapterDocumentResult reranked) {
        if (reranked == null) {
            return original;
        }
        List<AdapterDocumentEvidence> originalHits = nonNullEvidence(original == null ? null : original.getHits());
        List<AdapterDocumentEvidence> rerankedHits = nonNullEvidence(reranked.getHits());
        if (originalHits.isEmpty() || rerankedHits.isEmpty()) {
            return original;
        }
        Map<String, AdapterDocumentEvidence> originalById = new LinkedHashMap<>();
        for (AdapterDocumentEvidence hit : originalHits) {
            String id = citationId(hit);
            if (id != null) {
                originalById.putIfAbsent(id, hit);
            }
        }
        List<AdapterDocumentEvidence> ordered = new ArrayList<>();
        Set<String> selected = new LinkedHashSet<>();
        for (AdapterDocumentEvidence rerankedHit : rerankedHits) {
            String id = citationId(rerankedHit);
            AdapterDocumentEvidence originalHit = id == null ? null : originalById.get(id);
            if (originalHit == null || selected.contains(id)) {
                continue;
            }
            applyRerankFields(originalHit, rerankedHit);
            ordered.add(originalHit);
            selected.add(id);
        }
        for (AdapterDocumentEvidence hit : originalHits) {
            String id = citationId(hit);
            if (id == null || selected.add(id)) {
                ordered.add(hit);
            }
        }
        AdapterDocumentResult result = copyResultShell(original);
        result.setHits(ordered);
        result.setCitations(original == null || original.getCitations() == null
                ? null
                : reorderEvidence(original.getCitations(), rerankedHits));
        return result;
    }

    private static List<AdapterDocumentEvidence> reorderEvidence(
            List<AdapterDocumentEvidence> source,
            List<AdapterDocumentEvidence> order) {
        List<AdapterDocumentEvidence> safeSource = nonNullEvidence(source);
        if (safeSource.isEmpty() || order == null || order.isEmpty()) {
            return safeSource;
        }
        Map<String, AdapterDocumentEvidence> sourceById = new LinkedHashMap<>();
        for (AdapterDocumentEvidence evidence : safeSource) {
            String id = citationId(evidence);
            if (id != null) {
                sourceById.putIfAbsent(id, evidence);
            }
        }
        List<AdapterDocumentEvidence> reordered = new ArrayList<>();
        Set<String> selected = new LinkedHashSet<>();
        for (AdapterDocumentEvidence evidence : order) {
            String id = citationId(evidence);
            AdapterDocumentEvidence match = id == null ? null : sourceById.get(id);
            if (match != null && selected.add(id)) {
                reordered.add(match);
            }
        }
        for (AdapterDocumentEvidence evidence : safeSource) {
            String id = citationId(evidence);
            if (id == null || selected.add(id)) {
                reordered.add(evidence);
            }
        }
        return reordered;
    }

    private static void applyRerankFields(
            AdapterDocumentEvidence original,
            AdapterDocumentEvidence reranked) {
        if (reranked.getScore() != null) {
            original.setScore(reranked.getScore());
        }
        Map<String, Object> rerankMetadata = safeRerankMetadata(reranked.getMetadata());
        if (!rerankMetadata.isEmpty()) {
            Map<String, Object> merged = new LinkedHashMap<>(
                    original.getMetadata() == null ? Map.of() : original.getMetadata());
            merged.putAll(rerankMetadata);
            original.setMetadata(merged);
        }
    }

    private static AdapterDocumentResult copyResultShell(AdapterDocumentResult source) {
        AdapterDocumentResult target = new AdapterDocumentResult();
        if (source == null) {
            return target;
        }
        target.setCandidateAnswerText(source.getCandidateAnswerText());
        target.setCandidateSummaryText(source.getCandidateSummaryText());
        target.setCandidateSummaryBullets(source.getCandidateSummaryBullets());
        target.setPartial(source.isPartial());
        target.setRequestedDocumentCount(source.getRequestedDocumentCount());
        target.setCoveredDocumentCount(source.getCoveredDocumentCount());
        target.setRetrievalDiagnostics(source.getRetrievalDiagnostics());
        return target;
    }

    private static AgentDocumentParameters toParameters(ValidatedDocumentPlan plan) {
        AgentDocumentParameters parameters = new AgentDocumentParameters();
        parameters.setDomain(plan.domain().orElseThrow());
        parameters.setMaterialType(plan.request().getMaterialType());
        parameters.setRetrievalProfile(plan.request().getRetrievalProfile());
        parameters.setProfileVersion(plan.request().getProfileVersion());
        parameters.setIndexAlias(plan.request().getIndexAlias());
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
        coverage.setRequestedDocumentCount(requestedDocumentCount(plan, safeResult));
        coverage.setCoveredDocumentCount(safeResult.getCoveredDocumentCount());
        coverage.setEvidenceCount(citations.size());
        coverage.setTruncated(safeResult.isPartial()
                || citations.size() > plan.request().getTopK()
                || hits.size() > citations.size());
        result.setCoverage(coverage);
        return result;
    }

    private static int requestedDocumentCount(ValidatedDocumentPlan plan, AdapterDocumentResult safeResult) {
        var summaryScope = plan.request().getSummaryScope();
        if (summaryScope != null && summaryScope.getDocumentIds() != null && !summaryScope.getDocumentIds().isEmpty()) {
            return (int) summaryScope.getDocumentIds().stream()
                    .filter(Objects::nonNull)
                    .map(String::trim)
                    .filter(value -> !value.isBlank())
                    .distinct()
                    .count();
        }
        return safeResult.getRequestedDocumentCount() > 0 ? safeResult.getRequestedDocumentCount() : plan.request().getTopK();
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
        filteredEvidence = selectGenerationEvidence(filteredEvidence);
        if (filteredEvidence.isEmpty()) {
            result.setGenerationStatus(DocumentGenerationStatus.SKIPPED);
            return;
        }
        int maxOutputChars = resolveMaxOutputChars(options, plan);
        DocumentContextBudget budget = new DocumentContextBudget(
                properties.getDocument().getGeneration().getMaxContextChars(),
                properties.getDocument().getGeneration().getMaxEvidenceChars(),
                properties.getDocument().getMaxGenerationEvidenceCount(),
                maxOutputChars);
        var evidencePackage = contextPacker.pack(new DocumentContextPackRequest(plan, filteredEvidence, context, budget));
        try {
            if (deadlineExpired(context.absoluteDeadline())) {
                throw new IllegalStateException("document generation deadline expired");
            }
            DocumentGenerationResult generated;
            try {
                generated = generationPort.generate(new DocumentGenerationRequest(
                        context.invocationId(),
                        retrievalRequest.getOperation(),
                        retrievalRequest.getQueryText(),
                        properties.getDocument().getGeneration().getModel(),
                        evidencePackage,
                        budget.maxOutputChars(),
                        context.absoluteDeadline()));
                recordProvider("generation", retrievalRequest.getOperation().name(), "SUCCESS");
            } catch (RuntimeException ex) {
                recordProvider("generation", retrievalRequest.getOperation().name(), "FAILED");
                throw ex;
            }
            if (deadlineExpired(context.absoluteDeadline())) {
                throw new IllegalStateException("document generation deadline expired");
            }
            CitationVerificationResult verification = citationVerifier.verify(generated, evidencePackage);
            result.setCitationVerification(toApiVerification(verification));
            result.setGroundingStatus(verification.status());
            if (verification.status() == GroundingStatus.VERIFIED) {
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

    private static boolean deadlineExpired(Instant deadline) {
        return deadline == null || !deadline.isAfter(Instant.now());
    }

    private void recordRetrieval(DocumentRetrievalRequest request, String result, long startedNanos) {
        if (observabilitySupport == null) {
            return;
        }
        observabilitySupport.recordRetrieval(
                request.getDomain(),
                request.getRetrievalMode().name(),
                result,
                Duration.ofNanos(System.nanoTime() - startedNanos));
    }

    private void recordProvider(String providerType, String operation, String result) {
        if (observabilitySupport != null) {
            observabilitySupport.recordProvider(providerType, operation, result);
        }
    }

    private void recordRevocation(DocumentRevocationDecision decision) {
        recordRevocation(decision.target(), decision.source());
    }

    private void recordRevocation(String target, String source) {
        if (observabilitySupport != null) {
            observabilitySupport.recordRevocationHit(target, source);
        }
    }

    private void recordRetrievalDiagnostics(
            DocumentRetrievalRequest request,
            AdapterDocumentResult adapterResult) {
        if (observabilitySupport == null || adapterResult == null) {
            return;
        }
        observabilitySupport.recordRetrievalDiagnostics(
                request.getDomain(),
                request.getRetrievalMode().name(),
                adapterResult.getRetrievalDiagnostics());
    }

    private List<AdapterDocumentEvidence> selectGenerationEvidence(List<AdapterDocumentEvidence> evidence) {
        List<AdapterDocumentEvidence> sorted = nonNullEvidence(evidence).stream()
                .sorted(evidenceRanking())
                .toList();
        int maxEvidenceCount = Math.max(1, properties.getDocument().getMaxGenerationEvidenceCount());
        if (sorted.size() <= maxEvidenceCount) {
            return sorted;
        }
        var selection = properties.getDocument().getEvidenceSelection();
        if (selection.getStrategy() == AgentProperties.EvidenceSelectionStrategy.SCORE_GROUP_TOP) {
            List<AdapterDocumentEvidence> grouped = scoreGroupTop(sorted, selection.getScoreGroups(), selection.getMinTopGroupSize());
            if (!grouped.isEmpty()) {
                return grouped.stream().limit(maxEvidenceCount).toList();
            }
        }
        return sorted.stream().limit(maxEvidenceCount).toList();
    }

    private static List<AdapterDocumentEvidence> scoreGroupTop(
            List<AdapterDocumentEvidence> sorted,
            int configuredGroups,
            int configuredMinTopGroupSize) {
        List<AdapterDocumentEvidence> scored = sorted.stream()
                .filter(evidence -> effectiveScore(evidence) != null)
                .toList();
        if (scored.size() < 2) {
            return List.of();
        }
        BigDecimal max = effectiveScore(scored.get(0));
        BigDecimal min = effectiveScore(scored.get(scored.size() - 1));
        if (max == null || min == null || max.compareTo(min) <= 0) {
            return List.of();
        }
        int groups = Math.max(1, configuredGroups);
        BigDecimal threshold = max.subtract(max.subtract(min).divide(BigDecimal.valueOf(groups), java.math.RoundingMode.HALF_UP));
        List<AdapterDocumentEvidence> topGroup = scored.stream()
                .filter(evidence -> effectiveScore(evidence).compareTo(threshold) >= 0)
                .toList();
        int minTopGroupSize = Math.max(1, configuredMinTopGroupSize);
        if (topGroup.size() < minTopGroupSize) {
            return sorted.stream().limit(minTopGroupSize).toList();
        }
        return topGroup;
    }

    private static Comparator<AdapterDocumentEvidence> evidenceRanking() {
        return Comparator
                .comparing(DocumentCapabilityHandler::effectiveScore, Comparator.nullsLast(Comparator.reverseOrder()))
                .thenComparing(AdapterDocumentEvidence::getChunkIndex, Comparator.nullsLast(Integer::compareTo));
    }

    private static BigDecimal effectiveScore(AdapterDocumentEvidence evidence) {
        if (evidence == null) {
            return null;
        }
        return evidence.getRrfScore() == null ? evidence.getScore() : evidence.getRrfScore();
    }

    private int resolveMaxOutputChars(DocumentGenerationOptions options, ValidatedDocumentPlan plan) {
        int outputLimit = options.getMaxOutputChars() == null
                ? properties.getDocument().getGeneration().getMaxOutputChars()
                : options.getMaxOutputChars();
        var summaryScope = plan.request().getSummaryScope();
        if (plan.request().getOperation() == com.dylan.agent.api.plan.DocumentPlanOperation.SUMMARIZE
                && summaryScope != null
                && summaryScope.getMaxSummaryChars() != null) {
            return Math.min(outputLimit, summaryScope.getMaxSummaryChars());
        }
        return outputLimit;
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
        hit.setSnippet(displaySnippet(evidence));
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
        citation.setSnippet(displaySnippet(evidence));
        citation.setChunkIndex(evidence.getChunkIndex());
        citation.setCharStart(evidence.getCharStart());
        citation.setCharEnd(evidence.getCharEnd());
        return citation;
    }

    private static String displaySnippet(AdapterDocumentEvidence evidence) {
        if (evidence == null) {
            return null;
        }
        if (evidence.getCitationText() != null && !evidence.getCitationText().isBlank()) {
            return evidence.getCitationText();
        }
        return evidence.getSnippet();
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
