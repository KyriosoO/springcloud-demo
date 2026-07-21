package com.dylan.agent.adapter.api.document;

import java.util.List;
import java.util.Map;

/** 启用/必需 channel 与冻结权重。 */
public record DocumentRetrievalChannels(
        List<DocumentRetrievalChannel> enabled,
        List<DocumentRetrievalChannel> required,
        Map<DocumentRetrievalChannel, Integer> weights,
        int candidatesPerChannel,
        int vectorNumCandidates) {
    public DocumentRetrievalChannels {
        enabled = List.copyOf(enabled == null ? List.of() : enabled);
        required = List.copyOf(required == null ? List.of() : required);
        weights = Map.copyOf(weights == null ? Map.of() : weights);
        Map<DocumentRetrievalChannel, Integer> frozenWeights = weights;
        if (enabled.isEmpty() || !enabled.containsAll(required) || candidatesPerChannel <= 0
                || vectorNumCandidates <= 0
                || enabled.contains(DocumentRetrievalChannel.DENSE_VECTOR)
                && vectorNumCandidates < candidatesPerChannel
                || enabled.stream().anyMatch(channel -> frozenWeights.getOrDefault(channel, 0) <= 0)) {
            throw new IllegalArgumentException("document retrieval channels invalid");
        }
    }
}
