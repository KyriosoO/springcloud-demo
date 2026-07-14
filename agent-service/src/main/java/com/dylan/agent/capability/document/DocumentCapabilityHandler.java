package com.dylan.agent.capability.document;

import com.dylan.agent.capability.document.profile.DocumentFeaturePolicy;

import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.document.AdapterDocumentRetrievalDiagnostics;
import com.dylan.agent.adapter.api.document.AdapterDocumentRetrievalResult;
import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.adapter.api.document.SafeDocumentCandidate;
import com.dylan.agent.adapter.api.document.provider.*;
import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.adapter.api.operation.CapabilityOperationOutcome;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
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
import com.dylan.agent.capability.document.embedding.DocumentEmbeddingResult;
import com.dylan.agent.capability.document.acl.*;
import com.dylan.agent.capability.document.generation.CitationVerificationResult;
import com.dylan.agent.capability.document.generation.DocumentCitationVerifier;
import com.dylan.agent.capability.document.generation.DocumentEvidencePackingLimit;
import com.dylan.agent.capability.document.generation.DocumentGenerationEvidenceProjector;
import com.dylan.agent.capability.document.generation.DocumentGenerationInputProjector;
import com.dylan.agent.capability.document.generation.DocumentGeneratedContent;
import com.dylan.agent.capability.document.generation.DocumentGeneratedTextCandidate;
import com.dylan.agent.capability.document.generation.DocumentGeneratedTextCandidateFactory;
import com.dylan.agent.capability.document.generation.EvidenceContextPackageFactory;
import com.dylan.agent.capability.document.generation.EvidenceContextPackageRequest;
import com.dylan.agent.capability.document.generation.DocumentGenerationPort;
import com.dylan.agent.capability.document.generation.DocumentExtractiveFallbackComposer;
import com.dylan.agent.capability.document.provider.DocumentProviderOperationRequestBinder;
import com.dylan.agent.capability.document.provider.security.*;
import com.dylan.agent.capability.document.rerank.DocumentRerankPort;
import com.dylan.agent.capability.document.rewrite.DocumentQueryRewritePort;
import com.dylan.agent.capability.document.rewrite.QueryVariants;
import com.dylan.agent.capability.document.rewrite.RewriteCandidateNormalizer;
import com.dylan.agent.capability.document.security.*;
import com.dylan.agent.capability.document.evidence.DocumentCoverageFactory;
import com.dylan.agent.capability.document.evidence.DocumentEvidenceSelector;
import com.dylan.agent.capability.document.evidence.DocumentEvidenceVisibilityProjector;
import com.dylan.agent.capability.document.evidence.DocumentResultSizeGuard;
import com.dylan.agent.capability.document.evidence.SelectedDocumentEvidence;
import com.dylan.agent.kernel.core.ExecutionContext;
import com.dylan.agent.kernel.handler.CapabilityHandler;
import com.dylan.agent.kernel.handler.HandlerResult;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.time.Duration;
import java.time.Instant;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import com.fasterxml.jackson.databind.ObjectMapper;

public class DocumentCapabilityHandler
        implements CapabilityHandler<ValidatedDocumentPlan, DocumentAgentResultPayload> {

    private static final Logger log = LoggerFactory.getLogger(DocumentCapabilityHandler.class);
    private final DocumentEmbeddingPort embeddingPort;
    private final DocumentAclScopePort aclScopePort;
    private final DocumentAclCurrentnessPort aclCurrentnessPort;
    private final DocumentRevocationGuard revocationGuard;
    private final DocumentEvidenceVisibilityProjector visibilityProjector;
    private final DocumentGenerationEvidenceProjector generationEvidenceProjector;
    private final EvidenceContextPackageFactory evidenceContextPackageFactory;
    private final DocumentGeneratedTextCandidateFactory generatedTextCandidateFactory;
    private final DocumentGenerationInputProjector generationInputProjector;
    private final DocumentGenerationPort generationPort;
    private final DocumentCitationVerifier citationVerifier;
    private final DocumentObservabilitySupport observabilitySupport;
    private final DocumentRerankPort rerankPort;
    private final DocumentQueryRewritePort rewritePort;
    private final RewriteCandidateNormalizer rewriteCandidateNormalizer;
    private final DocumentRuleExtractor ruleExtractor;
    private final DocumentProviderOperationRequestBinder providerRequestBinder;
    private final DocumentProviderOutboundPolicyDecisionFactory providerPolicyDecisionFactory;
    private final DocumentProviderOutboundFieldProjector providerFieldProjector;
    private final DocumentProtectedFilterFactory protectedFilterFactory;
    private final DocumentAclExecutionEvidenceFactory aclEvidenceFactory = new DocumentAclExecutionEvidenceFactory();
    private final DocumentCandidateSecurityProjector candidateSecurityProjector = new DocumentCandidateSecurityProjector();
    private final DocumentCandidateSetCanonicalizer candidateSetCanonicalizer = new DocumentCandidateSetCanonicalizer();
    private final DocumentResultSecurityEvidenceMapper resultSecurityEvidenceMapper = new DocumentResultSecurityEvidenceMapper();
    private final DocumentRetrievalCommandFactory retrievalCommandFactory = new DocumentRetrievalCommandFactory();
    private final DocumentExtractiveFallbackComposer fallbackComposer = new DocumentExtractiveFallbackComposer();
    private final DocumentEvidenceSelector evidenceSelector = new DocumentEvidenceSelector();
    private final DocumentCoverageFactory coverageFactory = new DocumentCoverageFactory();
    private final DocumentResultSizeGuard resultSizeGuard;

    public DocumentCapabilityHandler(
            DocumentEmbeddingPort embeddingPort,
            DocumentAclScopePort aclScopePort,
            DocumentAclCurrentnessPort aclCurrentnessPort,
            DocumentRevocationGuard revocationGuard,
            DocumentEvidenceVisibilityProjector visibilityProjector,
            DocumentGenerationEvidenceProjector generationEvidenceProjector,
            EvidenceContextPackageFactory evidenceContextPackageFactory,
            DocumentGeneratedTextCandidateFactory generatedTextCandidateFactory,
            DocumentGenerationInputProjector generationInputProjector,
            DocumentGenerationPort generationPort,
            DocumentCitationVerifier citationVerifier,
            DocumentObservabilitySupport observabilitySupport,
            DocumentRerankPort rerankPort,
            DocumentQueryRewritePort rewritePort,
            RewriteCandidateNormalizer rewriteCandidateNormalizer,
            DocumentRuleExtractor ruleExtractor,
            DocumentProviderOperationRequestBinder providerRequestBinder,
            DocumentProviderOutboundPolicyDecisionFactory providerPolicyDecisionFactory,
            DocumentProviderOutboundFieldProjector providerFieldProjector,
            DocumentProtectedFilterFactory protectedFilterFactory,
            ObjectMapper objectMapper) {
        this.embeddingPort = Objects.requireNonNull(embeddingPort, "embeddingPort must not be null");
        this.aclScopePort = Objects.requireNonNull(aclScopePort, "aclScopePort must not be null");
        this.aclCurrentnessPort = Objects.requireNonNull(aclCurrentnessPort, "aclCurrentnessPort must not be null");
        this.revocationGuard = Objects.requireNonNull(revocationGuard, "revocationGuard must not be null");
        this.visibilityProjector = Objects.requireNonNull(
                visibilityProjector, "visibilityProjector must not be null");
        this.generationEvidenceProjector = Objects.requireNonNull(
                generationEvidenceProjector, "generationEvidenceProjector must not be null");
        this.evidenceContextPackageFactory = Objects.requireNonNull(
                evidenceContextPackageFactory, "evidenceContextPackageFactory must not be null");
        this.generatedTextCandidateFactory = Objects.requireNonNull(
                generatedTextCandidateFactory, "generatedTextCandidateFactory must not be null");
        this.generationInputProjector = Objects.requireNonNull(
                generationInputProjector, "generationInputProjector must not be null");
        this.generationPort = Objects.requireNonNull(generationPort, "generationPort must not be null");
        this.citationVerifier = Objects.requireNonNull(citationVerifier, "citationVerifier must not be null");
        this.observabilitySupport = observabilitySupport;
        this.rerankPort = Objects.requireNonNull(rerankPort, "rerankPort must not be null");
        this.rewritePort = Objects.requireNonNull(rewritePort, "rewritePort must not be null");
        this.rewriteCandidateNormalizer = Objects.requireNonNull(
                rewriteCandidateNormalizer, "rewriteCandidateNormalizer must not be null");
        this.ruleExtractor = Objects.requireNonNull(ruleExtractor, "ruleExtractor must not be null");
        this.providerRequestBinder = Objects.requireNonNull(providerRequestBinder, "providerRequestBinder must not be null");
        this.providerPolicyDecisionFactory = Objects.requireNonNull(
                providerPolicyDecisionFactory, "providerPolicyDecisionFactory must not be null");
        this.providerFieldProjector = Objects.requireNonNull(
                providerFieldProjector, "providerFieldProjector must not be null");
        this.protectedFilterFactory = Objects.requireNonNull(protectedFilterFactory, "protectedFilterFactory must not be null");
        this.resultSizeGuard = new DocumentResultSizeGuard(Objects.requireNonNull(objectMapper, "objectMapper must not be null"));
    }

    @Override
    public HandlerResult<DocumentAgentResultPayload> execute(
            ValidatedDocumentPlan plan,
            ExecutionContext context) {
        DocumentRetrievableAdapter adapter = context.requireAdapter(DocumentRetrievableAdapter.class);
        PreparedAclRetrieval aclPrepared = withProtectedFilter(
                initialExecution(plan), plan.profile(), context);
        assertScopeCurrent(aclPrepared.evidence(), context);
        DocumentRetrievalExecution retrievalRequest = withQueryVectorIfNeeded(
                buildQueryVariants(aclPrepared.request(), plan, context), plan.profile(), context);
        DocumentAclExecutionEvidence aclEvidence = aclPrepared.evidence();
        DocumentResourceLimit limits = documentLimits(context);
        long retrievalStarted = System.nanoTime();
        AdapterDocumentRetrievalResult adapterResult;
        try {
            var retrievalContext=context.operationContext(com.dylan.agent.adapter.api.operation.CapabilityOperationType.of("DOCUMENT_RETRIEVAL"));
            adapterResult=requireSuccess(adapter.retrieve(
                    retrievalCommandFactory.create(retrievalRequest,retrievalContext),retrievalContext),
                    "document retrieval", retrievalContext);
            List<SafeDocumentCandidate> rerankCandidates = candidateSecurityProjector.project(
                    adapterResult.hits(), aclEvidence, limits);
            adapterResult = applyRerankIfEnabled(
                    retrievalRequest, adapterResult, rerankCandidates, plan.profile(), context);
            recordRetrieval(retrievalRequest, "SUCCESS", retrievalStarted);
            recordRetrievalDiagnostics(retrievalRequest, adapterResult);
        } catch (RuntimeException ex) {
            recordRetrieval(retrievalRequest, "FAILED", retrievalStarted);
            throw ex;
        }
        List<AclBoundDocumentHit> publicVisibleHits = visibilityProjector.project(
                adapterResult.hits(), context.executionScope(), retrievalRequest.getDomain());
        SelectedDocumentEvidence selection = evidenceSelector.select(publicVisibleHits, limits);
        List<AclBoundDocumentHit> visibleHits = selection.items();
        AdapterDocumentRetrievalResult visibleResult = new AdapterDocumentRetrievalResult(
                visibleHits, adapterResult.diagnostics(), adapterResult.binding(), adapterResult.requestedDocumentCount());
        DocumentAgentResultPayload payload = new DocumentAgentResultPayload(
                toParameters(plan),
                toResult(plan, visibleResult, selection.truncated()));
        DocumentProviderBindingReference generationProvider = applyGenerationIfEnabled(
                plan, retrievalRequest, visibleResult, payload.getDocumentResult(), context);
        int retainedEvidence = enforceResultSize(payload, plan, visibleHits, limits);
        if (retainedEvidence < visibleHits.size()) {
            visibleHits = List.copyOf(visibleHits.subList(0, retainedEvidence));
            visibleResult = new AdapterDocumentRetrievalResult(
                    visibleHits, adapterResult.diagnostics(), adapterResult.binding(), adapterResult.requestedDocumentCount());
        }
        var safeCandidates = candidateSecurityProjector.project(
                visibleResult.hits(), aclEvidence, limits);
        var evidenceRefs = citationIds(visibleResult.hits());
        String candidateSetDigest = candidateSetCanonicalizer.digest(
                safeCandidates, evidenceRefs, AgentExecutionContracts.DOCUMENT_RESULT);
        DocumentFinalCurrentnessDecision finalDecision = revocationGuard.evaluate(
                new DocumentRevocationGuard.FinalDocumentCurrentnessRequest(
                        aclEvidence, safeCandidates, evidenceRefs, AgentExecutionContracts.DOCUMENT_RESULT,
                        candidateSetDigest,
                        context.capabilityId(),
                        context.executionScope().agentProfileRef().toString(),
                        java.util.Optional.ofNullable(generationProvider),
                        context.operationContext(CapabilityOperationType.of("DOCUMENT_ACL_CANDIDATE_CURRENTNESS"))));
        if (finalDecision.outcome() != DocumentCurrentnessOutcome.ALLOW) {
            recordRevocation("FINAL_CURRENTNESS", finalDecision.reasonCode().name());
            throw new IllegalStateException("document final currentness denied");
        }
        payload.setInternalSecurityEvidence(
                resultSecurityEvidenceMapper.map(finalDecision, safeCandidates, evidenceRefs));
        return HandlerResult.of(payload, List.of(toContextWrite(plan, visibleResult)));
    }

    private void assertScopeCurrent(
            DocumentAclExecutionEvidence aclEvidence,
            ExecutionContext context) {
        var scopeCurrentness = aclCurrentnessPort.verifyScope(new DocumentAclScopeCurrentnessRequest(
                aclEvidence, context.operationContext(CapabilityOperationType.of("DOCUMENT_ACL_SCOPE_CURRENTNESS"))));
        if (scopeCurrentness.outcome() != DocumentCurrentnessOutcome.ALLOW
                || !aclEvidence.aclAuthorityVersion().equals(scopeCurrentness.authorityVersion())
                || !context.executionScope().currentPermissionVersion().equals(scopeCurrentness.permissionVersion())) {
            recordRevocation("ACL_SCOPE_CURRENTNESS", scopeCurrentness.reasonCode());
            throw new IllegalStateException("document ACL scope is not current");
        }
    }

    private DocumentRetrievalExecution buildQueryVariants(
            DocumentRetrievalExecution request,
            ValidatedDocumentPlan plan,
            ExecutionContext context) {
        List<String> ruleKeywords = ruleExtractor.extract(
                request.getQueryText(),
                request.getDomain(),
                request.getMaterialType());
        List<com.dylan.agent.capability.document.rewrite.DocumentRewriteCandidate> rewriteCandidates = List.of();
        DocumentResourceLimit limits = documentLimits(context);
        int maxCandidates = limits.enhancement().maxRewriteCandidates();
        boolean rewriteEnabled = plan.profile().rewritePolicy() != DocumentFeaturePolicy.DISABLED
                && maxCandidates > 0;
        if (rewriteEnabled) {
            try {
                var operationContext = context.operationContext(CapabilityOperationType.of("DOCUMENT_REWRITE"));
                var input = new DocumentRewriteInputProjection(
                        request.getQueryText(), DocumentLanguage.ZH_CN, maxCandidates);
                var decision = requireProviderDecision(
                        operationContext.operationType(), plan, context,
                        plan.profile().rewritePolicy(), DocumentProviderIntendedFieldView.queryOnly());
                var outcome = rewritePort.rewrite(new DocumentRewriteOperationRequest(
                        input, providerRequestBinder.bind(decision, input, operationContext), operationContext));
                DocumentUntrustedRewritePayload payload = requireSuccess(
                        outcome, "rewrite", operationContext);
                rewriteCandidates = payload.candidates().stream()
                        .map(value -> new com.dylan.agent.capability.document.rewrite.DocumentRewriteCandidate(value, null, null))
                        .toList();
                recordProvider("rewrite", request.getOperation().name(), "SUCCESS");
            } catch (RuntimeException ex) {
                recordProvider("rewrite", request.getOperation().name(), "FAILED");
                if (plan.profile().rewritePolicy() == DocumentFeaturePolicy.REQUIRED) {
                    throw ex;
                }
                log.warn("document rewrite degraded: invocationId={}, domain={}, reason={}",
                        context.invocationId(),
                        request.getDomain(),
                        ex.getClass().getSimpleName());
            }
        }
        QueryVariants variants = rewriteCandidateNormalizer.normalize(
                request.getQueryText(),
                ruleKeywords,
                rewriteCandidates,
                maxCandidates,
                limits.input().maxQueryChars());
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

    private DocumentRetrievalExecution initialExecution(ValidatedDocumentPlan plan) {
        ValidatedDocumentExecutionParameters parameters = plan.parameters();
        return new DocumentRetrievalExecution(
                parameters.operation(), plan.selectedCorpus(), plan.profile().profileName(),
                plan.profile().documentProfileVersion(),
                parameters.normalizedQuery(), List.of(), List.of(),
                parameters.callerFilters().stream().map(filter -> new com.dylan.agent.adapter.api.query.ValidatedFilter(
                        filter.field(), com.dylan.agent.api.enums.AgentOperator.valueOf(filter.operator().name()),
                        filter.value(), filter.values())).toList(),
                parameters.sorts(), parameters.topK(), parameters.page(), parameters.size(), parameters.summaryScope(),
                parameters.citationRequired(), parameters.retrievalMode(), List.of(), null,
                parameters.channelProjection(), parameters.contextOptions(), null);
    }

    private PreparedAclRetrieval withProtectedFilter(
            DocumentRetrievalExecution request,
            DocumentExecutionProfileProjection profile,
            ExecutionContext context) {
        var operationContext = context.operationContext(CapabilityOperationType.of("DOCUMENT_ACL_SCOPE"));
        var aclRequest = new DocumentAclScopeRequest(
                operationContext,
                context.resourceLimits().reference().registrationIdentity(),
                context.executionScope().subject(),
                new com.dylan.agent.adapter.api.document.DocumentCorpusKey(
                        request.getDomain(), request.getMaterialType()),
                request.getOperation(),
                new PermissionEvidenceReference(
                        context.executionScope().currentPermissionEvidenceId(),
                        context.executionScope().currentPermissionVersion()),
                profile.profileProjectionDigest());
        var resolution = aclScopePort.resolve(aclRequest);
        if (resolution instanceof DocumentAclScopeDenied denied) {
            recordRevocation("ACL_SCOPE", denied.reason().name());
            throw new IllegalStateException("document ACL scope denied");
        }
        if (resolution instanceof DocumentAclScopeFailed failed) {
            recordRevocation("ACL_SCOPE", failed.code().name());
            throw new IllegalStateException("document ACL scope unavailable");
        }
        if (!(resolution instanceof DocumentAclScopeAllowed allowed)) {
            throw new IllegalStateException("unknown document ACL resolution");
        }
        DocumentAclExecutionEvidence evidence = aclEvidenceFactory.create(
                aclRequest, allowed.scope(), allowed.metadata());
        return new PreparedAclRetrieval(
                request.withProtectedFilterBinding(protectedFilterFactory.build(allowed.scope(), evidence)), evidence);
    }

    private record PreparedAclRetrieval(
            DocumentRetrievalExecution request,
            DocumentAclExecutionEvidence evidence) {}

    private DocumentRetrievalExecution withQueryVectorIfNeeded(
            DocumentRetrievalExecution request,
            DocumentExecutionProfileProjection profile,
            ExecutionContext context) {
        DocumentRetrievalMode mode = request.getRetrievalMode();
        DocumentChannelProfileProjection options = request.getChannelProjection();
        boolean denseVectorRequired = mode == DocumentRetrievalMode.VECTOR
                || (mode == DocumentRetrievalMode.HYBRID
                && (options == null || options.enablesDenseVector()));
        if (!denseVectorRequired) {
            return request;
        }
        if (profile.embeddingPolicy() == DocumentFeaturePolicy.DISABLED
                || documentLimits(context).enhancement().maxEmbeddingTexts() == 0) {
            if (mode == DocumentRetrievalMode.HYBRID) {
                return downgradeHybridToKeyword(request, context, "EMBEDDING_DISABLED");
            }
            throw new IllegalStateException("document vector retrieval requires enabled embedding");
        }
        var embedding = embedOrFallback(request, profile, context, mode);
        if (embedding == null) {
            return downgradeHybridToKeyword(request, context, "EMBEDDING_PROVIDER_FAILURE");
        }
        if (embedding.queryVector() == null || embedding.queryVector().isEmpty()) {
            if (mode == DocumentRetrievalMode.HYBRID) {
                return downgradeHybridToKeyword(request, context, "EMPTY_QUERY_VECTOR");
            }
            throw new IllegalStateException("document embedding returned empty queryVector");
        }
        int configuredDimension = documentLimits(context).enhancement().maxEmbeddingDimensions();
        if (configuredDimension > 0
                && (embedding.dimension() != configuredDimension
                || embedding.queryVector().size() != configuredDimension)) {
            throw new IllegalStateException("document embedding dimension mismatch");
        }
        if (embedding.queryVector().stream().anyMatch(value -> value == null || !Double.isFinite(value))) {
            throw new IllegalStateException("document embedding returned invalid queryVector");
        }
        return request.copy(mode, embedding.queryVector(), embedding.digest(), request.getRuleKeywords(),
                request.getRewriteCandidates(), request.getProtectedFilterBinding());
    }

    private DocumentRetrievalExecution downgradeHybridToKeyword(
            DocumentRetrievalExecution request,
            ExecutionContext context,
            String reason) {
        DocumentChannelProfileProjection options = request.getChannelProjection();
        log.warn("document hybrid retrieval degraded: invocationId={}, domain={}, requestedMode={}, "
                        + "effectiveMode={}, reason={}, topK={}, keywordK={}, vectorK={}, rrfK={}, numCandidates={}",
                context.invocationId(),
                request.getDomain(),
                DocumentRetrievalMode.HYBRID,
                DocumentRetrievalMode.KEYWORD,
                reason,
                request.getTopK(),
                options == null ? null : options.keywordCandidateCount(),
                options == null ? null : options.vectorCandidateCount(),
                options == null ? null : options.rrfK(),
                options == null ? null : options.numCandidates());
        return request.copy(DocumentRetrievalMode.KEYWORD, List.of(), null, request.getRuleKeywords(),
                request.getRewriteCandidates(), request.getProtectedFilterBinding());
    }

    private DocumentEmbeddingResult embedOrFallback(
            DocumentRetrievalExecution request,
            DocumentExecutionProfileProjection profile,
            ExecutionContext context,
            DocumentRetrievalMode mode) {
        try {
            if (deadlineExpired(context.absoluteDeadline())) {
                throw new IllegalStateException("document embedding deadline expired");
            }
            var operationContext = context.operationContext(CapabilityOperationType.of("DOCUMENT_EMBEDDING"));
            var input = new DocumentEmbeddingInputProjection(List.of(request.getQueryText()));
            var decision = requireProviderDecision(
                    operationContext.operationType(), null, profile,
                    context, profile.embeddingPolicy(), DocumentProviderIntendedFieldView.queryOnly());
            DocumentUntrustedEmbeddingPayload payload = requireSuccess(embeddingPort.embed(
                    new DocumentEmbeddingOperationRequest(
                            input, providerRequestBinder.bind(decision, input, operationContext), operationContext)),
                    "embedding", operationContext);
            if (payload.vectors().size() != 1) {
                throw new IllegalStateException("document embedding must return exactly one vector");
            }
            DocumentEmbeddingResult result = new DocumentEmbeddingResult(
                    payload.vectors().getFirst().stream().map(Float::doubleValue).toList(),
                    payload.bindingReference().canonicalDigest(), payload.dimension(),
                    payload.bindingReference().canonicalDigest());
            recordProvider("embedding", mode.name(), "SUCCESS");
            return result;
        } catch (RuntimeException ex) {
            recordProvider("embedding", mode.name(), "FAILED");
            if (mode == DocumentRetrievalMode.HYBRID
                    && profile.embeddingPolicy() != DocumentFeaturePolicy.REQUIRED) {
                return null;
            }
            throw ex;
        }
    }

    private DocumentRetrievalExecution copyRequest(
            DocumentRetrievalExecution source,
            DocumentRetrievalMode mode,
            List<Double> queryVector) {
        return copyRequest(source, mode, queryVector, source.getRuleKeywords(), source.getRewriteCandidates());
    }

    private DocumentRetrievalExecution copyRequest(
            DocumentRetrievalExecution source,
            DocumentRetrievalMode mode,
            List<Double> queryVector,
            List<String> ruleKeywords,
            List<String> rewriteCandidates) {
        return source.copy(mode, queryVector, source.getEmbeddingBindingDigest(), ruleKeywords,
                rewriteCandidates, source.getProtectedFilterBinding());
    }

    private static List<String> queryVariants(DocumentRetrievalExecution request) {
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

    private AdapterDocumentRetrievalResult applyRerankIfEnabled(
            DocumentRetrievalExecution request,
            AdapterDocumentRetrievalResult adapterResult,
            List<SafeDocumentCandidate> safeCandidates,
            DocumentExecutionProfileProjection profile,
            ExecutionContext context) {
        DocumentChannelProfileProjection options = request.getChannelProjection();
        if (options == null || !options.rerankEnabled()
                || profile.rerankPolicy() == DocumentFeaturePolicy.DISABLED
                || documentLimits(context).enhancement().maxRerankCandidates() == 0) {
            markRerankDiagnostics(adapterResult, "SKIPPED", "DISABLED");
            return adapterResult;
        }
        try {
            List<AclBoundDocumentHit> hits = adapterResult.hits();
            if (safeCandidates.isEmpty()) {
                markRerankDiagnostics(adapterResult, "SKIPPED", "EMPTY_CANDIDATES");
                return adapterResult;
            }
            if (safeCandidates.size() != hits.size()) {
                throw new IllegalArgumentException("document rerank safe candidate count mismatch");
            }
            int maxCandidates = Math.min(
                    safeCandidates.size(), documentLimits(context).enhancement().maxRerankCandidates());
            DocumentProviderIntendedFieldView fieldView = providerFieldViewFromSafeCandidates(
                    profile.selectedCorpus().domain(), safeCandidates.subList(0, maxCandidates));
            var operationContext = context.operationContext(CapabilityOperationType.of("DOCUMENT_RERANK"));
            var decision = requireProviderDecision(
                    operationContext.operationType(), null, profile,
                    context, profile.rerankPolicy(), fieldView);
            List<DocumentRerankInputProjection.DocumentRerankInputItem> items = new ArrayList<>();
            for (int i = 0; i < maxCandidates; i++) {
                SafeDocumentCandidate evidence = safeCandidates.get(i);
                items.add(new DocumentRerankInputProjection.DocumentRerankInputItem(
                        evidence.candidateId(),
                        providerFieldProjector.stringValue(
                                decision, context.executionScope(), profile.selectedCorpus().domain(), "title", evidence.title()),
                        providerFieldProjector.stringValue(
                                decision, context.executionScope(), profile.selectedCorpus().domain(), "snippet", evidence.safeSnippet())));
            }
            var input = new DocumentRerankInputProjection(request.getQueryText(), items);
            DocumentUntrustedRerankPayload payload = requireSuccess(rerankPort.rerank(
                    new DocumentRerankOperationRequest(
                            input, providerRequestBinder.bind(decision, input, operationContext), operationContext)),
                    "rerank", operationContext);
            AdapterDocumentRetrievalResult result = applyRerankScores(adapterResult, maxCandidates, payload);
            markRerankDiagnostics(result, "SUCCEEDED", null);
            return result;
        } catch (RuntimeException ex) {
            log.warn("document rerank skipped: invocationId={}, domain={}, profile={}, reason={}",
                    context.invocationId(),
                    request.getDomain(),
                    request.getProfileName(),
                    ex.getClass().getSimpleName());
            if (profile.rerankPolicy() == DocumentFeaturePolicy.REQUIRED) {
                throw ex;
            }
            markRerankDiagnostics(adapterResult, "SKIPPED", ex.getClass().getSimpleName());
            return adapterResult;
        }
    }

    private static AdapterDocumentRetrievalResult applyRerankScores(
            AdapterDocumentRetrievalResult source,
            int rerankCandidateCount,
            DocumentUntrustedRerankPayload payload) {
        List<AclBoundDocumentHit> hits = source.hits();
        Map<String, AclBoundDocumentHit> eligible = new LinkedHashMap<>();
        for (int i = 0; i < rerankCandidateCount; i++) {
            AclBoundDocumentHit hit = hits.get(i);
            if (eligible.putIfAbsent(hit.candidateId(), hit) != null) {
                throw new IllegalArgumentException("duplicate rerank candidate id");
            }
        }
        Set<String> scored = new LinkedHashSet<>();
        List<AclBoundDocumentHit> ordered = payload.scores().stream()
                .peek(score -> {
                    if (!Double.isFinite(score.score()) || !eligible.containsKey(score.candidateId())
                            || !scored.add(score.candidateId())) {
                        throw new IllegalArgumentException("invalid rerank score binding");
                    }
                })
                .sorted(Comparator
                        .comparingDouble(DocumentUntrustedRerankPayload.DocumentRerankScoreItem::score).reversed()
                        .thenComparingInt(score -> indexOfCandidate(hits, score.candidateId())))
                .map(score -> eligible.get(score.candidateId()))
                .collect(java.util.stream.Collectors.toCollection(ArrayList::new));
        if (ordered.isEmpty()) {
            throw new IllegalArgumentException("empty rerank result");
        }
        hits.stream().filter(hit -> !scored.contains(hit.candidateId())).forEach(ordered::add);
        return new AdapterDocumentRetrievalResult(
                ordered, source.diagnostics(), source.binding(), source.requestedDocumentCount());
    }

    private static int indexOfCandidate(List<AclBoundDocumentHit> hits, String candidateId) {
        for (int i = 0; i < hits.size(); i++) {
            if (hits.get(i).candidateId().equals(candidateId)) return i;
        }
        return Integer.MAX_VALUE;
    }

    private static void markRerankDiagnostics(
            AdapterDocumentRetrievalResult result,
            String status,
            String skippedReason) {
        if (result == null) {
            return;
        }
        AdapterDocumentRetrievalDiagnostics diagnostics = result.diagnostics();
        diagnostics.setRerankStatus(status);
        diagnostics.setRerankSkippedReason(skippedReason);
    }

    private static AgentDocumentParameters toParameters(ValidatedDocumentPlan plan) {
        AgentDocumentParameters parameters = new AgentDocumentParameters();
        parameters.setDomain(plan.domain().orElseThrow());
        parameters.setMaterialType(plan.selectedCorpus().materialType());
        parameters.setOperation(plan.parameters().operation().name());
        parameters.setQueryText(plan.parameters().normalizedQuery());
        parameters.setFilters(plan.parameters().callerFilters().stream()
                .map(DocumentCapabilityHandler::toFilterParameter)
                .toList());
        parameters.setSorts(plan.parameters().sorts().stream()
                .map(sort -> {
                    AgentQuerySortParameter parameter = new AgentQuerySortParameter();
                    parameter.setField(sort.getField());
                    parameter.setDirection(sort.getDirection());
                    return parameter;
                })
                .toList());
        parameters.setTopK(plan.parameters().topK());
        parameters.setSummaryScope(plan.parameters().summaryScope() == null ? null : "CUSTOM");
        return parameters;
    }

    private AgentDocumentResult toResult(ValidatedDocumentPlan plan, AdapterDocumentRetrievalResult adapterResult,
                                         boolean selectionTruncated) {
        List<AclBoundDocumentHit> hits = adapterResult.hits();
        AgentDocumentResult result = new AgentDocumentResult();
        List<AgentDocumentHit> publicHits = new ArrayList<>();
        List<AgentDocumentCitation> citations = new ArrayList<>();
        for (int i = 0; i < hits.size(); i++) {
            String citationId = citationId(i);
            publicHits.add(toHit(hits.get(i), citationId));
            citations.add(toCitation(hits.get(i), citationId));
        }
        result.setHits(publicHits);
        result.setCitations(citations);
        result.setPartial(adapterResult.diagnostics().isDegraded());
        result.setGenerationStatus(DocumentGenerationStatus.DISABLED);
        var draft = coverageFactory.create(plan, hits, adapterResult.diagnostics().isDegraded(), selectionTruncated);
        AgentDocumentCoverage coverage = new AgentDocumentCoverage();
        coverage.setRequestedDocumentCount(draft.requestedDocumentCount());
        coverage.setRequestedCountKnown(draft.requestedCountKnown());
        coverage.setCoveredDocumentCount(draft.coveredDocumentCount());
        coverage.setEvidenceCount(draft.evidenceCount());
        coverage.setTruncated(draft.truncated());
        result.setCoverage(coverage);
        return result;
    }

    private DocumentProviderBindingReference applyGenerationIfEnabled(
            ValidatedDocumentPlan plan,
            DocumentRetrievalExecution retrievalRequest,
            AdapterDocumentRetrievalResult adapterResult,
            AgentDocumentResult result,
            ExecutionContext context) {
        if (retrievalRequest.getOperation() == com.dylan.agent.api.plan.DocumentPlanOperation.SEARCH) {
            result.setGenerationStatus(DocumentGenerationStatus.DISABLED);
            result.setGroundingStatus(adapterResult.hits().isEmpty() ? GroundingStatus.NO_EVIDENCE : GroundingStatus.VERIFIED);
            return null;
        }
        DocumentGenerationOptions options = plan.generationOptions().orElse(null);
        boolean requested = options != null && Boolean.TRUE.equals(options.getEnabled());
        if (!requested) {
            result.setGenerationStatus(DocumentGenerationStatus.DISABLED);
            return null;
        }
        List<AclBoundDocumentHit> filteredEvidence = adapterResult.hits();
        DocumentResourceLimit limits = documentLimits(context);
        if (filteredEvidence.isEmpty()) {
            result.setGenerationStatus(DocumentGenerationStatus.SKIPPED);
            result.setGroundingStatus(GroundingStatus.NO_EVIDENCE);
            return null;
        }
        if (plan.profile().generationPolicy() == DocumentFeaturePolicy.DISABLED) {
            fallbackOrFail(result, options, plan, filteredEvidence, limits, false);
            return null;
        }
        int maxOutputChars = resolveMaxOutputChars(options, plan, limits);
        DocumentEvidencePackingLimit budget = new DocumentEvidencePackingLimit(
                limits.output().maxContextChars(),
                limits.output().maxEvidenceChars(),
                limits.output().maxSnippetChars(),
                limits.output().maxEvidenceCount());
        DocumentProviderBindingReference usedProvider = null;
        try {
            if (deadlineExpired(context.absoluteDeadline())) {
                throw new IllegalStateException("document generation deadline expired");
            }
            var operationContext = context.operationContext(CapabilityOperationType.of("DOCUMENT_GENERATION"));
            var decision = requireProviderDecision(
                    operationContext.operationType(), plan, context,
                    plan.profile().generationPolicy(),
                    providerFieldView(plan.selectedCorpus().domain(), filteredEvidence, true));
            var generationProjection = generationEvidenceProjector.project(
                    filteredEvidence, budget, decision, context.executionScope());
            var evidencePackage = evidenceContextPackageFactory.create(
                    new EvidenceContextPackageRequest(
                            plan, context, adapterResult.binding(), decision), generationProjection);
            DocumentGeneratedTextCandidate generated;
            try {
                DocumentGenerationInstructionCode instruction = retrievalRequest.getOperation()
                        == com.dylan.agent.api.plan.DocumentPlanOperation.ANSWER
                        ? DocumentGenerationInstructionCode.ANSWER_WITH_CITATIONS
                        : DocumentGenerationInstructionCode.SUMMARIZE_WITH_CITATIONS;
                DocumentGenerationOutputShape shape = retrievalRequest.getOperation()
                        == com.dylan.agent.api.plan.DocumentPlanOperation.ANSWER
                        ? DocumentGenerationOutputShape.ANSWER : DocumentGenerationOutputShape.SUMMARY;
                var input = generationInputProjector.project(evidencePackage, instruction, shape);
                var request = new DocumentGenerationOperationRequest(
                        input, providerRequestBinder.bind(decision, input, operationContext), operationContext);
                var outcome = generationPort.generate(request);
                generated = generatedTextCandidateFactory.create(
                        evidencePackage, request, outcome, plan,
                        context.executionScope(), context.resourceLimits());
                usedProvider = generated.providerBinding();
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
            if (verification.verified()) {
                validateGeneratedLimits(generated.content(), generated.citedIds(), limits, maxOutputChars);
                result.setAnswerText(generated.content().answerText());
                result.setSummaryText(generated.content().summaryText());
                result.setSummaryBullets(generated.content().summaryBullets());
                result.setGenerationStatus(DocumentGenerationStatus.SUCCEEDED);
            } else {
                fallbackOrFail(result, options, plan, filteredEvidence, limits,
                        plan.profile().generationPolicy() == DocumentFeaturePolicy.REQUIRED);
            }
        } catch (RuntimeException ex) {
            fallbackOrFail(result, options, plan, filteredEvidence, limits,
                    plan.profile().generationPolicy() == DocumentFeaturePolicy.REQUIRED);
        }
        return usedProvider;
    }

    private static boolean deadlineExpired(Instant deadline) {
        return deadline == null || !deadline.isAfter(Instant.now());
    }

    private static DocumentResourceLimit documentLimits(ExecutionContext context) {
        return context.resourceLimits().require(
                AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, DocumentResourceLimit.class);
    }

    private static <T> T requireSuccess(
            CapabilityOperationOutcome<T> outcome,
            String operation,
            com.dylan.agent.adapter.api.operation.CapabilityOperationContext operationContext) {
        try {
            return com.dylan.agent.adapter.api.operation.CapabilityOperationOutcomes
                    .requireBoundSuccess(outcome, operationContext);
        } catch (RuntimeException ex) {
            throw new IllegalStateException("document " + operation + " outcome rejected", ex);
        }
    }

    private void recordRetrieval(DocumentRetrievalExecution request, String result, long startedNanos) {
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

    private void recordRevocation(String target, String source) {
        if (observabilitySupport != null) {
            observabilitySupport.recordRevocationHit(target, source);
        }
    }

    private void recordRetrievalDiagnostics(
            DocumentRetrievalExecution request,
            AdapterDocumentRetrievalResult adapterResult) {
        if (observabilitySupport == null || adapterResult == null) {
            return;
        }
        observabilitySupport.recordRetrievalDiagnostics(
                request.getDomain(),
                request.getRetrievalMode().name(),
                adapterResult.diagnostics());
    }

    private int resolveMaxOutputChars(
            DocumentGenerationOptions options,
            ValidatedDocumentPlan plan,
            DocumentResourceLimit limits) {
        int operationLimit = plan.parameters().operation()
                == com.dylan.agent.api.plan.DocumentPlanOperation.SUMMARIZE
                ? limits.output().maxSummaryChars()
                : limits.output().maxGeneratedChars();
        int outputLimit = options.getMaxOutputChars() == null
                ? operationLimit
                : options.getMaxOutputChars();
        var summaryScope = plan.parameters().summaryScope();
        if (plan.parameters().operation() == com.dylan.agent.api.plan.DocumentPlanOperation.SUMMARIZE
                && summaryScope != null
                && summaryScope.getMaxSummaryChars() != null) {
            return Math.min(outputLimit, summaryScope.getMaxSummaryChars());
        }
        return outputLimit;
    }

    private void fallbackOrFail(AgentDocumentResult result, DocumentGenerationOptions options,
                                ValidatedDocumentPlan plan, List<AclBoundDocumentHit> evidence,
                                DocumentResourceLimit limits, boolean required) {
        if (required) throw new IllegalStateException("required document generation failed");
        AgentDocumentCitationVerification verification = result.getCitationVerification();
        if (verification == null) {
            verification = new AgentDocumentCitationVerification();
            verification.setBoundUnitCount(0);
            verification.setVisibleCitationCount(result.getCitations() == null ? 0 : result.getCitations().size());
            result.setCitationVerification(verification);
        }
        if (options == null || options.getFailurePolicy() != DocumentGenerationFailurePolicy.FALLBACK_EXTRACTIVE) {
            clearGeneratedText(result);
            result.setGenerationStatus(DocumentGenerationStatus.FAILED);
            result.setGroundingStatus(GroundingStatus.UNVERIFIED);
        } else {
            int maxOutput = resolveMaxOutputChars(options, plan, limits);
            var fallback = fallbackComposer.compose(plan.parameters().operation(), evidence, maxOutput,
                    Math.min(maxOutput, limits.output().maxSummaryChars()), limits.output().maxSummaryBullets());
            if (fallback.refused()) {
                clearGeneratedText(result);
                result.setGenerationStatus(DocumentGenerationStatus.FAILED);
                result.setGroundingStatus(GroundingStatus.UNVERIFIED);
                return;
            }
            result.setAnswerText(fallback.answerText()); result.setSummaryText(fallback.summaryText());
            result.setSummaryBullets(fallback.summaryBullets()); result.setGenerationStatus(DocumentGenerationStatus.FALLBACK);
            result.setGroundingStatus(GroundingStatus.VERIFIED);
            verification.setStatus(GroundingStatus.VERIFIED);
            verification.setBoundUnitCount(plan.parameters().operation() == com.dylan.agent.api.plan.DocumentPlanOperation.ANSWER
                    ? countVisibleUnits(fallback.answerText()) : fallback.summaryBullets().size());
            verification.setVisibleCitationCount(fallback.citedIds().size());
        }
    }

    private AgentDocumentCitationVerification toApiVerification(CitationVerificationResult verification) {
        AgentDocumentCitationVerification api = new AgentDocumentCitationVerification();
        api.setStatus(verification.status());
        api.setBoundUnitCount(verification.boundUnitCount());
        api.setVisibleCitationCount(verification.visibleCitationCount());
        return api;
    }

    private static void validateGeneratedLimits(DocumentGeneratedContent generated,
                                                List<String> citedIds,
                                                DocumentResourceLimit limits, int maxOutputChars) {
        if (codePoints(generated.answerText()) > maxOutputChars
                || summaryChars(generated) > Math.min(maxOutputChars, limits.output().maxSummaryChars())
                || generated.summaryBullets().size() > limits.output().maxSummaryBullets()
                || citedIds.size() > limits.output().maxCitationCount()) {
            throw new IllegalStateException("document generated output exceeds limits");
        }
    }

    private static int summaryChars(DocumentGeneratedContent generated) {
        int total = codePoints(generated.summaryText());
        for (String bullet : generated.summaryBullets()) {
            total = Math.addExact(total, codePoints(bullet));
        }
        return total;
    }

    private DocumentProviderOutboundPolicyDecision requireProviderDecision(
            CapabilityOperationType type,
            ValidatedDocumentPlan plan,
            ExecutionContext context,
            DocumentFeaturePolicy feature,
            DocumentProviderIntendedFieldView fieldView) {
        return requireProviderDecision(type, plan, plan.profile(), context, feature, fieldView);
    }

    private DocumentProviderOutboundPolicyDecision requireProviderDecision(
            CapabilityOperationType type,
            ValidatedDocumentPlan plan,
            DocumentExecutionProfileProjection profile,
            ExecutionContext context,
            DocumentFeaturePolicy feature,
            DocumentProviderIntendedFieldView fieldView) {
        var corpus = plan == null ? profile.selectedCorpus() : plan.selectedCorpus();
        DocumentProviderOutboundPolicyDecisionResult decision = providerPolicyDecisionFactory.create(
                type, context.executionScope(), corpus, feature, fieldView,
                profile.profileProjectionDigest(), context.absoluteDeadline());
        if (decision instanceof DocumentProviderOutboundPolicyAllowed allowed) {
            return allowed.decision();
        }
        var denied = (DocumentProviderOutboundPolicyDenied) decision;
        throw new IllegalStateException("document provider is not eligible: " + denied.reasonCode());
    }

    private static DocumentProviderIntendedFieldView providerFieldView(
            String domain,
            List<AclBoundDocumentHit> evidence,
            boolean generation) {
        List<com.dylan.agent.metadata.domain.port.CanonicalFieldRef> fields = new ArrayList<>();
        if (evidence.stream().anyMatch(item -> item.title() != null)) {
            fields.add(new com.dylan.agent.metadata.domain.port.CanonicalFieldRef(domain, "title"));
        }
        if (generation && evidence.stream().anyMatch(item -> item.section() != null)) {
            fields.add(new com.dylan.agent.metadata.domain.port.CanonicalFieldRef(domain, "section"));
        }
        if (generation && evidence.stream().anyMatch(item -> item.page() != null)) {
            fields.add(new com.dylan.agent.metadata.domain.port.CanonicalFieldRef(domain, "page"));
        }
        if ((generation && !evidence.isEmpty())
                || evidence.stream().anyMatch(item -> item.snippet() != null)) {
            fields.add(new com.dylan.agent.metadata.domain.port.CanonicalFieldRef(domain, "snippet"));
        }
        return new DocumentProviderIntendedFieldView(fields);
    }

    private static DocumentProviderIntendedFieldView providerFieldViewFromSafeCandidates(
            String domain,
            List<SafeDocumentCandidate> candidates) {
        List<com.dylan.agent.metadata.domain.port.CanonicalFieldRef> fields = new ArrayList<>();
        if (candidates.stream().anyMatch(item -> item.title() != null)) {
            fields.add(new com.dylan.agent.metadata.domain.port.CanonicalFieldRef(domain, "title"));
        }
        if (candidates.stream().anyMatch(item -> item.safeSnippet() != null)) {
            fields.add(new com.dylan.agent.metadata.domain.port.CanonicalFieldRef(domain, "snippet"));
        }
        return new DocumentProviderIntendedFieldView(fields);
    }
    private static int codePoints(String value) { return value == null ? 0 : value.codePointCount(0, value.length()); }
    private static int countVisibleUnits(String value) { if (value == null || value.isBlank()) return 0; return (int) java.util.Arrays.stream(value.split("(?:\\R\\s*){2,}|\\R")).filter(unit -> !unit.isBlank()).count(); }
    private static void clearGeneratedText(AgentDocumentResult result) { result.setAnswerText(null); result.setSummaryText(null); result.setSummaryBullets(List.of()); }

    private int enforceResultSize(DocumentAgentResultPayload payload, ValidatedDocumentPlan plan,
                                  List<AclBoundDocumentHit> evidence, DocumentResourceLimit limits) {
        long maxBytes = limits.output().maxResultBytes();
        if (resultSizeGuard.fits(payload, maxBytes)) return evidence.size();
        if (plan.parameters().operation() == com.dylan.agent.api.plan.DocumentPlanOperation.SEARCH) {
            return resultSizeGuard.reduceEvidenceOnly(payload, maxBytes);
        }
        if (plan.profile().generationPolicy() == DocumentFeaturePolicy.REQUIRED) {
            throw new IllegalStateException("required document result exceeds byte limit");
        }
        fallbackOrFail(payload.getDocumentResult(), plan.generationOptions().orElse(null), plan, evidence, limits, false);
        if (resultSizeGuard.fits(payload, maxBytes)) return evidence.size();
        clearGeneratedText(payload.getDocumentResult());
        payload.getDocumentResult().setGenerationStatus(DocumentGenerationStatus.FAILED);
        payload.getDocumentResult().setGroundingStatus(GroundingStatus.UNVERIFIED);
        int retained = resultSizeGuard.reduceEvidenceOnly(payload, maxBytes);
        if (payload.getDocumentResult().getCitationVerification() != null) {
            payload.getDocumentResult().getCitationVerification().setVisibleCitationCount(retained);
            payload.getDocumentResult().getCitationVerification().setBoundUnitCount(0);
            payload.getDocumentResult().getCitationVerification().setStatus(GroundingStatus.UNVERIFIED);
        }
        return retained;
    }

    private static ContextWriteCandidate toContextWrite(
            ValidatedDocumentPlan plan,
            AdapterDocumentRetrievalResult adapterResult) {
        return new ContextWriteCandidate(
                RuntimeContextType.DOCUMENT,
                AgentExecutionContracts.DOCUMENT_CONTEXT,
                new DocumentCapabilityContextPayload(
                        plan.parameters().operation().name(),
                        plan.domain().orElseThrow(),
                        plan.selectedCorpus().materialType(),
                        plan.parameters().normalizedQuery(),
                        plan.parameters().callerFilters().stream()
                                .map(DocumentCapabilityHandler::toAgentFilter)
                                .toList(),
                        plan.parameters().topK(),
                        plan.parameters().summaryScope() == null ? null : "CUSTOM"));
    }

    private static AgentDocumentHit toHit(AclBoundDocumentHit evidence, String citationId) {
        AgentDocumentHit hit = new AgentDocumentHit();
        hit.setDocumentId(evidence.identity().documentId());
        hit.setTitle(evidence.title());
        hit.setSourceType(evidence.sourceType());
        hit.setSnippet(displaySnippet(evidence));
        hit.setScore(evidence.score());
        hit.setCitationIds(List.of(citationId));
        return hit;
    }

    private static AgentDocumentCitation toCitation(AclBoundDocumentHit evidence, String citationId) {
        AgentDocumentCitation citation = new AgentDocumentCitation();
        citation.setCitationId(citationId);
        citation.setDocumentId(evidence.identity().documentId());
        citation.setTitle(evidence.title());
        citation.setSection(evidence.section());
        citation.setPage(evidence.page());
        citation.setSourceUri(evidence.sourceUri());
        citation.setSnippet(displaySnippet(evidence));
        citation.setChunkIndex(evidence.identity().chunkIndex());
        citation.setCharStart(evidence.charStart());
        citation.setCharEnd(evidence.charEnd());
        return citation;
    }

    private static String displaySnippet(AclBoundDocumentHit evidence) {
        if (evidence == null) {
            return null;
        }
        if (evidence.citationText() != null && !evidence.citationText().isBlank()) {
            return evidence.citationText();
        }
        return evidence.snippet();
    }

    private static String citationId(int index) {
        return "C" + (index + 1);
    }

    private static List<String> citationIds(List<AclBoundDocumentHit> hits) {
        List<String> ids = new ArrayList<>(hits.size());
        for (int i = 0; i < hits.size(); i++) ids.add(citationId(i));
        return List.copyOf(ids);
    }

    private static AgentQueryFilterParameter toFilterParameter(ValidatedFilter filter) {
        AgentQueryFilterParameter parameter = new AgentQueryFilterParameter();
        parameter.setField(filter.getField());
        parameter.setOperator(filter.getOperator());
        parameter.setValue(filter.getValue());
        parameter.setValues(filter.getValues().isEmpty() ? null : filter.getValues());
        return parameter;
    }

    private static AgentQueryFilterParameter toFilterParameter(
            com.dylan.agent.adapter.api.document.ValidatedDocumentCallerFilter filter) {
        AgentQueryFilterParameter parameter = new AgentQueryFilterParameter();
        parameter.setField(filter.field());
        parameter.setOperator(com.dylan.agent.api.enums.AgentOperator.valueOf(filter.operator().name()));
        parameter.setValue(filter.value());
        parameter.setValues(filter.values().isEmpty() ? null : filter.values());
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

    private static AgentFilter toAgentFilter(
            com.dylan.agent.adapter.api.document.ValidatedDocumentCallerFilter filter) {
        AgentFilter agentFilter = new AgentFilter();
        agentFilter.setField(filter.field());
        agentFilter.setOperator(com.dylan.agent.api.enums.AgentOperator.valueOf(filter.operator().name()));
        agentFilter.setValue(filter.value());
        agentFilter.setValues(filter.values());
        return agentFilter;
    }

}
