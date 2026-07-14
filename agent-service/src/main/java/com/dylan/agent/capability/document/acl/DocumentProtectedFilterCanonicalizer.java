package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.document.*;
import com.dylan.agent.adapter.api.operation.ResourceLimitReference;

import java.nio.charset.StandardCharsets;
import java.util.List;

/** DAF-1 canonicalizer：集合和逻辑节点顺序不影响 digest。 */
public final class DocumentProtectedFilterCanonicalizer {
    private final DocumentAclCompilerLimits limits;

    public DocumentProtectedFilterCanonicalizer(DocumentAclCompilerLimits limits) {
        this.limits = limits;
    }

    public String digest(
            DocumentCorpusKey corpusKey,
            DocumentProtectedFilterNode root,
            String aclEvidenceDigest,
            String profileProjectionDigest,
            ResourceLimitReference resourceLimitReference) {
        Counters counters = new Counters();
        String canonicalRoot = canonical(root, 1, counters);
        String canonical = corpusKey.domain() + "\u001f" + corpusKey.materialType() + "\u001f"
                + canonicalRoot + "\u001f" + aclEvidenceDigest + "\u001f" + profileProjectionDigest
                + "\u001f" + resourceLimitReference.canonicalDigest();
        if (canonical.getBytes(StandardCharsets.UTF_8).length > limits.maxCanonicalBytes()) {
            throw new IllegalArgumentException("protected filter canonical bytes exceed cap");
        }
        if (counters.nodes > limits.maxAstNodes() || counters.terms > limits.maxTerms()) {
            throw new IllegalArgumentException("protected filter structure exceeds cap");
        }
        return DocumentAclCanonicalDigests.digest("DAF-1", canonical);
    }

    private String canonical(DocumentProtectedFilterNode node, int depth, Counters counters) {
        if (depth > limits.maxAstDepth()) throw new IllegalArgumentException("protected filter depth exceeds cap");
        counters.nodes++;
        if (node instanceof DocumentExactTerm exact) {
            counters.terms++;
            return "EXACT(" + exact.field().name() + "," + value(exact.value()) + ")";
        }
        if (node instanceof DocumentAnyTerms any) {
            counters.terms += any.values().size();
            return "ANY_TERMS(" + any.field().name() + "," + values(any.values().stream().toList()) + ")";
        }
        if (node instanceof DocumentNoneTerms none) {
            counters.terms += none.values().size();
            return "NONE_TERMS(" + none.field().name() + "," + values(none.values().stream().toList()) + ")";
        }
        List<DocumentProtectedFilterNode> children;
        String kind;
        if (node instanceof DocumentAllOf all) {
            children = all.children();
            kind = "ALL";
        } else if (node instanceof DocumentAnyOf any) {
            children = any.children();
            kind = "ANY";
        } else {
            throw new IllegalArgumentException("unknown protected filter subtype");
        }
        String joined = children.stream().map(child -> canonical(child, depth + 1, counters))
                .distinct().sorted().map(DocumentProtectedFilterCanonicalizer::value)
                .reduce("", String::concat);
        return kind + "(" + joined + ")";
    }

    private static String values(List<String> values) {
        return values.stream().sorted().distinct().map(DocumentProtectedFilterCanonicalizer::value)
                .reduce("", String::concat);
    }

    private static String value(String value) {
        if (value == null || value.isBlank() || value.length() > 512 || value.indexOf('\u0000') >= 0) {
            throw new IllegalArgumentException("protected filter value is invalid");
        }
        return value.length() + ":" + value;
    }

    private static final class Counters {
        private int nodes;
        private int terms;
    }
}
