package com.dylan.agent.api;

import com.dylan.agent.api.enums.AgentResponseType;
import com.dylan.agent.api.enums.AgentResultKind;
import com.dylan.agent.api.response.AgentChatResponse;
import com.dylan.agent.api.response.AggregateAgentResultPayload;
import com.dylan.agent.api.response.AgentQueryParameters;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.api.response.QueryPreviewResult;
import com.dylan.agent.api.response.QueryPreviewResultPayload;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AgentResultPayloadContractTest {

    @Test
    void responseTypeDoesNotExposeAggregateResultBranch() {
        assertThat(AgentResponseType.values())
                .containsExactly(AgentResponseType.RESULT, AgentResponseType.CLARIFY, AgentResponseType.ERROR);
    }

    @Test
    void payloadDiscriminatorsAreFixed() {
        assertThat(new QueryAgentResultPayload().getResultKind()).isEqualTo(AgentResultKind.QUERY);
        assertThat(new QueryPreviewResultPayload().getResultKind()).isEqualTo(AgentResultKind.QUERY_PREVIEW);
        assertThat(new AggregateAgentResultPayload().getResultKind()).isEqualTo(AgentResultKind.AGGREGATE);
    }

    @Test
    void queryPreviewPayloadSerializesWithDiscriminator() throws Exception {
        QueryPreviewResult preview = new QueryPreviewResult();
        preview.setColumns(List.of("name"));
        preview.setSampleRows(List.of(Map.of("name", "Alice")));
        preview.setTotalEstimate(1L);
        preview.setTotalExact(true);
        preview.setPreviewSize(1);

        AgentQueryParameters parameters = new AgentQueryParameters();
        parameters.setDomain("employee");
        parameters.setSelectFields(List.of("name"));
        parameters.setPage(1);
        parameters.setSize(1);

        String json = new ObjectMapper().writeValueAsString(
                new QueryPreviewResultPayload(parameters, preview));

        assertThat(json).contains("\"resultKind\":\"QUERY_PREVIEW\"");
        assertThat(json).contains("\"previewResult\"");
        assertThat(json).contains("\"sampleRows\"");
    }

    @Test
    void queryPreviewPayloadRejectsUnknownFieldsWithStrictMapper() {
        ObjectMapper mapper = new ObjectMapper()
                .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, true);

        assertThatThrownBy(() -> mapper.readValue(
                "{\"unexpected\":true}",
                QueryPreviewResultPayload.class))
                .isInstanceOf(com.fasterxml.jackson.databind.exc.UnrecognizedPropertyException.class);
    }

    @Test
    void chatResponseHasSingleResultSlot() {
        assertThat(AgentChatResponse.class.getDeclaredFields())
                .extracting(java.lang.reflect.Field::getName)
                .contains("result")
                .doesNotContain("queryParameters", "queryResult", "previewResult", "aggregateResult");
    }
}
