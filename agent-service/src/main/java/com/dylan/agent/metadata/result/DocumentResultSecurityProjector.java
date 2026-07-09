package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.response.AgentDocumentCitation;
import com.dylan.agent.api.response.AgentDocumentCoverage;
import com.dylan.agent.api.response.AgentDocumentHit;
import com.dylan.agent.api.response.AgentDocumentParameters;
import com.dylan.agent.api.response.AgentDocumentResult;
import com.dylan.agent.api.response.DocumentGenerationStatus;
import com.dylan.agent.api.response.GroundingStatus;
import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.api.response.AgentQuerySortParameter;
import com.dylan.agent.api.response.DocumentAgentResultPayload;
import com.dylan.agent.capability.document.DocumentObservabilitySupport;
import com.dylan.agent.capability.document.security.DocumentRevocationGuard;
import com.dylan.agent.capability.document.security.DocumentRevocationDecision;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

public final class DocumentResultSecurityProjector implements ResultSecurityProjector<DocumentAgentResultPayload> {

    private static final Pattern CITATION_PATTERN = Pattern.compile("\\[([^\\]]+)]");
    private static final String TITLE_FIELD = "title";
    private static final String SOURCE_TYPE_FIELD = "sourceType";
    private static final String SECTION_FIELD = "section";
    private static final String PAGE_FIELD = "page";
    private static final String SOURCE_URI_FIELD = "sourceUri";
    private static final String SNIPPET_FIELD = "snippet";

    private final ResultValueMaskingSupport maskingSupport;
    private final AgentProperties properties;
    private final DocumentRevocationGuard revocationGuard;
    private final DocumentObservabilitySupport observabilitySupport;

    public DocumentResultSecurityProjector(ResultValueMaskingSupport maskingSupport, AgentProperties properties) {
        this(maskingSupport, properties, new DocumentRevocationGuard(properties));
    }

    public DocumentResultSecurityProjector(
            ResultValueMaskingSupport maskingSupport,
            AgentProperties properties,
            DocumentRevocationGuard revocationGuard) {
        this(maskingSupport, properties, revocationGuard, null);
    }

    public DocumentResultSecurityProjector(
            ResultValueMaskingSupport maskingSupport,
            AgentProperties properties,
            DocumentRevocationGuard revocationGuard,
            DocumentObservabilitySupport observabilitySupport) {
        this.maskingSupport = Objects.requireNonNull(maskingSupport, "maskingSupport must not be null");
        this.properties = Objects.requireNonNull(properties, "properties must not be null");
        this.revocationGuard = Objects.requireNonNull(revocationGuard, "revocationGuard must not be null");
        this.observabilitySupport = observabilitySupport;
    }

    @Override
    public ContractRef supports() { return AgentExecutionContracts.DOCUMENT_RESULT; }

    @Override
    public Class<DocumentAgentResultPayload> payloadType() { return DocumentAgentResultPayload.class; }

    @Override
    public FilteredResult<DocumentAgentResultPayload> filter(DocumentAgentResultPayload candidate, ExecutionScope scope) {
        try {
            AgentDocumentParameters parameters = candidate.getDocumentParameters();
            String domain = parameters == null ? null : parameters.getDomain();
            if (domain == null || domain.isBlank()) {
                throw new IllegalStateException("document result payload missing domain");
            }
            if (!scope.allowedDomains().contains(domain)) {
                throw new IllegalStateException("document result domain outside execution scope");
            }
            DocumentRevocationDecision decision = revocationGuard.evaluate(
                    domain,
                    null,
                    parameters.getRetrievalProfile(),
                    parameters.getProfileVersion(),
                    parameters.getIndexAlias());
            if (decision.revoked()) {
                recordRevocation(decision);
                throw new IllegalStateException("document access revoked by "
                        + decision.source() + ":" + decision.target());
            }
            AgentDocumentResult result = filterResult(domain, candidate.getDocumentResult(), scope);
            DocumentPlanOperation operation = parseOperation(parameters.getOperation());
            if (!applyVerifiedCandidate(operation, result)) {
                DocumentSafeTextComposer.compose(operation, result, properties.getDocument().getMaxSummaryChars());
            }
            clearCandidateText(result);
            DocumentAgentResultPayload filtered = new DocumentAgentResultPayload(
                    filterParameters(domain, parameters, scope),
                    result);
            recordResultSecurity("FILTERED");
            return new FilteredResult<>(filtered, "文档处理完成", "文档结果已按当前执行范围过滤和脱敏");
        } catch (RuntimeException ex) {
            recordResultSecurity("FAILED");
            throw ex;
        }
    }

    private void recordResultSecurity(String decision) {
        if (observabilitySupport != null) {
            observabilitySupport.recordResultSecurity(decision);
        }
    }

    private void recordRevocation(DocumentRevocationDecision decision) {
        if (observabilitySupport != null) {
            observabilitySupport.recordRevocationHit(decision.target(), decision.source());
        }
    }

    private AgentDocumentParameters filterParameters(
            String domain,
            AgentDocumentParameters source,
            ExecutionScope scope) {
        AgentDocumentParameters target = new AgentDocumentParameters();
        target.setDomain(source.getDomain());
        target.setMaterialType(source.getMaterialType());
        target.setRetrievalProfile(source.getRetrievalProfile());
        target.setProfileVersion(source.getProfileVersion());
        target.setIndexAlias(source.getIndexAlias());
        target.setOperation(source.getOperation());
        target.setQueryText(source.getQueryText());
        target.setTopK(source.getTopK());
        target.setSummaryScope(source.getSummaryScope());
        target.setFilters(source.getFilters() == null ? null : source.getFilters().stream()
                .map(filter -> maskingSupport.filterAndMaskFilter(domain, filter, scope))
                .filter(Objects::nonNull)
                .toList());
        target.setSorts(source.getSorts() == null ? null : source.getSorts().stream()
                .filter(sort -> sort != null
                        && maskingSupport.filterFields(domain, List.of(sort.getField()), scope).contains(sort.getField()))
                .map(DocumentResultSecurityProjector::copySort)
                .toList());
        return target;
    }

    private AgentDocumentResult filterResult(
            String domain,
            AgentDocumentResult source,
            ExecutionScope scope) {
        AgentDocumentResult target = new AgentDocumentResult();
        if (source == null) {
            source = new AgentDocumentResult();
        }
        target.setHits(source.getHits() == null ? List.of() : source.getHits().stream()
                .map(hit -> filterHit(domain, hit, scope))
                .filter(Objects::nonNull)
                .limit(properties.getDocument().getMaxEvidenceCount())
                .toList());
        target.setCitations(source.getCitations() == null ? List.of() : source.getCitations().stream()
                .map(citation -> filterCitation(domain, citation, scope))
                .filter(Objects::nonNull)
                .limit(properties.getDocument().getMaxEvidenceCount())
                .toList());
        target.setPartial(source.isPartial());
        target.setCoverage(filterCoverage(source.getCoverage(), target.getCitations()));
        target.setGenerationStatus(source.getGenerationStatus());
        target.setGroundingStatus(source.getGroundingStatus());
        target.setCitationVerification(source.getCitationVerification());
        target.setCandidateAnswerText(source.getCandidateAnswerText());
        target.setCandidateSummaryText(source.getCandidateSummaryText());
        target.setCandidateSummaryBullets(source.getCandidateSummaryBullets());
        return target;
    }

    private AgentDocumentHit filterHit(String domain, AgentDocumentHit source, ExecutionScope scope) {
        if (source == null) {
            return null;
        }
        AgentDocumentHit target = new AgentDocumentHit();
        String title = filterString(domain, TITLE_FIELD, source.getTitle(), scope);
        String sourceType = filterString(domain, SOURCE_TYPE_FIELD, source.getSourceType(), scope);
        String snippet = filterString(domain, SNIPPET_FIELD, source.getSnippet(), scope);
        if (title == null && sourceType == null && snippet == null) {
            return null;
        }
        target.setDocumentId(source.getDocumentId());
        target.setTitle(title);
        target.setSourceType(sourceType);
        target.setSnippet(truncate(snippet));
        target.setScore(source.getScore());
        target.setCitationIds(source.getCitationIds() == null ? List.of() : source.getCitationIds());
        return target;
    }

    private AgentDocumentCitation filterCitation(String domain, AgentDocumentCitation source, ExecutionScope scope) {
        if (source == null) {
            return null;
        }
        String snippet = filterString(domain, SNIPPET_FIELD, source.getSnippet(), scope);
        if (snippet == null) {
            return null;
        }
        AgentDocumentCitation target = new AgentDocumentCitation();
        target.setCitationId(source.getCitationId());
        target.setDocumentId(source.getDocumentId());
        target.setTitle(filterString(domain, TITLE_FIELD, source.getTitle(), scope));
        target.setSection(filterString(domain, SECTION_FIELD, source.getSection(), scope));
        target.setPage(filterInteger(domain, PAGE_FIELD, source.getPage(), scope));
        target.setSourceUri(filterString(domain, SOURCE_URI_FIELD, source.getSourceUri(), scope));
        target.setSnippet(truncate(snippet));
        target.setChunkIndex(source.getChunkIndex());
        target.setCharStart(source.getCharStart());
        target.setCharEnd(source.getCharEnd());
        return target;
    }

    private AgentDocumentCoverage filterCoverage(AgentDocumentCoverage source, List<AgentDocumentCitation> citations) {
        AgentDocumentCoverage target = new AgentDocumentCoverage();
        int evidenceCount = citations.size();
        int coveredDocumentCount = (int) citations.stream()
                .map(AgentDocumentCitation::getDocumentId)
                .filter(value -> value != null && !value.isBlank())
                .distinct()
                .count();
        if (source != null) {
            target.setRequestedDocumentCount(source.getRequestedDocumentCount());
            boolean securityFiltered = source.getEvidenceCount() > evidenceCount
                    || source.getCoveredDocumentCount() > coveredDocumentCount;
            target.setTruncated(source.isTruncated() || securityFiltered);
        }
        target.setCoveredDocumentCount(coveredDocumentCount);
        target.setEvidenceCount(evidenceCount);
        return target;
    }

    private String truncate(String value) {
        if (value == null) {
            return null;
        }
        int limit = properties.getDocument().getMaxSnippetChars();
        return value.length() <= limit ? value : value.substring(0, limit);
    }

    private String filterString(String domain, String field, String value, ExecutionScope scope) {
        if (value == null || !maskingSupport.allowedFields(domain, scope).contains(field)) {
            return null;
        }
        return maskingSupport.maskStringValue(domain, field, value, scope);
    }

    private Integer filterInteger(String domain, String field, Integer value, ExecutionScope scope) {
        if (value == null || !maskingSupport.allowedFields(domain, scope).contains(field)) {
            return null;
        }
        return value;
    }

    private boolean applyVerifiedCandidate(DocumentPlanOperation operation, AgentDocumentResult result) {
        if (result.getGenerationStatus() != DocumentGenerationStatus.SUCCEEDED
                || result.getGroundingStatus() != GroundingStatus.VERIFIED
                || result.getCitations() == null
                || result.getCitations().isEmpty()) {
            return false;
        }
        if (operation == DocumentPlanOperation.ANSWER
                && result.getCandidateAnswerText() != null
                && !result.getCandidateAnswerText().isBlank()) {
            if (!candidateCitationsValid(result, List.of(result.getCandidateAnswerText()))) {
                markGeneratedCandidateFallback(result);
                return false;
            }
            result.setAnswerText(truncateGeneratedText(result.getCandidateAnswerText()));
            return true;
        }
        if (operation == DocumentPlanOperation.SUMMARIZE
                && result.getCandidateSummaryText() != null
                && !result.getCandidateSummaryText().isBlank()) {
            List<String> summaryTexts = new java.util.ArrayList<>();
            summaryTexts.add(result.getCandidateSummaryText());
            if (result.getCandidateSummaryBullets() != null) {
                summaryTexts.addAll(result.getCandidateSummaryBullets());
            }
            if (!candidateCitationsValid(result, summaryTexts)) {
                markGeneratedCandidateFallback(result);
                return false;
            }
            result.setSummaryText(truncateGeneratedText(result.getCandidateSummaryText()));
            result.setSummaryBullets(result.getCandidateSummaryBullets() == null ? null : result.getCandidateSummaryBullets().stream()
                    .map(this::truncateGeneratedText)
                    .toList());
            return true;
        }
        return false;
    }

    private String truncateGeneratedText(String value) {
        if (value == null) {
            return null;
        }
        int limit = properties.getDocument().getGeneration().getMaxOutputChars();
        return value.length() <= limit ? value : value.substring(0, limit);
    }

    private boolean candidateCitationsValid(AgentDocumentResult result, List<String> texts) {
        Set<String> allowedCitationIds = result.getCitations().stream()
                .filter(citation -> citation.getSnippet() != null && !citation.getSnippet().isBlank())
                .map(AgentDocumentCitation::getCitationId)
                .filter(Objects::nonNull)
                .collect(Collectors.toUnmodifiableSet());
        List<String> checkedTexts = texts.stream()
                .filter(text -> text != null && !text.isBlank())
                .toList();
        return !checkedTexts.isEmpty() && checkedTexts.stream()
                .allMatch(text -> {
                    Set<String> referencedCitationIds = citationIds(text);
                    return !referencedCitationIds.isEmpty()
                            && allowedCitationIds.containsAll(referencedCitationIds);
                });
    }

    private static Set<String> citationIds(String text) {
        return CITATION_PATTERN.matcher(text).results()
                .map(match -> match.group(1).trim())
                .filter(value -> !value.isBlank())
                .collect(Collectors.toUnmodifiableSet());
    }

    private static void markGeneratedCandidateFallback(AgentDocumentResult result) {
        result.setGenerationStatus(DocumentGenerationStatus.FALLBACK);
        result.setGroundingStatus(GroundingStatus.UNVERIFIED);
    }

    private static void clearCandidateText(AgentDocumentResult result) {
        result.setCandidateAnswerText(null);
        result.setCandidateSummaryText(null);
        result.setCandidateSummaryBullets(null);
    }

    private static AgentQuerySortParameter copySort(AgentQuerySortParameter source) {
        AgentQuerySortParameter target = new AgentQuerySortParameter();
        target.setField(source.getField());
        target.setDirection(source.getDirection());
        return target;
    }

    private static DocumentPlanOperation parseOperation(String operation) {
        try {
            return DocumentPlanOperation.valueOf(operation);
        } catch (RuntimeException ex) {
            throw new IllegalStateException("invalid document operation", ex);
        }
    }
}
