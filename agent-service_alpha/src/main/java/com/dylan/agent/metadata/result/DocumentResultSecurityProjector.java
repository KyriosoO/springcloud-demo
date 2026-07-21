package com.dylan.agent.metadata.result;

import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.*;
import com.dylan.agent.capability.document.acl.DocumentCurrentnessOutcome;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.generation.DocumentCitationVerifier;
import com.dylan.agent.capability.document.security.DocumentSafeSourceUri;
import com.dylan.agent.capability.document.security.DocumentFinalCurrentnessDecision;
import com.dylan.agent.capability.document.security.DocumentFinalCurrentnessDecisionVerifier;
import com.dylan.agent.capability.document.security.DocumentResultCandidateSetCanonicalizer;
import com.dylan.agent.capability.document.security.DocumentSecurityReasonCode;
import com.dylan.agent.kernel.resource.EffectiveCapabilityResourceLimits;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.time.Clock;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;

/** Document public contract 的纯本地 Result Security projector。 */
public final class DocumentResultSecurityProjector implements ResultSecurityProjector<DocumentAgentResultPayload> {
    private final ResultValueMaskingSupport masking;
    private final ObjectMapper objectMapper;
    private final DocumentFinalCurrentnessDecisionVerifier currentnessVerifier;
    private final DocumentResultCandidateSetCanonicalizer candidateSetCanonicalizer =
            new DocumentResultCandidateSetCanonicalizer();
    private final DocumentCitationVerifier citationVerifier = new DocumentCitationVerifier();

    public DocumentResultSecurityProjector(
            ResultValueMaskingSupport masking,
            ObjectMapper objectMapper,
            Clock clock) {
        this.masking = Objects.requireNonNull(masking, "masking must not be null");
        this.objectMapper = Objects.requireNonNull(objectMapper, "objectMapper must not be null");
        this.currentnessVerifier = new DocumentFinalCurrentnessDecisionVerifier(
                Objects.requireNonNull(clock, "clock must not be null"));
    }
    @Override public ContractRef supports() { return AgentExecutionContracts.DOCUMENT_RESULT; }
    @Override public Class<DocumentAgentResultPayload> payloadType() { return DocumentAgentResultPayload.class; }

    @Override
    public FilteredResult<DocumentAgentResultPayload> filter(DocumentAgentResultPayload candidate, ExecutionScope scope, EffectiveCapabilityResourceLimits effective) {
        Objects.requireNonNull(candidate, "candidate must not be null"); Objects.requireNonNull(scope, "scope must not be null");
        DocumentResourceLimit limits = effective.require(AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, DocumentResourceLimit.class);
        AgentDocumentParameters parameters = Objects.requireNonNull(candidate.getDocumentParameters(), "document parameters required");
        AgentDocumentResult result = Objects.requireNonNull(candidate.getDocumentResult(), "document result required");
        if (parameters.getDomain()==null || parameters.getDomain().isBlank() || parameters.getMaterialType()==null || parameters.getMaterialType().isBlank()) throw new IllegalStateException("document public corpus binding missing");
        if (parameters.getQueryText()!=null && parameters.getQueryText().codePointCount(0, parameters.getQueryText().length()) > limits.input().maxQueryChars()) throw new IllegalStateException("document query exceeds limit");
        List<AgentDocumentHit> hits = result.getHits()==null?List.of():List.copyOf(result.getHits());
        List<AgentDocumentCitation> citations = result.getCitations()==null?List.of():List.copyOf(result.getCitations());
        if(hits.size()>limits.retrieval().maxReturnedDocuments()||citations.size()>limits.output().maxCitationCount()||citations.size()>limits.output().maxEvidenceCount()) throw new IllegalStateException("document evidence count exceeds limit");
        Set<String> ids = validateCitations(citations, limits);
        verifyCurrentness(candidate, hits, citations, scope, effective);
        List<String> bullets=result.getSummaryBullets()==null?List.of():result.getSummaryBullets();
        validateGeneratedText(parameters.getOperation(), result, bullets, citations, ids, limits);
        validateCoverage(parameters.getOperation(), result.getCoverage(), citations);
        for(AgentDocumentHit hit:hits){ if(hit.getSnippet()!=null && hit.getSnippet().codePointCount(0,hit.getSnippet().length())>limits.output().maxSnippetChars()) throw new IllegalStateException("document snippet exceeds limit"); if(hit.getCitationIds()!=null&&!ids.containsAll(hit.getCitationIds())) throw new IllegalStateException("document hit citation binding invalid"); }
        DocumentAgentResultPayload filtered = project(candidate, parameters.getDomain(), scope, hits, citations, bullets);
        List<AgentDocumentCitation> filteredCitations = filtered.getDocumentResult().getCitations();
        validateGeneratedText(
                filtered.getDocumentParameters().getOperation(), filtered.getDocumentResult(),
                filtered.getDocumentResult().getSummaryBullets(), filteredCitations,
                filteredCitations.stream().map(AgentDocumentCitation::getCitationId).collect(java.util.stream.Collectors.toUnmodifiableSet()),
                limits);
        try { if(objectMapper.writeValueAsBytes(filtered).length>limits.output().maxResultBytes()) throw new IllegalStateException("document result bytes exceed limit"); }
        catch(java.io.IOException ex){throw new IllegalStateException("document result serialization failed",ex);}
        return new FilteredResult<>(filtered, "文档结果已通过安全校验。", "文档结果已按权限、引用和资源上限投影。");
    }

    private DocumentAgentResultPayload project(
            DocumentAgentResultPayload candidate,
            String domain,
            ExecutionScope scope,
            List<AgentDocumentHit> hits,
            List<AgentDocumentCitation> citations,
            List<String> bullets) {
        AgentDocumentParameters sourceParameters = candidate.getDocumentParameters();
        AgentDocumentParameters targetParameters = new AgentDocumentParameters();
        targetParameters.setDomain(sourceParameters.getDomain());
        targetParameters.setMaterialType(sourceParameters.getMaterialType());
        targetParameters.setOperation(sourceParameters.getOperation());
        targetParameters.setQueryText(sourceParameters.getQueryText());
        targetParameters.setFilters(sourceParameters.getFilters() == null ? null : sourceParameters.getFilters().stream()
                .map(filter -> masking.filterAndMaskFilter(domain, filter, scope))
                .filter(Objects::nonNull)
                .toList());
        targetParameters.setSorts(filterSorts(domain, sourceParameters.getSorts(), scope));
        targetParameters.setTopK(sourceParameters.getTopK());
        targetParameters.setSummaryScope(sourceParameters.getSummaryScope());

        AgentDocumentResult sourceResult = candidate.getDocumentResult();
        AgentDocumentResult targetResult = new AgentDocumentResult();
        targetResult.setAnswerText(sourceResult.getAnswerText());
        targetResult.setSummaryText(sourceResult.getSummaryText());
        targetResult.setSummaryBullets(List.copyOf(bullets));
        targetResult.setHits(hits.stream().map(hit -> projectHit(domain, hit, scope)).toList());
        targetResult.setCitations(citations.stream().map(citation -> projectCitation(domain, citation, scope)).toList());
        targetResult.setPartial(sourceResult.isPartial());
        targetResult.setCoverage(copyCoverage(sourceResult.getCoverage()));
        targetResult.setGenerationStatus(sourceResult.getGenerationStatus());
        targetResult.setGroundingStatus(sourceResult.getGroundingStatus());
        targetResult.setCitationVerification(copyVerification(sourceResult.getCitationVerification()));
        return new DocumentAgentResultPayload(targetParameters, targetResult);
    }

    private List<AgentQuerySortParameter> filterSorts(
            String domain,
            List<AgentQuerySortParameter> sorts,
            ExecutionScope scope) {
        if (sorts == null) return null;
        Set<String> allowedFields = masking.allowedFields(domain, scope);
        return sorts.stream()
                .filter(sort -> sort != null && sort.getField() != null && allowedFields.contains(sort.getField()))
                .map(sort -> {
                    AgentQuerySortParameter target = new AgentQuerySortParameter();
                    target.setField(sort.getField());
                    target.setDirection(sort.getDirection());
                    return target;
                })
                .toList();
    }

    private AgentDocumentHit projectHit(String domain, AgentDocumentHit source, ExecutionScope scope) {
        AgentDocumentHit target = new AgentDocumentHit();
        target.setDocumentId(source.getDocumentId());
        target.setTitle(projectString(domain, "title", source.getTitle(), scope));
        target.setSourceType(projectString(domain, "sourceType", source.getSourceType(), scope));
        target.setSnippet(projectString(domain, "snippet", source.getSnippet(), scope));
        target.setScore(source.getScore());
        target.setCitationIds(source.getCitationIds() == null ? null : List.copyOf(source.getCitationIds()));
        return target;
    }

    private AgentDocumentCitation projectCitation(
            String domain,
            AgentDocumentCitation source,
            ExecutionScope scope) {
        AgentDocumentCitation target = new AgentDocumentCitation();
        target.setCitationId(source.getCitationId());
        target.setDocumentId(source.getDocumentId());
        target.setTitle(projectString(domain, "title", source.getTitle(), scope));
        target.setSection(projectString(domain, "section", source.getSection(), scope));
        target.setPage(projectInteger(domain, "page", source.getPage(), scope));
        target.setSourceUri(DocumentSafeSourceUri.sanitize(
                projectString(domain, "sourceUri", source.getSourceUri(), scope)));
        target.setSnippet(projectString(domain, "snippet", source.getSnippet(), scope));
        target.setChunkIndex(source.getChunkIndex());
        target.setCharStart(source.getCharStart());
        target.setCharEnd(source.getCharEnd());
        return target;
    }

    private String projectString(String domain, String field, String value, ExecutionScope scope) {
        if (!masking.allowedFields(domain, scope).contains(field)) return null;
        return masking.maskStringValue(domain, field, value, scope);
    }

    private Integer projectInteger(String domain, String field, Integer value, ExecutionScope scope) {
        if (!masking.allowedFields(domain, scope).contains(field)) return null;
        Object masked = masking.maskValue(domain, field, value, scope);
        if (masked == null || masked instanceof Integer) return (Integer) masked;
        throw new IllegalStateException("document numeric field mask type mismatch");
    }

    private void verifyCurrentness(
            DocumentAgentResultPayload candidate,
            List<AgentDocumentHit> hits,
            List<AgentDocumentCitation> citations,
            ExecutionScope scope,
            EffectiveCapabilityResourceLimits effective) {
        DocumentResultSecurityEvidence evidence = Objects.requireNonNull(
                candidate.getInternalSecurityEvidence(), "document final currentness evidence required");
        if (evidence.candidates().size() != hits.size() || citations.size() != hits.size()) {
            throw new IllegalStateException("document result candidate binding count mismatch");
        }
        for (int index = 0; index < hits.size(); index++) {
            String publicDocumentId = hits.get(index).getDocumentId();
            String securedDocumentId = evidence.candidates().get(index).documentId();
            AgentDocumentCitation citation = citations.get(index);
            if (!Objects.equals(publicDocumentId, securedDocumentId)
                    || !Objects.equals(citation.getDocumentId(), securedDocumentId)
                    || !Objects.equals(citation.getChunkIndex(), evidence.candidates().get(index).chunkIndex())
                    || !List.of(citation.getCitationId()).equals(hits.get(index).getCitationIds())) {
                throw new IllegalStateException("document result candidate ordering mismatch");
            }
        }
        List<String> citationIds = citations.stream().map(AgentDocumentCitation::getCitationId).toList();
        if (!citationIds.equals(evidence.evidenceRefs())) {
            throw new IllegalStateException("document result evidence reference mismatch");
        }
        if (!effective.reference().canonicalDigest().equals(evidence.resourceLimitDigest())) {
            throw new IllegalStateException("document result resource limit binding mismatch");
        }
        String candidateSetDigest = candidateSetCanonicalizer.digest(
                evidence.candidates(), evidence.evidenceRefs(), AgentExecutionContracts.DOCUMENT_RESULT);
        if (!candidateSetDigest.equals(evidence.candidateSetDigest())) {
            throw new IllegalStateException("document result candidate set digest mismatch");
        }
        DocumentFinalCurrentnessDecision decision = new DocumentFinalCurrentnessDecision(
                DocumentCurrentnessOutcome.valueOf(evidence.outcome()),
                evidence.invocationId(), evidence.operationId(), evidence.permissionVersion(),
                evidence.candidateSetDigest(), evidence.authorizationBindingDigest(), effective.reference(),
                evidence.aclDecisionVersion(), evidence.emergencyViewVersion(), evidence.checkedAt(),
                evidence.validUntil(), evidence.decisionDigest(),
                DocumentSecurityReasonCode.valueOf(evidence.reasonCode()));
        currentnessVerifier.verify(decision, candidateSetDigest, scope);
    }

    private static Set<String> validateCitations(List<AgentDocumentCitation> citations, DocumentResourceLimit limits){
        Set<String> ids=new HashSet<>();
        for(int i=0;i<citations.size();i++){AgentDocumentCitation c=Objects.requireNonNull(citations.get(i));String expected="C"+(i+1);if(!expected.equals(c.getCitationId())||!ids.add(expected))throw new IllegalStateException("citation sequence invalid");if(c.getSnippet()!=null&&c.getSnippet().codePointCount(0,c.getSnippet().length())>limits.output().maxSnippetChars())throw new IllegalStateException("citation snippet exceeds limit");if(c.getDocumentId()==null||c.getDocumentId().isBlank()||c.getChunkIndex()==null||c.getChunkIndex()<0||c.getCharStart()!=null&&c.getCharStart()<0||c.getCharEnd()!=null&&(c.getCharEnd()<0||c.getCharStart()!=null&&c.getCharEnd()<c.getCharStart()))throw new IllegalStateException("citation identity or offset invalid");}
        return Set.copyOf(ids);
    }

    private static void validateCoverage(
            String operation,
            AgentDocumentCoverage coverage,
            List<AgentDocumentCitation> citations) {
        if (coverage == null) throw new IllegalStateException("document coverage required");
        int coveredDocuments = (int) citations.stream()
                .map(AgentDocumentCitation::getDocumentId).distinct().count();
        if (coverage.getRequestedDocumentCount() < 0
                || !coverage.isRequestedCountKnown() && coverage.getRequestedDocumentCount() != 0
                || coverage.isRequestedCountKnown() && !DocumentPlanOperation.SUMMARIZE.name().equals(operation)
                || coverage.getCoveredDocumentCount() != coveredDocuments
                || coverage.getEvidenceCount() != citations.size()
                || coverage.isRequestedCountKnown()
                && coverage.getCoveredDocumentCount() > coverage.getRequestedDocumentCount()) {
            throw new IllegalStateException("document coverage binding invalid");
        }
    }

    private static AgentDocumentCoverage copyCoverage(AgentDocumentCoverage source) {
        if (source == null) return null;
        AgentDocumentCoverage target = new AgentDocumentCoverage();
        target.setRequestedDocumentCount(source.getRequestedDocumentCount());
        target.setRequestedCountKnown(source.isRequestedCountKnown());
        target.setCoveredDocumentCount(source.getCoveredDocumentCount());
        target.setEvidenceCount(source.getEvidenceCount());
        target.setTruncated(source.isTruncated());
        return target;
    }

    private static AgentDocumentCitationVerification copyVerification(
            AgentDocumentCitationVerification source) {
        if (source == null) return null;
        AgentDocumentCitationVerification target = new AgentDocumentCitationVerification();
        target.setStatus(source.getStatus());
        target.setBoundUnitCount(source.getBoundUnitCount());
        target.setVisibleCitationCount(source.getVisibleCitationCount());
        return target;
    }
    private void validateGeneratedText(
            String operationValue,
            AgentDocumentResult result,
            List<String> bullets,
            List<AgentDocumentCitation> citations,
            Set<String> ids,
            DocumentResourceLimit limits) {
        if (codePoints(result.getAnswerText()) > limits.output().maxGeneratedChars()) {
            throw new IllegalStateException("document text exceeds limit");
        }
        int summaryChars = codePoints(result.getSummaryText());
        for (String bullet : bullets) summaryChars = Math.addExact(summaryChars, codePoints(bullet));
        if (summaryChars > limits.output().maxSummaryChars()
                || bullets.size() > limits.output().maxSummaryBullets()) {
            throw new IllegalStateException("document summary exceeds limit");
        }
        boolean hasVisibleText = codePoints(result.getAnswerText()) > 0
                || codePoints(result.getSummaryText()) > 0
                || bullets.stream().anyMatch(value -> codePoints(value) > 0);
        if (!hasVisibleText) return;
        DocumentPlanOperation operation;
        try { operation = DocumentPlanOperation.valueOf(operationValue); }
        catch (RuntimeException ex) { throw new IllegalStateException("document operation binding invalid", ex); }
        List<String> citationIds = citations.stream().map(AgentDocumentCitation::getCitationId).toList();
        var verification = citationVerifier.verifyVisible(
                operation, result.getAnswerText(), result.getSummaryText(), bullets, citationIds, ids);
        if (!verification.verified()) {
            throw new IllegalStateException("unknown citation marker or invalid citation position: "
                    + verification.reasonCode());
        }
    }
    private static int codePoints(String value) {
        return value == null ? 0 : value.codePointCount(0, value.length());
    }
}
