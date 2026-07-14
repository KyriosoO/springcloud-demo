package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Base64;
import java.util.Map;

import org.junit.jupiter.api.Test;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.metadata.crypto.internal.AeadProtectedPayloadCodec;
import com.dylan.agent.metadata.crypto.internal.EnvironmentPayloadKeyProvider;
import com.dylan.agent.metadata.crypto.internal.SecretMaterialPayloadKeyProvider;
import com.dylan.agent.metadata.crypto.model.PayloadProtectionContext;
import com.dylan.agent.metadata.crypto.model.PayloadPurpose;
import com.dylan.common.security.CompositeSecretMaterialProvider;
import com.dylan.common.security.SecretProperties;
import com.dylan.common.security.SecretSourceType;

class ProtectedPayloadCodecTest {
    @Test
    void encryptsWithUniqueNonceAndRoundTrips() {
        String encoded = Base64.getEncoder().encodeToString(new byte[32]);
        AeadProtectedPayloadCodec codec = new AeadProtectedPayloadCodec(
                "ACTIVE",
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

    @Test
    void encryptDecryptWithSecretMaterialProvider() {
        String encoded = Base64.getEncoder().encodeToString(new byte[32]);
        SecretProperties properties = new SecretProperties();
        properties.setAllowConfigValues(true);
        properties.setSourceOrder(java.util.List.of(SecretSourceType.CONFIG));
        properties.getAgentPayload().setKeys(Map.of("ACTIVE", key(encoded)));
        AeadProtectedPayloadCodec codec = new AeadProtectedPayloadCodec(
                "ACTIVE",
                new SecretMaterialPayloadKeyProvider(properties, new CompositeSecretMaterialProvider(properties)));
        PayloadProtectionContext context = new PayloadProtectionContext(
                PayloadPurpose.CONTEXT_PAYLOAD,
                "ctx-2",
                AgentExecutionContracts.QUERY_CONTEXT,
                "1123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef");

        var encrypted = codec.encrypt("y".getBytes(java.nio.charset.StandardCharsets.UTF_8), context);

        assertThat(new String(codec.decrypt(encrypted, context), java.nio.charset.StandardCharsets.UTF_8)).isEqualTo("y");
        assertThat(encrypted.keyId()).isEqualTo("ACTIVE");
    }

    private static SecretProperties.KeyProperties key(String value) {
        SecretProperties.KeyProperties key = new SecretProperties.KeyProperties();
        key.setValue(value);
        return key;
    }
}
