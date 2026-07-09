package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentHybridOptions;
import com.dylan.agent.config.AgentProperties;

import java.util.List;
import java.util.Locale;
import java.util.Objects;

/** 解析并冻结资料域/资料类型检索 profile。 */
public class DocumentRetrievalProfileResolver {

    private final AgentProperties properties;

    public DocumentRetrievalProfileResolver(AgentProperties properties) {
        this.properties = Objects.requireNonNull(properties, "properties must not be null");
    }

    public DocumentRetrievalProfile resolve(String domain, String materialType, String requestedProfile) {
        var profile = properties.getDocument().getRetrievalProfiles().values().stream()
                .filter(Objects::nonNull)
                .filter(AgentProperties.RetrievalProfileProperties::isEnabled)
                .filter(candidate -> equalsTrimmed(candidate.getDomain(), domain))
                .filter(candidate -> requestedProfile == null || requestedProfile.isBlank()
                        || equalsTrimmed(candidate.getRetrievalProfile(), requestedProfile))
                .filter(candidate -> materialType == null || materialType.isBlank()
                        || candidate.getMaterialType() == null || candidate.getMaterialType().isBlank()
                        || equalsTrimmed(candidate.getMaterialType(), materialType))
                .max((left, right) -> Integer.compare(matchScore(left, materialType), matchScore(right, materialType)))
                .orElse(null);
        if (profile == null) {
            if (requestedProfile != null && !requestedProfile.isBlank()) {
                throw new IllegalArgumentException("document retrievalProfile is not configured for domain");
            }
            return defaultProfile(domain, materialType);
        }
        return new DocumentRetrievalProfile(
                domain,
                blankToNull(profile.getMaterialType()) == null ? blankToNull(materialType) : profile.getMaterialType(),
                profile.getRetrievalProfile(),
                blankToDefault(profile.getProfileVersion(), "v1"),
                blankToNull(profile.getIndexAlias()),
                new DocumentHybridOptions(
                        profile.getKeywordK(),
                        profile.getVectorK(),
                        profile.getRrfK(),
                        profile.getNumCandidates(),
                        profile.getExactK(),
                        profile.getPhraseK(),
                        profile.getMaxChunksPerDocument(),
                        normalizedChannels(profile.getChannels()),
                        profile.getChannelWeights(),
                        blankToDefault(profile.getEmbeddingField(), "embedding"),
                        profile.getRerank().isEnabled(),
                        profile.getRerank().getTopN()));
    }

    private DocumentRetrievalProfile defaultProfile(String domain, String materialType) {
        var hybrid = properties.getDocument().getHybrid();
        return new DocumentRetrievalProfile(
                domain,
                blankToNull(materialType),
                "default",
                "legacy",
                null,
                new DocumentHybridOptions(
                        hybrid.getKeywordK(),
                        hybrid.getVectorK(),
                        hybrid.getRrfK(),
                        hybrid.getNumCandidates()));
    }

    private static List<String> normalizedChannels(List<String> channels) {
        if (channels == null || channels.isEmpty()) {
            return List.of("BM25", "EXACT", "PHRASE", "DENSE_VECTOR");
        }
        return channels.stream()
                .filter(Objects::nonNull)
                .map(String::trim)
                .filter(value -> !value.isBlank())
                .map(value -> value.toUpperCase(Locale.ROOT))
                .distinct()
                .toList();
    }

    private static boolean equalsTrimmed(String left, String right) {
        if (left == null || right == null) {
            return false;
        }
        return left.trim().equals(right.trim());
    }

    private static int matchScore(AgentProperties.RetrievalProfileProperties candidate, String materialType) {
        if (materialType == null || materialType.isBlank()) {
            return 0;
        }
        if (equalsTrimmed(candidate.getMaterialType(), materialType)) {
            return 2;
        }
        if (candidate.getMaterialType() == null || candidate.getMaterialType().isBlank()) {
            return 1;
        }
        return 0;
    }

    private static String blankToDefault(String value, String defaultValue) {
        String normalized = blankToNull(value);
        return normalized == null ? defaultValue : normalized;
    }

    private static String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }
}
