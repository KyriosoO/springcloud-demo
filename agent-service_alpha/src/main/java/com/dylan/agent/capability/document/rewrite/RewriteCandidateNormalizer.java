package com.dylan.agent.capability.document.rewrite;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Objects;

/** 对 Runtime 改写候选执行 Java 侧可信校验、去重和截断。 */
public final class RewriteCandidateNormalizer {

    private static final List<String> FORBIDDEN_TOKENS = List.of(
            "dsl",
            "filter",
            "indexalias",
            "retrievalprofile",
            "aclscope",
            "acl",
            "topk",
            "sort",
            "\"query\"",
            "\"bool\"",
            "\"must\"",
            "\"term\"");

    public QueryVariants normalize(
            String normalizedQuery,
            List<String> ruleKeywords,
            List<DocumentRewriteCandidate> runtimeCandidates,
            int maxCandidates,
            int maxCandidateLength) {
        String query = normalizedQuery == null ? "" : normalizedQuery.trim();
        LinkedHashSet<String> accepted = new LinkedHashSet<>();
        int rejected = 0;
        for (DocumentRewriteCandidate candidate : runtimeCandidates == null ? List.<DocumentRewriteCandidate>of() : runtimeCandidates) {
            if (accepted.size() >= Math.max(0, maxCandidates)) {
                break;
            }
            String value = candidate == null ? null : candidate.text();
            String normalized = value == null ? null : value.trim().replaceAll("\\s+", " ");
            if (!isAllowed(normalized, query, maxCandidateLength)) {
                rejected++;
                continue;
            }
            accepted.add(normalized);
        }
        List<String> safeRuleKeywords = ruleKeywords == null ? List.of() : ruleKeywords.stream()
                .filter(Objects::nonNull)
                .map(String::trim)
                .filter(value -> !value.isBlank())
                .distinct()
                .toList();
        List<String> safeCandidates = List.copyOf(accepted);
        return new QueryVariants(query, safeRuleKeywords, safeCandidates, rejected, digest(safeCandidates));
    }

    private static boolean isAllowed(String value, String originalQuery, int maxCandidateLength) {
        if (value == null || value.isBlank()) {
            return false;
        }
        if (value.equals(originalQuery)) {
            return false;
        }
        int maxLength = Math.max(1, maxCandidateLength);
        if (value.length() > maxLength) {
            return false;
        }
        for (int i = 0; i < value.length(); i++) {
            char current = value.charAt(i);
            if (Character.isISOControl(current) && !Character.isWhitespace(current)) {
                return false;
            }
        }
        String lowered = value.toLowerCase(Locale.ROOT);
        return FORBIDDEN_TOKENS.stream().noneMatch(lowered::contains);
    }

    private static String digest(List<String> candidates) {
        if (candidates == null || candidates.isEmpty()) {
            return "";
        }
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(String.join("|", candidates).getBytes(StandardCharsets.UTF_8));
            return "sha256:" + HexFormat.of().formatHex(hash, 0, 8);
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 is not available", ex);
        }
    }
}
