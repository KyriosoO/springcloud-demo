package com.dylan.agent.capability.document.provider.security;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

/** DPO-1 的唯一 canonical 实现。 */
public final class DocumentProviderOutboundPolicyCanonicalizer {

    public String canonicalDigest(DocumentProviderOutboundPolicyDecision decision) {
        Writer writer = new Writer();
        writer.text("DPO-1");
        writer.text(decision.operationType().value());
        writer.text("DCK-1");
        writer.text(decision.corpusKey().domain());
        writer.text(decision.corpusKey().materialType());
        writer.text(decision.authorizationBindingDigest());
        writer.text(decision.policyEvidenceDigest());
        writer.text(decision.permissionEvidenceDigest());
        writer.text(decision.profileProjectionDigest());
        writer.text(decision.resourceLimitReference().canonicalDigest());
        writer.integer(decision.orderedFieldRules().size());
        for (DocumentProviderFieldRuleDecision rule : decision.orderedFieldRules()) {
            writer.text(rule.field().domain());
            writer.text(rule.field().field());
            writer.text(rule.classification().canonicalDigest());
            writer.text(rule.maskType().name());
        }
        writer.longValue(decision.validUntil().toEpochMilli());
        return writer.hex();
    }

    private static final class Writer {
        private final MessageDigest digest;

        private Writer() {
            try {
                digest = MessageDigest.getInstance("SHA-256");
            } catch (NoSuchAlgorithmException ex) {
                throw new IllegalStateException("SHA-256 unavailable", ex);
            }
        }

        private void text(String value) {
            byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
            integer(bytes.length);
            digest.update(bytes);
        }

        private void integer(int value) {
            digest.update(ByteBuffer.allocate(Integer.BYTES).putInt(value).array());
        }

        private void longValue(long value) {
            digest.update(ByteBuffer.allocate(Long.BYTES).putLong(value).array());
        }

        private String hex() { return HexFormat.of().formatHex(digest.digest()); }
    }
}
