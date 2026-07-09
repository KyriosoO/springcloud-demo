package com.dylan.agent.adapter.api.document;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 文档混合检索参数。 */
public final class DocumentHybridOptions {
    private final int keywordK;
    private final int vectorK;
    private final int rrfK;
    private final int numCandidates;
    private final int exactK;
    private final int phraseK;
    private final int maxChunksPerDocument;
    private final List<String> channels;
    private final Map<String, Double> channelWeights;
    private final String embeddingField;
    private final String embeddingProvider;
    private final String embeddingModel;
    private final int embeddingDimension;
    private final boolean rerankEnabled;
    private final int rerankTopN;

    public DocumentHybridOptions(int keywordK, int vectorK, int rrfK, int numCandidates) {
        this(keywordK, vectorK, rrfK, numCandidates, keywordK, keywordK, 1,
                List.of("BM25", "EXACT", "PHRASE", "DENSE_VECTOR"), Map.of(), "embedding", false, 0);
    }

    public DocumentHybridOptions(
            int keywordK,
            int vectorK,
            int rrfK,
            int numCandidates,
            int exactK,
            int phraseK,
            int maxChunksPerDocument,
            List<String> channels,
            Map<String, Double> channelWeights,
            String embeddingField,
            boolean rerankEnabled,
            int rerankTopN) {
        this(keywordK, vectorK, rrfK, numCandidates, exactK, phraseK, maxChunksPerDocument,
                channels, channelWeights, embeddingField, null, null, 0, rerankEnabled, rerankTopN);
    }

    public DocumentHybridOptions(
            int keywordK,
            int vectorK,
            int rrfK,
            int numCandidates,
            int exactK,
            int phraseK,
            int maxChunksPerDocument,
            List<String> channels,
            Map<String, Double> channelWeights,
            String embeddingField,
            String embeddingProvider,
            String embeddingModel,
            int embeddingDimension,
            boolean rerankEnabled,
            int rerankTopN) {
        this.keywordK = keywordK;
        this.vectorK = vectorK;
        this.rrfK = rrfK;
        this.numCandidates = numCandidates;
        this.exactK = exactK;
        this.phraseK = phraseK;
        this.maxChunksPerDocument = maxChunksPerDocument;
        this.channels = List.copyOf(channels == null ? List.of() : channels);
        this.channelWeights = Map.copyOf(channelWeights == null ? new LinkedHashMap<>() : channelWeights);
        this.embeddingField = embeddingField;
        this.embeddingProvider = embeddingProvider;
        this.embeddingModel = embeddingModel;
        this.embeddingDimension = embeddingDimension;
        this.rerankEnabled = rerankEnabled;
        this.rerankTopN = rerankTopN;
    }

    public int keywordK() { return keywordK; }
    public int vectorK() { return vectorK; }
    public int rrfK() { return rrfK; }
    public int numCandidates() { return numCandidates; }
    public int exactK() { return exactK; }
    public int phraseK() { return phraseK; }
    public int maxChunksPerDocument() { return maxChunksPerDocument; }
    public List<String> channels() { return channels; }
    public Map<String, Double> channelWeights() { return channelWeights; }
    public String embeddingField() { return embeddingField; }
    public String embeddingProvider() { return embeddingProvider; }
    public String embeddingModel() { return embeddingModel; }
    public int embeddingDimension() { return embeddingDimension; }
    public boolean rerankEnabled() { return rerankEnabled; }
    public int rerankTopN() { return rerankTopN; }

    public boolean requiresDenseVector() {
        return channels.stream().anyMatch(channel ->
                "DENSE_VECTOR".equalsIgnoreCase(channel) || "VECTOR".equalsIgnoreCase(channel));
    }
}
