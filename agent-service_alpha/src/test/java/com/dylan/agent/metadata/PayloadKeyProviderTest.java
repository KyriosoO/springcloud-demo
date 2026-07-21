package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Base64;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import org.junit.jupiter.api.Test;

import com.dylan.agent.metadata.crypto.internal.EnvironmentPayloadKeyProvider;
import com.dylan.agent.metadata.crypto.internal.SecretMaterialPayloadKeyProvider;
import com.dylan.common.security.CompositeSecretMaterialProvider;
import com.dylan.common.security.SecretKeyRef;
import com.dylan.common.security.SecretMaterial;
import com.dylan.common.security.SecretMaterialException;
import com.dylan.common.security.SecretMaterialProvider;
import com.dylan.common.security.SecretProperties;
import com.dylan.common.security.SecretSourceType;

class PayloadKeyProviderTest {
    @Test
    void resolvesBase64EncodedAes256KeyByUppercaseKeyId() {
        byte[] key = new byte[32];
        String encoded = Base64.getEncoder().encodeToString(key);
        EnvironmentPayloadKeyProvider provider =
                new EnvironmentPayloadKeyProvider(name -> Map.of("AGENT_PAYLOAD_KEY_ACTIVE", encoded).get(name));

        assertThat(provider.requireKey("ACTIVE").getEncoded()).hasSize(32);
    }

    @Test
    void resolvesAes256PayloadKeyFromSecretMaterialProvider() {
        byte[] key = new byte[32];
        String encoded = Base64.getEncoder().encodeToString(key);
        SecretProperties properties = new SecretProperties();
        properties.setAllowConfigValues(true);
        properties.setSourceOrder(java.util.List.of(SecretSourceType.CONFIG));
        properties.getAgentPayload().setActiveKeyId("ACTIVE");
        properties.getAgentPayload().setKeys(Map.of("ACTIVE", key(encoded)));
        SecretMaterialPayloadKeyProvider provider =
                new SecretMaterialPayloadKeyProvider(properties, new CompositeSecretMaterialProvider(properties));

        assertThat(provider.requireKey("ACTIVE").getEncoded()).hasSize(32);
    }

    @Test
    void cachesPayloadKeyByKeyId() {
        byte[] key = new byte[32];
        String encoded = Base64.getEncoder().encodeToString(key);
        SecretProperties properties = new SecretProperties();
        properties.getAgentPayload().setKeys(Map.of("ACTIVE", key(encoded)));
        CountingSecretMaterialProvider secretMaterialProvider = new CountingSecretMaterialProvider(
                new CompositeSecretMaterialProvider(properties));
        SecretMaterialPayloadKeyProvider provider =
                new SecretMaterialPayloadKeyProvider(properties, secretMaterialProvider);

        provider.requireKey("ACTIVE");
        provider.requireKey("ACTIVE");

        assertThat(secretMaterialProvider.count()).isEqualTo(1);
    }

    @Test
    void rejectsInvalidPayloadKeyIdBeforeSecretLookup() {
        SecretProperties properties = new SecretProperties();
        SecretMaterialPayloadKeyProvider provider =
                new SecretMaterialPayloadKeyProvider(properties, ref -> {
                    throw new AssertionError("secret lookup must not be called for invalid keyId");
                });

        assertThatThrownBy(() -> provider.requireKey("invalid-key-id"))
                .isInstanceOf(SecretMaterialException.class)
                .hasMessageContaining("Invalid key id");
    }

    private static SecretProperties.KeyProperties key(String value) {
        SecretProperties.KeyProperties key = new SecretProperties.KeyProperties();
        key.setValue(value);
        return key;
    }

    private static final class CountingSecretMaterialProvider implements SecretMaterialProvider {
        private final SecretMaterialProvider delegate;
        private final AtomicInteger count = new AtomicInteger();

        private CountingSecretMaterialProvider(SecretMaterialProvider delegate) {
            this.delegate = delegate;
        }

        @Override
        public SecretMaterial requireSecret(SecretKeyRef ref) {
            count.incrementAndGet();
            return delegate.requireSecret(ref);
        }

        int count() {
            return count.get();
        }
    }
}
