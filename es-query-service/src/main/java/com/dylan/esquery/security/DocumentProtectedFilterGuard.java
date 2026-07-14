package com.dylan.esquery.security;

import com.dylan.esquery.api.model.DocumentProtectedFilterDto;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;

/** 专用 Document request boundary 的 protected filter 结构、cap 与 DAF-1 binding gate。 */
public final class DocumentProtectedFilterGuard {
    private static final int MAX_NODES = 64;
    private static final int MAX_DEPTH = 8;
    private static final int MAX_TERMS = 1024;
    private static final int MAX_CANONICAL_BYTES = 128 * 1024;

    public void requireValid(com.dylan.esquery.api.model.document.HybridSearchRequest request) {
        if (request == null) throw new IllegalArgumentException("document hybrid request is required");
        String actual=canonicalDigest(request);
        if(!actual.equals(request.protectedFilterDigest()))throw new IllegalArgumentException("document protected filter digest mismatch or exceeds security cap");
    }

    String canonicalDigest(com.dylan.esquery.api.model.document.HybridSearchRequest request) {
        Counters counters = new Counters();
        String root = canonical(request.protectedFilter(), 1, counters);
        String canonical = request.corpusKey().domain() + "\u001f" + request.corpusKey().materialType()
                + "\u001f" + root + "\u001f" + request.executionBinding().aclEvidenceDigest() + "\u001f"
                + request.executionBinding().profileProjectionDigest() + "\u001f"
                + request.executionBinding().resourceLimit().canonicalDigest();
        if (canonical.getBytes(StandardCharsets.UTF_8).length > MAX_CANONICAL_BYTES
                || counters.nodes > MAX_NODES || counters.terms > MAX_TERMS
                ) {
            throw new IllegalArgumentException("document protected filter exceeds security cap");
        }
        return digest("DAF-1", canonical);
    }

    private String canonical(DocumentProtectedFilterDto node, int depth, Counters counters) {
        if (node == null || depth > MAX_DEPTH) throw new IllegalArgumentException("invalid protected filter depth");
        counters.nodes++;
        return switch (node.kind()) {
            case EXACT -> {
                requireExactField(node.field());
                counters.terms++;
                yield "EXACT(" + node.field().name() + "," + value(node.value()) + ")";
            }
            case ANY_TERMS -> {
                requireAnyTermsField(node.field());
                counters.terms += node.values().size();
                yield "ANY_TERMS(" + node.field().name() + "," + values(node.values()) + ")";
            }
            case NONE_TERMS -> {
                if (node.field() != DocumentProtectedFilterDto.Field.DOCUMENT_ID) {
                    throw new IllegalArgumentException("NONE_TERMS only supports DOCUMENT_ID");
                }
                counters.terms += node.values().size();
                yield "NONE_TERMS(" + node.field().name() + "," + values(node.values()) + ")";
            }
            case ALL_OF, ANY_OF -> {
                String joined = node.children().stream().map(child -> canonical(child, depth + 1, counters))
                        .distinct().sorted().map(DocumentProtectedFilterGuard::value).reduce("", String::concat);
                yield (node.kind() == DocumentProtectedFilterDto.Kind.ALL_OF ? "ALL" : "ANY")
                        + "(" + joined + ")";
            }
        };
    }

    private static void requireExactField(DocumentProtectedFilterDto.Field field) {
        if (field != DocumentProtectedFilterDto.Field.TENANT_ID
                && field != DocumentProtectedFilterDto.Field.STATUS
                && field != DocumentProtectedFilterDto.Field.VISIBILITY) {
            throw new IllegalArgumentException("protected filter field does not support EXACT");
        }
    }

    private static void requireAnyTermsField(DocumentProtectedFilterDto.Field field) {
        if (field == DocumentProtectedFilterDto.Field.TENANT_ID
                || field == DocumentProtectedFilterDto.Field.STATUS
                || field == DocumentProtectedFilterDto.Field.VISIBILITY) {
            throw new IllegalArgumentException("protected filter field does not support ANY_TERMS");
        }
    }

    private static String values(List<String> values) {
        return values.stream().sorted().distinct().map(DocumentProtectedFilterGuard::value)
                .reduce("", String::concat);
    }

    private static String value(String value) {
        if (value == null || value.isBlank() || value.codePointCount(0, value.length()) > 512
                || value.codePoints().anyMatch(Character::isISOControl)) {
            throw new IllegalArgumentException("invalid protected filter value");
        }
        return value.length() + ":" + value;
    }

    private static String digest(String contract, String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            update(digest, contract);
            update(digest, value);
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }

    private static void update(MessageDigest digest, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        digest.update(new byte[] {(byte) (bytes.length >>> 24), (byte) (bytes.length >>> 16),
                (byte) (bytes.length >>> 8), (byte) bytes.length});
        digest.update(bytes);
    }

    private static final class Counters {
        private int nodes;
        private int terms;
    }
}
