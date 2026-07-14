package com.dylan.agent.adapter.api.document.provider;

import org.junit.jupiter.api.Test;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentUntrustedRerankPayloadTest {
    @Test
    void requiresClosedReasonCode() {
        assertThatThrownBy(() -> new DocumentUntrustedRerankPayload.DocumentRerankScoreItem("candidate-1", 1.0, null))
                .isInstanceOf(NullPointerException.class)
                .hasMessage("reasonCode must not be null");
    }

    @Test
    void acceptsModelRelevanceReason() {
        new DocumentUntrustedRerankPayload(List.of(
                new DocumentUntrustedRerankPayload.DocumentRerankScoreItem(
                        "candidate-1", 0.25, DocumentRerankReasonCode.MODEL_RELEVANCE)));
    }

    @Test
    void rejectsUnknownWireReasonInsteadOfFallingBack() {
        ObjectMapper mapper=new ObjectMapper();
        assertThatThrownBy(()->mapper.readValue(
                "{\"scores\":[{\"candidateId\":\"candidate-1\",\"score\":0.25,\"reasonCode\":\"OTHER\"}]}",
                DocumentUntrustedRerankPayload.class))
                .isInstanceOf(com.fasterxml.jackson.databind.exc.InvalidFormatException.class);
    }
}
