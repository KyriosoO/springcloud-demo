package com.dylan.agent.capability.document.acl;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

final class DocumentAclCanonicalDigests {
    private DocumentAclCanonicalDigests() {
    }

    static String digest(String contract, String... fields) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            update(digest, contract);
            for (String field : fields) update(digest, field);
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }

    private static void update(MessageDigest digest, String value) {
        byte[] bytes = String.valueOf(value).getBytes(StandardCharsets.UTF_8);
        digest.update(new byte[] {
                (byte) (bytes.length >>> 24), (byte) (bytes.length >>> 16),
                (byte) (bytes.length >>> 8), (byte) bytes.length});
        digest.update(bytes);
    }
}
