package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.Test;

import com.dylan.agent.api.context.QueryCapabilityContextPayload;
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
}
