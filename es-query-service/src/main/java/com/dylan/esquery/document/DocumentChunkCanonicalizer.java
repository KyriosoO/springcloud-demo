package com.dylan.esquery.document;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;
import java.util.Comparator;
import java.util.HexFormat;

/** CHUNK-1/CONTENT-1 的唯一 canonical 实现。 */
public final class DocumentChunkCanonicalizer {
    private DocumentChunkCanonicalizer() { }

    public static String chunkId(NormalizedDocument document, int chunkIndex, int start, int end, String strategyRef) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(digest("CHUNK-1", document.tenantId(),
                document.documentId(), document.documentVersion(), Integer.toString(chunkIndex),
                Integer.toString(start), Integer.toString(end), strategyRef));
    }

    public static String contentHash(String content, String title, String section,
                                     java.util.List<DocumentBusinessFieldValue> businessFields) {
        java.util.List<String> projection = businessFields.stream()
                .sorted(Comparator.comparing(DocumentBusinessFieldValue::name))
                .map(value -> value.name() + "=" + value.getClass().getSimpleName() + ":" + value.value())
                .toList();
        java.util.List<String> parts = new java.util.ArrayList<>();
        parts.add("CONTENT-1"); parts.add(content); parts.add(title); parts.add(section); parts.addAll(projection);
        return HexFormat.of().formatHex(digest(parts.toArray(String[]::new)));
    }

    private static byte[] digest(String... parts) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (String part : parts) {
                byte[] bytes = String.valueOf(part == null ? "" : part).getBytes(StandardCharsets.UTF_8);
                digest.update(ByteBuffer.allocate(Integer.BYTES).putInt(bytes.length).array());
                digest.update(bytes);
            }
            return digest.digest();
        } catch (Exception ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }
}
