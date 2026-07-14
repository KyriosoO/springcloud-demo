package com.dylan.agent.capability.document.profile;

import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.adapter.api.document.DocumentRetrievalChannel;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.DocumentCapabilityIds;

import java.util.EnumMap;
import java.util.LinkedHashSet;
import java.util.Objects;
import java.util.Set;

/** Policy/caller 集合收窄和 frozen typed limit 双门禁的唯一 projector。 */
public final class DocumentPlanningProfileProjector {
    public DocumentPlanningProfileProjection project(
            DocumentProfileSelection selection,
            DocumentResourceLimit limits,
            String selectedCapabilityId) {
        Objects.requireNonNull(selection);
        Objects.requireNonNull(limits);
        DocumentPlanOperation operation = operation(selectedCapabilityId);
        DocumentRetrievalProfile profile = selection.selectedProfile();
        DocumentPolicyConstraint policy = selection.policyConstraint();
        Set<DocumentPlanOperation> operations = intersection(profile.allowedOperations(),
                policy.allowedOperationsByDomain().get(profile.domain()));
        if (!operations.contains(operation)) throw new IllegalStateException("selected document operation is not allowed");
        Set<DocumentRetrievalChannel> channels = intersection(profile.allowedChannels(),
                policy.allowedChannelsByDomain().get(profile.domain()));
        if (!channels.containsAll(profile.requiredChannels())) {
            throw new IllegalStateException("document policy removes a required channel");
        }
        DocumentFeaturePolicy rewrite = gate(profile.rewritePolicy(), limits.enhancement().maxRewriteCandidates(), "rewrite");
        DocumentFeaturePolicy embedding = gate(profile.embeddingPolicy(),
                Math.min(limits.enhancement().maxEmbeddingTexts(), limits.enhancement().maxEmbeddingDimensions()), "embedding");
        DocumentFeaturePolicy rerank = gate(profile.rerankPolicy(), limits.enhancement().maxRerankCandidates(), "rerank");
        int generationLimit = operation == DocumentPlanOperation.SUMMARIZE
                ? Math.min(limits.output().maxSummaryChars(), limits.output().maxSummaryBullets())
                : limits.output().maxGeneratedChars();
        DocumentFeaturePolicy generation = gate(profile.generationPolicy(operation), generationLimit, "generation");
        if (embedding == DocumentFeaturePolicy.DISABLED) {
            if (profile.requiredChannels().contains(DocumentRetrievalChannel.DENSE_VECTOR)) {
                throw new IllegalStateException("required dense-vector channel has zero effective embedding budget");
            }
            channels = new LinkedHashSet<>(channels);
            channels.remove(DocumentRetrievalChannel.DENSE_VECTOR);
        }
        if (channels.isEmpty()) throw new IllegalStateException("document profile has no channel after projection");
        var fusion = profile.fusionPolicy();
        if (channels.size() > limits.retrieval().maxChannelCount()
                || fusion.keywordCandidateCount() > limits.retrieval().maxCandidatesPerChannel()
                || fusion.vectorCandidateCount() > limits.retrieval().maxCandidatesPerChannel()
                || fusion.numCandidates() > limits.retrieval().maxFusedCandidates()
                || profile.dedupPolicy().maxChunksPerDocument() > limits.retrieval().maxChunksPerDocument()
                || rerank != DocumentFeaturePolicy.DISABLED
                && fusion.rerankTopN() > limits.enhancement().maxRerankCandidates()) {
            throw new IllegalStateException("document profile exceeds effective retrieval limits");
        }
        var weights = new EnumMap<DocumentRetrievalChannel, Integer>(DocumentRetrievalChannel.class);
        channels.forEach(channel -> weights.put(channel, profile.channelWeights().get(channel)));
        return new DocumentPlanningProfileProjection(
                profile.domain(), profile.profileName(), selection.assetRef().documentProfileVersion(),
                selection.allowedCorpora(), operations, Set.copyOf(channels), profile.requiredChannels(), weights,
                fusion, profile.dedupPolicy(), profile.contextPolicy(), rewrite, embedding, rerank, generation,
                profile.searchableFields(), profile.returnableFields());
    }

    public static DocumentPlanOperation operation(String capabilityId) {
        return switch (capabilityId) {
            case DocumentCapabilityIds.SEARCH -> DocumentPlanOperation.SEARCH;
            case DocumentCapabilityIds.ANSWER -> DocumentPlanOperation.ANSWER;
            case DocumentCapabilityIds.SUMMARIZE -> DocumentPlanOperation.SUMMARIZE;
            default -> throw new IllegalArgumentException("unknown document capability operation");
        };
    }

    private static <T> Set<T> intersection(Set<T> left, Set<T> right) {
        if (right == null || right.isEmpty()) throw new IllegalStateException("document policy set is missing");
        var result = new LinkedHashSet<>(left);
        result.retainAll(right);
        if (result.isEmpty()) throw new IllegalStateException("document profile/policy intersection is empty");
        return Set.copyOf(result);
    }

    private static DocumentFeaturePolicy gate(DocumentFeaturePolicy policy, int limit, String feature) {
        if (policy == DocumentFeaturePolicy.REQUIRED && limit == 0) {
            throw new IllegalStateException("required document " + feature + " has zero effective budget");
        }
        return policy == DocumentFeaturePolicy.OPTIONAL && limit == 0 ? DocumentFeaturePolicy.DISABLED : policy;
    }
}
