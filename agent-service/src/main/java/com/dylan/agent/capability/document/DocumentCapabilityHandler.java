package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.adapter.api.document.AdapterDocumentResult;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.api.context.DocumentCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.response.AgentDocumentCitation;
import com.dylan.agent.api.response.AgentDocumentCoverage;
import com.dylan.agent.api.response.AgentDocumentHit;
import com.dylan.agent.api.response.AgentDocumentParameters;
import com.dylan.agent.api.response.AgentDocumentResult;
import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.api.response.AgentQuerySortParameter;
import com.dylan.agent.api.response.DocumentAgentResultPayload;
import com.dylan.agent.kernel.core.ExecutionContext;
import com.dylan.agent.kernel.handler.CapabilityHandler;
import com.dylan.agent.kernel.handler.HandlerResult;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;

import java.util.List;
import java.util.Objects;

public class DocumentCapabilityHandler
        implements CapabilityHandler<ValidatedDocumentPlan, DocumentAgentResultPayload> {

    @Override
    public HandlerResult<DocumentAgentResultPayload> execute(
            ValidatedDocumentPlan plan,
            ExecutionContext context) {
        DocumentRetrievableAdapter adapter = context.requireAdapter(DocumentRetrievableAdapter.class);
        AdapterDocumentResult adapterResult = adapter.retrieve(plan.request());
        DocumentAgentResultPayload payload = new DocumentAgentResultPayload(
                toParameters(plan),
                toResult(plan, adapterResult));
        return HandlerResult.of(payload, List.of(toContextWrite(plan, adapterResult)));
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
        AgentDocumentCoverage coverage = new AgentDocumentCoverage();
        coverage.setRequestedDocumentCount(
                safeResult.getRequestedDocumentCount() > 0 ? safeResult.getRequestedDocumentCount() : plan.request().getTopK());
        coverage.setCoveredDocumentCount(safeResult.getCoveredDocumentCount());
        coverage.setEvidenceCount(citations.size());
        coverage.setTruncated(citations.size() > plan.request().getTopK());
        result.setCoverage(coverage);
        return result;
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
