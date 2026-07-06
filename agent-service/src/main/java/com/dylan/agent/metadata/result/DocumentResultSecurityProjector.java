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
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

public final class DocumentResultSecurityProjector implements ResultSecurityProjector<DocumentAgentResultPayload> {

    private static final Pattern CITATION_PATTERN = Pattern.compile("\\[([^\\]]+)]");

    private final ResultValueMaskingSupport maskingSupport;
    private final AgentProperties properties;

    public DocumentResultSecurityProjector(ResultValueMaskingSupport maskingSupport, AgentProperties properties) {
        this.maskingSupport = Objects.requireNonNull(maskingSupport, "maskingSupport must not be null");
        this.properties = Objects.requireNonNull(properties, "properties must not be null");
    }

    @Override
    public ContractRef supports() { return AgentExecutionContracts.DOCUMENT_RESULT; }

    @Override
    public Class<DocumentAgentResultPayload> payloadType() { return DocumentAgentResultPayload.class; }

    @Override
    public FilteredResult<DocumentAgentResultPayload> filter(DocumentAgentResultPayload candidate, ExecutionScope scope) {
        AgentDocumentParameters parameters = candidate.getDocumentParameters();
        String domain = parameters == null ? null : parameters.getDomain();
        if (domain == null || domain.isBlank()) {
            throw new IllegalStateException("document result payload missing domain");
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
        return new FilteredResult<>(filtered, "文档处理完成", "文档结果已按当前执行范围过滤和脱敏");
    }

    private AgentDocumentParameters filterParameters(
            String domain,
            AgentDocumentParameters source,
            ExecutionScope scope) {
        AgentDocumentParameters target = new AgentDocumentParameters();
        target.setDomain(source.getDomain());
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
        target.setCoverage(filterCoverage(source.getCoverage(), target.getCitations().size()));
        target.setGenerationStatus(source.getGenerationStatus());
        target.setGroundingStatus(source.getGroundingStatus());
        target.setCitationVerification(source.getCitationVerification());
        target.setCandidateAnswerText(source.getCandidateAnswerText());
        target.setCandidateSummaryText(source.getCandidateSummaryText());
        target.setCandidateSummaryBullets(source.getCandidateSummaryBullets());
        return target;
    }

    private AgentDocumentHit filterHit(String domain, AgentDocumentHit source, ExecutionScope scope) {
        if (source == null || !isAllowedDocumentEvidence(domain, scope)) {
            return null;
        }
        AgentDocumentHit target = new AgentDocumentHit();
        target.setDocumentId(source.getDocumentId());
        target.setTitle(source.getTitle());
        target.setSourceType(source.getSourceType());
        target.setSnippet(truncate(source.getSnippet()));
        target.setScore(source.getScore());
        target.setCitationIds(source.getCitationIds() == null ? List.of() : source.getCitationIds());
        return target;
    }

    private AgentDocumentCitation filterCitation(String domain, AgentDocumentCitation source, ExecutionScope scope) {
        if (source == null || !isAllowedDocumentEvidence(domain, scope)) {
            return null;
        }
        AgentDocumentCitation target = new AgentDocumentCitation();
        target.setCitationId(source.getCitationId());
        target.setDocumentId(source.getDocumentId());
        target.setTitle(source.getTitle());
        target.setSection(source.getSection());
        target.setPage(source.getPage());
        target.setSourceUri(source.getSourceUri());
        target.setSnippet(truncate(source.getSnippet()));
        target.setChunkIndex(source.getChunkIndex());
        target.setCharStart(source.getCharStart());
        target.setCharEnd(source.getCharEnd());
        return target;
    }

    private AgentDocumentCoverage filterCoverage(AgentDocumentCoverage source, int evidenceCount) {
        AgentDocumentCoverage target = new AgentDocumentCoverage();
        if (source != null) {
            target.setRequestedDocumentCount(source.getRequestedDocumentCount());
            target.setCoveredDocumentCount(source.getCoveredDocumentCount());
            target.setTruncated(source.isTruncated());
        }
        target.setEvidenceCount(evidenceCount);
        return target;
    }

    private boolean isAllowedDocumentEvidence(String domain, ExecutionScope scope) {
        return !maskingSupport.allowedFields(domain, scope).isEmpty();
    }

    private String truncate(String value) {
        if (value == null) {
            return null;
        }
        int limit = properties.getDocument().getMaxSnippetChars();
        return value.length() <= limit ? value : value.substring(0, limit);
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
