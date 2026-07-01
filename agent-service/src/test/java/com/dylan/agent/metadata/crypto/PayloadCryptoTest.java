package com.dylan.agent.metadata.crypto;

import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.metadata.config.AgentSecuritySettings;
import com.dylan.agent.metadata.config.AgentSecuritySettingsRegistry;
import com.dylan.agent.metadata.crypto.internal.AeadProtectedPayloadCodec;
import com.dylan.agent.metadata.crypto.internal.EnvironmentPayloadKeyProvider;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.crypto.model.PayloadProtectionContext;
import com.dylan.agent.metadata.crypto.model.PayloadPurpose;
import org.junit.jupiter.api.Test;

import java.security.SecureRandom;
import java.time.Duration;
import java.util.Base64;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class PayloadCryptoTest {

    @Test
    void jsonCodecOnlyAcceptsDeclaredPayloadRoots() {
        PayloadJsonCodec codec = new PayloadJsonCodec();
        QueryCapabilityContextPayload payload =
                new QueryCapabilityContextPayload(null, java.util.List.of("name"), 1, 20);

        byte[] bytes = codec.serialize(payload, QueryCapabilityContextPayload.class);
        QueryCapabilityContextPayload decoded =
                codec.deserialize(bytes, QueryCapabilityContextPayload.class);

        assertThat(decoded.selectFields()).containsExactly("name");
        assertThatThrownBy(() -> codec.serialize("raw", String.class))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("payload root");
    }

    @Test
    void aeadCodecRoundTripsAndFailsForWrongAad() {
        byte[] rawKey = new byte[32];
        new SecureRandom(new byte[] {1, 2, 3, 4}).nextBytes(rawKey);
        String encoded = Base64.getEncoder().encodeToString(rawKey);
        EnvironmentPayloadKeyProvider keys =
                new EnvironmentPayloadKeyProvider(name -> Map.of("AGENT_PAYLOAD_KEY_ACTIVE", encoded).get(name));
        AgentSecuritySettingsRegistry settings = new AgentSecuritySettingsRegistry(
                new AgentSecuritySettings(Duration.ofHours(1), Duration.ofMinutes(5), 10, "ACTIVE"));
        AeadProtectedPayloadCodec codec = new AeadProtectedPayloadCodec(settings, keys);

        PayloadProtectionContext context = context("ctx-1");
        var protectedPayload = codec.encrypt("secret".getBytes(java.nio.charset.StandardCharsets.UTF_8), context);

        assertThat(protectedPayload.keyId()).isEqualTo("ACTIVE");
        assertThat(protectedPayload.nonce()).hasSize(12);
        assertThat(new String(codec.decrypt(protectedPayload, context),
                java.nio.charset.StandardCharsets.UTF_8)).isEqualTo("secret");

        assertThatThrownBy(() -> codec.decrypt(protectedPayload, context("ctx-2")))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("cryptographic operation failed");
    }

    private PayloadProtectionContext context(String ownerId) {
        return new PayloadProtectionContext(
                PayloadPurpose.CONTEXT_PAYLOAD,
                "conversation",
                ownerId,
                Optional.of(RuntimeContextType.QUERY),
                new ContractRef("query_context", "v1"),
                "inv-1");
    }
}
