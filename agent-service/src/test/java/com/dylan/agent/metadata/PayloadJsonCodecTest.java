package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;

import org.junit.jupiter.api.Test;

import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.enums.AgentResultKind;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;

class PayloadJsonCodecTest {
    @Test
    void roundTripsOnlyDeclaredPayloadType() {
        PayloadJsonCodec codec = new PayloadJsonCodec();
        var payload = new QueryCapabilityContextPayload(List.of(), List.of("name"), 1, 10);

        var decoded = codec.deserialize(codec.serialize(payload, QueryCapabilityContextPayload.class),
                QueryCapabilityContextPayload.class);

        assertThat(decoded.selectFields()).containsExactly("name");
    }

    @Test
    void roundTripsResultPayloadWithReadOnlyDiscriminator() {
        PayloadJsonCodec codec = new PayloadJsonCodec();
        var payload = new QueryAgentResultPayload();

        byte[] bytes = codec.serialize(payload, QueryAgentResultPayload.class);
        var decoded = codec.deserialize(bytes, QueryAgentResultPayload.class);

        assertThat(new String(bytes, java.nio.charset.StandardCharsets.UTF_8))
                .contains("\"resultKind\":\"QUERY\"");
        assertThat(decoded.getResultKind()).isEqualTo(AgentResultKind.QUERY);
    }

    @Test
    void rejectsUnknownResultPayloadField() {
        PayloadJsonCodec codec = new PayloadJsonCodec();
        byte[] bytes = "{\"unexpected\":true}".getBytes(java.nio.charset.StandardCharsets.UTF_8);

        assertThatThrownBy(() -> codec.deserialize(bytes, QueryAgentResultPayload.class))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("payload deserialization failed");
    }
}
