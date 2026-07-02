package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Base64;
import java.util.Map;

import org.junit.jupiter.api.Test;

import com.dylan.agent.metadata.crypto.internal.EnvironmentPayloadKeyProvider;

class PayloadKeyProviderTest {
    @Test
    void resolvesBase64EncodedAes256KeyByUppercaseKeyId() {
        byte[] key = new byte[32];
        String encoded = Base64.getEncoder().encodeToString(key);
        EnvironmentPayloadKeyProvider provider =
                new EnvironmentPayloadKeyProvider(name -> Map.of("AGENT_PAYLOAD_KEY_ACTIVE", encoded).get(name));

        assertThat(provider.requireKey("ACTIVE").getEncoded()).hasSize(32);
    }
}
