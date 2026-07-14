package com.dylan.common.security;

import org.junit.jupiter.api.Test;

import java.security.KeyPairGenerator;
import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

class Ed25519IntegritySupportTest {
    @Test
    void signsAndVerifiesExactCanonicalBytes() throws Exception {
        var keyPair = KeyPairGenerator.getInstance("Ed25519").generateKeyPair();
        byte[] canonical = "EGE-1".getBytes(StandardCharsets.UTF_8);

        String signature = Ed25519IntegritySupport.signBase64Url(canonical, keyPair.getPrivate());

        assertThat(Ed25519IntegritySupport.verifyBase64Url(canonical, signature, keyPair.getPublic())).isTrue();
        assertThat(Ed25519IntegritySupport.verifyBase64Url(
                "EGE-2".getBytes(StandardCharsets.UTF_8), signature, keyPair.getPublic())).isFalse();
    }
}
