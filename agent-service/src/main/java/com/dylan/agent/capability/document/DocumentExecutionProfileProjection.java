package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;
import com.dylan.agent.adapter.api.document.DocumentRetrievalChannel;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.profile.DocumentContextPolicy;
import com.dylan.agent.capability.document.profile.DocumentDedupPolicy;
import com.dylan.agent.capability.document.profile.DocumentFeaturePolicy;
import com.dylan.agent.capability.document.profile.DocumentFusionPolicy;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;

import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** Validator 输出给 Handler 的最小具体策略投影；不保留 allowed corpus/operation 集合。 */
public final class DocumentExecutionProfileProjection {
    private final String profileName;
    private final String documentProfileVersion;
    private final String profileProjectionDigest;
    private final DocumentCorpusKey selectedCorpus;
    private final DocumentPlanOperation operation;
    private final Set<DocumentRetrievalChannel> enabledChannels;
    private final Set<DocumentRetrievalChannel> requiredChannels;
    private final Map<DocumentRetrievalChannel, Integer> channelWeights;
    private final DocumentFusionPolicy fusionPolicy;
    private final DocumentDedupPolicy dedupPolicy;
    private final DocumentContextPolicy contextPolicy;
    private final DocumentFeaturePolicy rewritePolicy;
    private final DocumentFeaturePolicy embeddingPolicy;
    private final DocumentFeaturePolicy rerankPolicy;
    private final DocumentFeaturePolicy generationPolicy;
    private final Set<CanonicalFieldRef> searchableFields;
    private final Set<CanonicalFieldRef> returnableFields;

    DocumentExecutionProfileProjection(
            String profileName,
            String documentProfileVersion,
            String profileProjectionDigest,
            DocumentCorpusKey selectedCorpus,
            DocumentPlanOperation operation,
            Set<DocumentRetrievalChannel> enabledChannels,
            Set<DocumentRetrievalChannel> requiredChannels,
            Map<DocumentRetrievalChannel, Integer> channelWeights,
            DocumentFusionPolicy fusionPolicy,
            DocumentDedupPolicy dedupPolicy,
            DocumentContextPolicy contextPolicy,
            DocumentFeaturePolicy rewritePolicy,
            DocumentFeaturePolicy embeddingPolicy,
            DocumentFeaturePolicy rerankPolicy,
            DocumentFeaturePolicy generationPolicy,
            Set<CanonicalFieldRef> searchableFields,
            Set<CanonicalFieldRef> returnableFields) {
        this.profileName = Objects.requireNonNull(profileName);
        this.documentProfileVersion = Objects.requireNonNull(documentProfileVersion);
        if (profileProjectionDigest == null || !profileProjectionDigest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("invalid execution profile projection digest");
        }
        this.profileProjectionDigest = profileProjectionDigest;
        this.selectedCorpus = Objects.requireNonNull(selectedCorpus);
        this.operation = Objects.requireNonNull(operation);
        this.enabledChannels = Set.copyOf(Objects.requireNonNull(enabledChannels));
        this.requiredChannels = Set.copyOf(Objects.requireNonNull(requiredChannels));
        this.channelWeights = Map.copyOf(Objects.requireNonNull(channelWeights));
        if (this.enabledChannels.isEmpty() || !this.enabledChannels.containsAll(this.requiredChannels)
                || !this.channelWeights.keySet().equals(this.enabledChannels)) {
            throw new IllegalArgumentException("invalid execution profile channels");
        }
        this.fusionPolicy = Objects.requireNonNull(fusionPolicy);
        this.dedupPolicy = Objects.requireNonNull(dedupPolicy);
        this.contextPolicy = Objects.requireNonNull(contextPolicy);
        this.rewritePolicy = Objects.requireNonNull(rewritePolicy);
        this.embeddingPolicy = Objects.requireNonNull(embeddingPolicy);
        this.rerankPolicy = Objects.requireNonNull(rerankPolicy);
        this.generationPolicy = Objects.requireNonNull(generationPolicy);
        this.searchableFields = Set.copyOf(Objects.requireNonNull(searchableFields));
        this.returnableFields = Set.copyOf(Objects.requireNonNull(returnableFields));
    }

    public String profileName() { return profileName; }
    public String documentProfileVersion() { return documentProfileVersion; }
    public String profileProjectionDigest() { return profileProjectionDigest; }
    public DocumentCorpusKey selectedCorpus() { return selectedCorpus; }
    public DocumentPlanOperation operation() { return operation; }
    public Set<DocumentRetrievalChannel> enabledChannels() { return enabledChannels; }
    public Set<DocumentRetrievalChannel> requiredChannels() { return requiredChannels; }
    public Map<DocumentRetrievalChannel, Integer> channelWeights() { return channelWeights; }
    public DocumentFusionPolicy fusionPolicy() { return fusionPolicy; }
    public DocumentDedupPolicy dedupPolicy() { return dedupPolicy; }
    public DocumentContextPolicy contextPolicy() { return contextPolicy; }
    public DocumentFeaturePolicy rewritePolicy() { return rewritePolicy; }
    public DocumentFeaturePolicy embeddingPolicy() { return embeddingPolicy; }
    public DocumentFeaturePolicy rerankPolicy() { return rerankPolicy; }
    public DocumentFeaturePolicy generationPolicy() { return generationPolicy; }
    public Set<CanonicalFieldRef> searchableFields() { return searchableFields; }
    public Set<CanonicalFieldRef> returnableFields() { return returnableFields; }

    public DocumentChannelProfileProjection channelProjection() {
        return new DocumentChannelProfileProjection(
                fusionPolicy.keywordCandidateCount(), fusionPolicy.vectorCandidateCount(), fusionPolicy.rrfK(),
                fusionPolicy.numCandidates(), dedupPolicy.maxChunksPerDocument(),
                enabledChannels.stream().sorted().toList(), requiredChannels.stream().sorted().toList(),
                channelWeights, rerankPolicy != DocumentFeaturePolicy.DISABLED,
                rerankPolicy == DocumentFeaturePolicy.DISABLED ? 0 : fusionPolicy.rerankTopN());
    }
}
