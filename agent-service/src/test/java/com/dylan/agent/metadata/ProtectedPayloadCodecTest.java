package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.util.Base64;
import java.util.Map;

import org.junit.jupiter.api.Test;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.metadata.config.AgentSecuritySettings;
import com.dylan.agent.metadata.config.AgentSecuritySettingsRegistry;
import com.dylan.agent.metadata.crypto.internal.AeadProtectedPayloadCodec;
import com.dylan.agent.metadata.crypto.internal.EnvironmentPayloadKeyProvider;
import com.dylan.agent.metadata.crypto.model.PayloadProtectionContext;
import com.dylan.agent.metadata.crypto.model.PayloadPurpose;

class ProtectedPayloadCodecTest {
    @Test
    void encryptsWithUniqueNonceAndRoundTrips() {
        String encoded = Base64.getEncoder().encodeToString(new byte[32]);
        AeadProtectedPayloadCodec codec = new AeadProtectedPayloadCodec(
                new AgentSecuritySettingsRegistry(new AgentSecuritySettings(Duration.ofHours(1), Duration.ZERO, 10, "ACTIVE")),
                new EnvironmentPayloadKeyProvider(name -> Map.of("AGENT_PAYLOAD_KEY_ACTIVE", encoded).get(name)));
        PayloadProtectionContext context = new PayloadProtectionContext(
                PayloadPurpose.CONTEXT_PAYLOAD,
                "ctx-1",
                AgentExecutionContracts.QUERY_CONTEXT,
                "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef");

        var encrypted = codec.encrypt("x".getBytes(java.nio.charset.StandardCharsets.UTF_8), context);

        assertThat(new String(codec.decrypt(encrypted, context), java.nio.charset.StandardCharsets.UTF_8)).isEqualTo("x");
        assertThat(encrypted.nonce()).hasSize(12);
    }
}
