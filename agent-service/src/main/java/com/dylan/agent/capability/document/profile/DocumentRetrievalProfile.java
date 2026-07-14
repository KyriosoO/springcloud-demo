package com.dylan.agent.capability.document.profile;

import com.dylan.agent.adapter.api.document.DocumentRetrievalChannel;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;

import java.util.EnumMap;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Pattern;

/** exact AgentProfile child asset 中的不可变文档策略；不持有预算、索引或 Provider 事实。 */
public record DocumentRetrievalProfile(
        String domain,
        String profileName,
        boolean defaultProfile,
        Set<String> allowedMaterialTypes,
        Set<DocumentPlanOperation> allowedOperations,
        Set<DocumentRetrievalChannel> allowedChannels,
        Set<DocumentRetrievalChannel> requiredChannels,
        Map<DocumentRetrievalChannel, Integer> channelWeights,
        DocumentFusionPolicy fusionPolicy,
        DocumentDedupPolicy dedupPolicy,
        DocumentContextPolicy contextPolicy,
        DocumentFeaturePolicy rewritePolicy,
        DocumentFeaturePolicy embeddingPolicy,
        DocumentFeaturePolicy rerankPolicy,
        Map<DocumentPlanOperation, DocumentFeaturePolicy> generationPolicy,
        Set<CanonicalFieldRef> searchableFields,
        Set<CanonicalFieldRef> returnableFields) {

    private static final Pattern CANONICAL_IDENTIFIER =
            Pattern.compile("[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*");

    public DocumentRetrievalProfile {
        domain = text(domain, "domain");
        profileName = text(profileName, "profileName");
        allowedMaterialTypes = Set.copyOf(Objects.requireNonNull(allowedMaterialTypes));
        allowedOperations = Set.copyOf(Objects.requireNonNull(allowedOperations));
        allowedChannels = Set.copyOf(Objects.requireNonNull(allowedChannels));
        requiredChannels = Set.copyOf(Objects.requireNonNull(requiredChannels));
        if (allowedMaterialTypes.isEmpty() || allowedOperations.isEmpty() || allowedChannels.isEmpty()) {
            throw new IllegalArgumentException("document profile material types, operations and channels must not be empty");
        }
        if (allowedMaterialTypes.size() > 32 || allowedChannels.size() > 8) {
            throw new IllegalArgumentException("document profile configured set exceeds hard cap");
        }
        if (!profileName.matches("[A-Za-z0-9][A-Za-z0-9._-]{0,63}")) {
            throw new IllegalArgumentException("invalid document profileName");
        }
        if (!CANONICAL_IDENTIFIER.matcher(domain).matches()) {
            throw new IllegalArgumentException("invalid canonical document domain");
        }
        for (String materialType : allowedMaterialTypes) {
            if (materialType == null || !CANONICAL_IDENTIFIER.matcher(materialType).matches()) {
                throw new IllegalArgumentException("invalid canonical document materialType");
            }
        }
        if (!allowedChannels.containsAll(requiredChannels)) {
            throw new IllegalArgumentException("required document channels must be an allowed subset");
        }
        var weights = new EnumMap<DocumentRetrievalChannel, Integer>(DocumentRetrievalChannel.class);
        weights.putAll(Objects.requireNonNull(channelWeights));
        if (!weights.keySet().equals(allowedChannels) || weights.values().stream().anyMatch(value -> value == null || value <= 0)) {
            throw new IllegalArgumentException("document channel weights must positively and exactly cover allowed channels");
        }
        channelWeights = Map.copyOf(weights);
        Objects.requireNonNull(fusionPolicy);
        Objects.requireNonNull(dedupPolicy);
        Objects.requireNonNull(contextPolicy);
        Objects.requireNonNull(rewritePolicy);
        Objects.requireNonNull(embeddingPolicy);
        Objects.requireNonNull(rerankPolicy);
        var generations = new EnumMap<DocumentPlanOperation, DocumentFeaturePolicy>(DocumentPlanOperation.class);
        generations.putAll(Objects.requireNonNull(generationPolicy));
        if (!generations.keySet().equals(allowedOperations)) {
            throw new IllegalArgumentException("generation policy must exactly cover allowed operations");
        }
        if (generations.getOrDefault(DocumentPlanOperation.SEARCH, DocumentFeaturePolicy.DISABLED)
                != DocumentFeaturePolicy.DISABLED) {
            throw new IllegalArgumentException("SEARCH generation must be disabled");
        }
        generationPolicy = Map.copyOf(generations);
        searchableFields = Set.copyOf(Objects.requireNonNull(searchableFields));
        returnableFields = Set.copyOf(Objects.requireNonNull(returnableFields));
        boolean crossDomainField = false;
        for (CanonicalFieldRef field : searchableFields) crossDomainField |= !field.domain().equals(domain);
        for (CanonicalFieldRef field : returnableFields) crossDomainField |= !field.domain().equals(domain);
        if (searchableFields.size() > 256 || returnableFields.size() > 256 || crossDomainField) {
            throw new IllegalArgumentException("document field refs exceed cap or cross domain boundary");
        }
        if (allowedChannels.contains(DocumentRetrievalChannel.DENSE_VECTOR)
                && embeddingPolicy == DocumentFeaturePolicy.DISABLED) {
            throw new IllegalArgumentException("dense-vector channel requires embedding");
        }
        if (requiredChannels.contains(DocumentRetrievalChannel.DENSE_VECTOR)
                && embeddingPolicy != DocumentFeaturePolicy.REQUIRED) {
            throw new IllegalArgumentException("required dense-vector channel requires REQUIRED embedding");
        }
    }

    public DocumentFeaturePolicy generationPolicy(DocumentPlanOperation operation) {
        DocumentFeaturePolicy policy = generationPolicy.get(operation);
        if (policy == null) throw new IllegalArgumentException("operation is not allowed by document profile");
        return policy;
    }

    private static String text(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) throw new IllegalArgumentException(name + " must not be blank");
        return normalized;
    }
}
