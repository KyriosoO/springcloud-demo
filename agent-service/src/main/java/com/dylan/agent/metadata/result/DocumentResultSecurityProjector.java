package com.dylan.agent.metadata.result;

import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.*;
import com.dylan.agent.capability.document.acl.DocumentCurrentnessOutcome;
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
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Document public contract 的纯本地 Result Security projector。 */
public final class DocumentResultSecurityProjector implements ResultSecurityProjector<DocumentAgentResultPayload> {
    private static final Pattern CITATION = Pattern.compile("\\[(C[1-9][0-9]*)]");
    private final ResultValueMaskingSupport masking;
    private final ObjectMapper objectMapper;
    private final DocumentFinalCurrentnessDecisionVerifier currentnessVerifier;
    private final DocumentResultCandidateSetCanonicalizer candidateSetCanonicalizer =
            new DocumentResultCandidateSetCanonicalizer();

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
        parameters.setFilters(parameters.getFilters()==null?List.of():parameters.getFilters().stream().map(f->masking.filterAndMaskFilter(parameters.getDomain(),f,scope)).filter(Objects::nonNull).toList());
        List<AgentDocumentHit> hits = result.getHits()==null?List.of():List.copyOf(result.getHits());
        List<AgentDocumentCitation> citations = result.getCitations()==null?List.of():List.copyOf(result.getCitations());
        if(hits.size()>limits.retrieval().maxReturnedDocuments()||citations.size()>limits.output().maxCitationCount()||citations.size()>limits.output().maxEvidenceCount()) throw new IllegalStateException("document evidence count exceeds limit");
        Set<String> ids = validateCitations(citations, limits);
        verifyCurrentness(candidate, hits, citations, scope, effective);
        validateText(result.getAnswerText(), ids, limits.output().maxGeneratedChars());
        validateText(result.getSummaryText(), ids, limits.output().maxSummaryChars());
        List<String> bullets=result.getSummaryBullets()==null?List.of():result.getSummaryBullets();
        if(bullets.size()>limits.output().maxSummaryBullets()) throw new IllegalStateException("document summary bullet count exceeds limit");
        bullets.forEach(value->validateText(value,ids,limits.output().maxSummaryChars()));
        for(AgentDocumentHit hit:hits){ if(hit.getSnippet()!=null && hit.getSnippet().codePointCount(0,hit.getSnippet().length())>limits.output().maxSnippetChars()) throw new IllegalStateException("document snippet exceeds limit"); if(hit.getCitationIds()!=null&&!ids.containsAll(hit.getCitationIds())) throw new IllegalStateException("document hit citation binding invalid"); }
        try { if(objectMapper.writeValueAsBytes(candidate).length>limits.output().maxResultBytes()) throw new IllegalStateException("document result bytes exceed limit"); }
        catch(java.io.IOException ex){throw new IllegalStateException("document result serialization failed",ex);}
        return new FilteredResult<>(candidate, "文档结果已通过安全校验。", "文档结果已按权限、引用和资源上限投影。");
    }

    private void verifyCurrentness(
            DocumentAgentResultPayload candidate,
            List<AgentDocumentHit> hits,
            List<AgentDocumentCitation> citations,
            ExecutionScope scope,
            EffectiveCapabilityResourceLimits effective) {
        DocumentResultSecurityEvidence evidence = Objects.requireNonNull(
                candidate.getInternalSecurityEvidence(), "document final currentness evidence required");
        if (evidence.candidates().size() != hits.size()) {
            throw new IllegalStateException("document result candidate binding count mismatch");
        }
        for (int index = 0; index < hits.size(); index++) {
            String publicDocumentId = hits.get(index).getDocumentId();
            String securedDocumentId = evidence.candidates().get(index).documentId();
            if (!Objects.equals(publicDocumentId, securedDocumentId)) {
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
        for(int i=0;i<citations.size();i++){AgentDocumentCitation c=Objects.requireNonNull(citations.get(i));String expected="C"+(i+1);if(!expected.equals(c.getCitationId())||!ids.add(expected))throw new IllegalStateException("citation sequence invalid");if(c.getSnippet()!=null&&c.getSnippet().codePointCount(0,c.getSnippet().length())>limits.output().maxSnippetChars())throw new IllegalStateException("citation snippet exceeds limit");}
        return Set.copyOf(ids);
    }
    private static void validateText(String text,Set<String> ids,int maxChars){if(text==null||text.isBlank())return;if(text.codePointCount(0,text.length())>maxChars)throw new IllegalStateException("document text exceeds limit");for(String unit:text.split("(?:\\R\\s*){2,}|\\R")){if(unit.isBlank())continue;Matcher m=CITATION.matcher(unit);boolean found=false;while(m.find()){found=true;if(!ids.contains(m.group(1)))throw new IllegalStateException("unknown citation marker");}if(!found)throw new IllegalStateException("visible text unit is not citation bound");}}
}
