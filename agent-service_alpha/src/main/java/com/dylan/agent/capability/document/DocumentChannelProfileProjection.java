package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentRetrievalChannel;

import java.util.List;
import java.util.Map;

/** Document Profile 中冻结的 closed channel/fusion/rerank 投影。 */
public record DocumentChannelProfileProjection(
        int keywordCandidateCount,
        int vectorCandidateCount,
        int rrfK,
        int numCandidates,
        int maxChunksPerDocument,
        List<DocumentRetrievalChannel> enabledChannels,
        List<DocumentRetrievalChannel> requiredChannels,
        Map<DocumentRetrievalChannel,Integer> channelWeights,
        boolean rerankEnabled,
        int rerankTopN) {
    public DocumentChannelProfileProjection {
        enabledChannels=List.copyOf(enabledChannels==null?List.of():enabledChannels);
        requiredChannels=List.copyOf(requiredChannels==null?List.of():requiredChannels);
        channelWeights=Map.copyOf(channelWeights==null?Map.of():channelWeights);
        Map<DocumentRetrievalChannel,Integer> frozenWeights=channelWeights;
        if(keywordCandidateCount<=0||vectorCandidateCount<=0||rrfK<=0||numCandidates<=0||maxChunksPerDocument<=0
                ||enabledChannels.isEmpty()||!enabledChannels.containsAll(requiredChannels)
                ||enabledChannels.stream().anyMatch(channel->frozenWeights.getOrDefault(channel,0)<=0)
                ||rerankTopN<0)throw new IllegalArgumentException("document channel profile invalid");
    }
    public boolean enablesDenseVector(){return enabledChannels.contains(DocumentRetrievalChannel.DENSE_VECTOR);}
}
