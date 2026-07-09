package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentHybridOptions;
import com.dylan.agent.config.AgentProperties;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;

/** 解析并冻结资料域/资料类型检索 profile。 */
public class DocumentRetrievalProfileResolver {

    private final AgentProperties properties;

    public DocumentRetrievalProfileResolver(AgentProperties properties) {
        this.properties = Objects.requireNonNull(properties, "properties must not be null");
    }

    public DocumentRetrievalProfile resolve(String domain, String materialType, String requestedProfile) {
        String normalizedDomain = blankToNull(domain);
        String normalizedMaterialType = blankToNull(materialType);
        String normalizedRequestedProfile = blankToNull(requestedProfile);
        List<AgentProperties.RetrievalProfileProperties> domainProfiles =
                properties.getDocument().getRetrievalProfiles().values().stream()
                .filter(Objects::nonNull)
                .filter(AgentProperties.RetrievalProfileProperties::isEnabled)
                .filter(candidate -> equalsTrimmed(candidate.getDomain(), normalizedDomain))
                .toList();
        if (domainProfiles.isEmpty()) {
            throw new IllegalArgumentException("document retrievalProfile is not configured for domain");
        }

        AgentProperties.RetrievalProfileProperties profile;
        if (normalizedRequestedProfile != null) {
            profile = domainProfiles.stream()
                    .filter(candidate -> equalsTrimmed(candidate.getRetrievalProfile(), normalizedRequestedProfile))
                    .findFirst()
                    .orElseThrow(() -> new IllegalArgumentException(
                            "document retrievalProfile is not configured for domain"));
            if (normalizedMaterialType != null && !supportsMaterialType(profile, normalizedMaterialType)) {
                throw new IllegalArgumentException("document retrievalProfile is not configured for materialType");
            }
        } else if (normalizedMaterialType != null) {
            profile = domainProfiles.stream()
                    .filter(candidate -> supportsMaterialType(candidate, normalizedMaterialType))
                    .findFirst()
                    .orElseThrow(() -> new IllegalArgumentException(
                            "document retrievalProfile is not configured for materialType"));
        } else {
            profile = domainProfiles.stream()
                    .filter(candidate -> materialTypes(candidate).isEmpty())
                    .findFirst()
                    .orElseGet(() -> domainProfiles.getFirst());
        }

        String resolvedMaterialType = normalizedMaterialType != null
                ? normalizedMaterialType
                : defaultMaterialType(profile);
        return new DocumentRetrievalProfile(
                normalizedDomain,
                resolvedMaterialType,
                profile.getRetrievalProfile(),
                derivedProfileVersion(profile),
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
                        normalizedChannelWeights(profile.getChannelWeights()),
                        blankToDefault(profile.getEmbeddingField(), "embedding"),
                        blankToDefault(profile.getEmbeddingProvider(), properties.getDocument().getEmbedding().getProvider()),
                        blankToDefault(profile.getEmbeddingModel(), properties.getDocument().getEmbedding().getModel()),
                        effectiveEmbeddingDimension(profile),
                        profile.getRerank().isEnabled(),
                        profile.getRerank().getTopN()));
    }

    private static boolean supportsMaterialType(
            AgentProperties.RetrievalProfileProperties profile,
            String materialType) {
        List<String> materialTypes = materialTypes(profile);
        return materialTypes.stream().anyMatch(value -> equalsTrimmed(value, materialType));
    }

    private static List<String> materialTypes(AgentProperties.RetrievalProfileProperties profile) {
        LinkedHashSet<String> values = new LinkedHashSet<>();
        if (profile.getMaterialTypes() != null) {
            profile.getMaterialTypes().stream()
                    .filter(Objects::nonNull)
                    .map(String::trim)
                    .filter(value -> !value.isBlank())
                    .forEach(values::add);
        }
        return List.copyOf(values);
    }

    private static String defaultMaterialType(AgentProperties.RetrievalProfileProperties profile) {
        List<String> materialTypes = materialTypes(profile);
        return materialTypes.isEmpty() ? null : materialTypes.getFirst();
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

    private static Map<String, Double> normalizedChannelWeights(Map<String, Double> channelWeights) {
        if (channelWeights == null || channelWeights.isEmpty()) {
            return Map.of();
        }
        Map<String, Double> normalized = new LinkedHashMap<>();
        channelWeights.forEach((channel, weight) -> {
            String key = blankToNull(channel);
            if (key != null && weight != null) {
                normalized.put(key.toUpperCase(Locale.ROOT), weight);
            }
        });
        return normalized;
    }

    private static String derivedProfileVersion(AgentProperties.RetrievalProfileProperties profile) {
        List<String> tokens = new ArrayList<>();
        tokens.add("domain=" + nullToEmpty(profile.getDomain()));
        tokens.add("materialTypes=" + String.join(",", materialTypes(profile)));
        tokens.add("retrievalProfile=" + nullToEmpty(profile.getRetrievalProfile()));
        tokens.add("indexAlias=" + nullToEmpty(profile.getIndexAlias()));
        tokens.add("channels=" + String.join(",", normalizedChannels(profile.getChannels())));
        tokens.add("channelWeights=" + normalizedChannelWeights(profile.getChannelWeights()));
        tokens.add("keywordK=" + profile.getKeywordK());
        tokens.add("exactK=" + profile.getExactK());
        tokens.add("phraseK=" + profile.getPhraseK());
        tokens.add("vectorK=" + profile.getVectorK());
        tokens.add("rrfK=" + profile.getRrfK());
        tokens.add("numCandidates=" + profile.getNumCandidates());
        tokens.add("maxChunksPerDocument=" + profile.getMaxChunksPerDocument());
        tokens.add("embeddingField=" + nullToEmpty(profile.getEmbeddingField()));
        tokens.add("embeddingProvider=" + nullToEmpty(profile.getEmbeddingProvider()));
        tokens.add("embeddingModel=" + nullToEmpty(profile.getEmbeddingModel()));
        tokens.add("embeddingDimension=" + profile.getEmbeddingDimension());
        tokens.add("rerankEnabled=" + profile.getRerank().isEnabled());
        tokens.add("rerankTopN=" + profile.getRerank().getTopN());
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(String.join("|", tokens).getBytes(StandardCharsets.UTF_8));
            return "pv-" + java.util.HexFormat.of().formatHex(hash, 0, 8);
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 is not available", ex);
        }
    }

    private static String nullToEmpty(String value) {
        return value == null ? "" : value.trim();
    }

    private static boolean equalsTrimmed(String left, String right) {
        if (left == null || right == null) {
            return false;
        }
        return left.trim().equals(right.trim());
    }

    private static String blankToDefault(String value, String defaultValue) {
        String normalized = blankToNull(value);
        return normalized == null ? defaultValue : normalized;
    }

    private static int effectiveEmbeddingDimension(AgentProperties.RetrievalProfileProperties profile) {
        return Math.max(0, profile.getEmbeddingDimension());
    }

    private static String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }
}
