package com.dylan.agent.metadata.config;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.assertThat;

import java.util.concurrent.atomic.AtomicBoolean;

import javax.crypto.spec.SecretKeySpec;

import org.junit.jupiter.api.Test;

import com.dylan.common.security.SecretMaterialException;

class AgentMetadataPropertiesValidatorTest {

    @Test
    void acceptsAes256ActivePayloadKey() {
        assertThatCode(() -> AgentMetadataPropertiesValidator.validate(
                "ACTIVE",
                keyId -> new SecretKeySpec(new byte[32], "AES")))
                .doesNotThrowAnyException();
    }

    @Test
    void rejectsNonAes256ActivePayloadKey() {
        assertThatThrownBy(() -> AgentMetadataPropertiesValidator.validate(
                "ACTIVE",
                keyId -> new SecretKeySpec(new byte[16], "AES")))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("AES-256");
    }

    @Test
    void rejectsInvalidActivePayloadKeyIdBeforeSecretLookup() {
        AtomicBoolean called = new AtomicBoolean(false);

        assertThatThrownBy(() -> AgentMetadataPropertiesValidator.validate("invalid-key", keyId -> {
                    called.set(true);
                    return new SecretKeySpec(new byte[32], "AES");
                }))
                .isInstanceOf(SecretMaterialException.class)
                .hasMessageContaining("Invalid key id");
        assertThat(called).isFalse();
    }

}
