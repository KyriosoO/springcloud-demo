package com.dylan.agent.capability.document.evidence;

import com.dylan.agent.api.response.AgentDocumentCitation;
import com.dylan.agent.api.response.AgentDocumentCoverage;
import com.dylan.agent.api.response.AgentDocumentHit;
import com.dylan.agent.api.response.AgentDocumentResult;
import com.dylan.agent.api.response.DocumentAgentResultPayload;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentResultSizeGuardTest {

    private final ObjectMapper mapper = new ObjectMapper();
    private final DocumentResultSizeGuard guard = new DocumentResultSizeGuard(mapper);

    @Test
    void removesHitAndCitationFromTailAsOneStablePair() throws Exception {
        DocumentAgentResultPayload payload = payload(2);
        AgentDocumentResult onePair = result(1);
        payload.setDocumentResult(onePair);
        long onePairBytes = mapper.writeValueAsBytes(payload).length;
        payload.setDocumentResult(result(2));

        int retained = guard.reduceEvidenceOnly(payload, onePairBytes);

        assertThat(retained).isOne();
        assertThat(payload.getDocumentResult().getHits()).extracting(AgentDocumentHit::getDocumentId)
                .containsExactly("doc-1");
        assertThat(payload.getDocumentResult().getCitations()).extracting(AgentDocumentCitation::getCitationId)
                .containsExactly("C1");
        assertThat(payload.getDocumentResult().getCoverage().getEvidenceCount()).isOne();
        assertThat(payload.getDocumentResult().getCoverage().isTruncated()).isTrue();
        assertThat(guard.fits(payload, onePairBytes)).isTrue();
    }

    @Test
    void refusesToDropEvidenceWhileGeneratedTextIsVisible() {
        DocumentAgentResultPayload payload = payload(1);
        payload.getDocumentResult().setAnswerText("答案 [C1]");

        assertThatThrownBy(() -> guard.reduceEvidenceOnly(payload, 1L))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("generated document result cannot remove bound evidence");
    }

    private static DocumentAgentResultPayload payload(int count) {
        return new DocumentAgentResultPayload(null, result(count));
    }

    private static AgentDocumentResult result(int count) {
        AgentDocumentResult result = new AgentDocumentResult();
        result.setHits(java.util.stream.IntStream.rangeClosed(1, count).mapToObj(i -> {
            AgentDocumentHit hit = new AgentDocumentHit();
            hit.setDocumentId("doc-" + i);
            hit.setTitle("文档" + i);
            hit.setSnippet("证据".repeat(20));
            hit.setCitationIds(List.of("C" + i));
            return hit;
        }).toList());
        result.setCitations(java.util.stream.IntStream.rangeClosed(1, count).mapToObj(i -> {
            AgentDocumentCitation citation = new AgentDocumentCitation();
            citation.setCitationId("C" + i);
            citation.setDocumentId("doc-" + i);
            citation.setTitle("文档" + i);
            citation.setSnippet("证据".repeat(20));
            return citation;
        }).toList());
        AgentDocumentCoverage coverage = new AgentDocumentCoverage();
        coverage.setRequestedDocumentCount(0);
        coverage.setRequestedCountKnown(false);
        coverage.setCoveredDocumentCount(count);
        coverage.setEvidenceCount(count);
        result.setCoverage(coverage);
        return result;
    }
}
