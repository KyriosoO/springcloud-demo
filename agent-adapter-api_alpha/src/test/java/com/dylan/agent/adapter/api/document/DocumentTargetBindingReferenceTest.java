package com.dylan.agent.adapter.api.document;

import org.junit.jupiter.api.Test;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentTargetBindingReferenceTest {
    @Test
    void canonicalDigestUsesGovernanceItb1Contract() throws Exception {
        var binding = new DocumentTargetBindingReference(
                "v1", "a".repeat(64), "b".repeat(64), "c".repeat(64));
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        for (String value : List.of("ITB-1", binding.schemaVersion(), binding.contentDigest(),
                binding.manifestDigest(), binding.attestationDigest())) {
            byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
            digest.update(ByteBuffer.allocate(4).putInt(bytes.length).array());
            digest.update(bytes);
        }
        assertThat(binding.canonicalDigest()).isEqualTo(HexFormat.of().formatHex(digest.digest()));
    }
}
