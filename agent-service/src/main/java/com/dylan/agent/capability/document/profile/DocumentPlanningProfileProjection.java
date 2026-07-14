package com.dylan.agent.capability.document.profile;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;
import com.dylan.agent.adapter.api.document.DocumentRetrievalChannel;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.DocumentChannelProfileProjection;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;

import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** freeze 后唯一 trusted Profile 投影；无 public/Jackson 构造入口。 */
public final class DocumentPlanningProfileProjection {
    private final String domain;
    private final String profileName;
    private final String documentProfileVersion;
    private final List<DocumentCorpusKey> allowedCorpora;
    private final Set<DocumentPlanOperation> allowedOperations;
    private final Set<DocumentRetrievalChannel> allowedChannels;
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

    DocumentPlanningProfileProjection(
            String domain,
            String profileName,
            String documentProfileVersion,
            List<DocumentCorpusKey> allowedCorpora,
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
            DocumentFeaturePolicy generationPolicy,
            Set<CanonicalFieldRef> searchableFields,
            Set<CanonicalFieldRef> returnableFields) {
        this.domain = Objects.requireNonNull(domain);
        this.profileName = Objects.requireNonNull(profileName);
        if (documentProfileVersion == null || !documentProfileVersion.matches("dp1-[0-9a-f]{64}")) {
            throw new IllegalArgumentException("invalid document profile projection version");
        }
        this.documentProfileVersion = documentProfileVersion;
        this.allowedCorpora = List.copyOf(Objects.requireNonNull(allowedCorpora));
        this.allowedOperations = Set.copyOf(Objects.requireNonNull(allowedOperations));
        this.allowedChannels = Set.copyOf(Objects.requireNonNull(allowedChannels));
        this.requiredChannels = Set.copyOf(Objects.requireNonNull(requiredChannels));
        if (this.allowedCorpora.isEmpty() || this.allowedOperations.isEmpty() || this.allowedChannels.isEmpty()
                || !this.allowedChannels.containsAll(this.requiredChannels)) {
            throw new IllegalArgumentException("invalid document profile projection sets");
        }
        var weights = new EnumMap<DocumentRetrievalChannel, Integer>(DocumentRetrievalChannel.class);
        weights.putAll(Objects.requireNonNull(channelWeights));
        if (!weights.keySet().equals(this.allowedChannels)) {
            throw new IllegalArgumentException("projection channel weights mismatch");
        }
        this.channelWeights = Map.copyOf(weights);
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

    public String domain() { return domain; }
    public String profileName() { return profileName; }
    public String documentProfileVersion() { return documentProfileVersion; }
    public List<DocumentCorpusKey> allowedCorpora() { return allowedCorpora; }
    public Set<DocumentPlanOperation> allowedOperations() { return allowedOperations; }
    public Set<DocumentRetrievalChannel> allowedChannels() { return allowedChannels; }
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
                allowedChannels.stream().sorted().toList(), requiredChannels.stream().sorted().toList(),
                channelWeights, rerankPolicy != DocumentFeaturePolicy.DISABLED,
                rerankPolicy == DocumentFeaturePolicy.DISABLED ? 0 : fusionPolicy.rerankTopN());
    }
}
