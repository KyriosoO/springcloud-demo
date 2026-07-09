package com.dylan.esquery.api.model;

import java.util.List;
import java.util.Map;

/**
 * 混合检索请求，queryVector 由上游生成，es-query 只负责检索与融合。
 */
public class HybridSearchRequest {
	private String queryText;
	private String domain;
	private String materialType;
	private String retrievalProfile;
	private String profileVersion;
	private String indexAlias;
	private String permissionEvidenceId;
	private String permissionVersion;
	private String filterDigest;
	private Map<String, Object> keywordDsl;
	private Map<String, Object> filters;
	private List<Double> queryVector;
	private String embeddingField;
	private List<HybridSearchChannelRequest> channels;
	private Integer keywordK;
	private Integer vectorK;
	private Integer exactK;
	private Integer phraseK;
	private Integer topK;
	private Integer numCandidates;
	private Integer rrfK;
	private Integer maxChunksPerDocument;
	private Map<String, Double> channelWeights;
	private List<String> sourceExcludes;
	private HybridContextWindow contextWindow;
	private Integer trackTotalHits;

	public String getQueryText() { return queryText; }
	public void setQueryText(String queryText) { this.queryText = queryText; }
	public String getDomain() { return domain; }
	public void setDomain(String domain) { this.domain = domain; }
	public String getMaterialType() { return materialType; }
	public void setMaterialType(String materialType) { this.materialType = materialType; }
	public String getRetrievalProfile() { return retrievalProfile; }
	public void setRetrievalProfile(String retrievalProfile) { this.retrievalProfile = retrievalProfile; }
	public String getProfileVersion() { return profileVersion; }
	public void setProfileVersion(String profileVersion) { this.profileVersion = profileVersion; }
	public String getIndexAlias() { return indexAlias; }
	public void setIndexAlias(String indexAlias) { this.indexAlias = indexAlias; }
	public String getPermissionEvidenceId() { return permissionEvidenceId; }
	public void setPermissionEvidenceId(String permissionEvidenceId) { this.permissionEvidenceId = permissionEvidenceId; }
	public String getPermissionVersion() { return permissionVersion; }
	public void setPermissionVersion(String permissionVersion) { this.permissionVersion = permissionVersion; }
	public String getFilterDigest() { return filterDigest; }
	public void setFilterDigest(String filterDigest) { this.filterDigest = filterDigest; }
	public Map<String, Object> getKeywordDsl() { return keywordDsl; }
	public void setKeywordDsl(Map<String, Object> keywordDsl) { this.keywordDsl = keywordDsl; }
	public Map<String, Object> getFilters() { return filters; }
	public void setFilters(Map<String, Object> filters) { this.filters = filters; }
	public List<Double> getQueryVector() { return queryVector; }
	public void setQueryVector(List<Double> queryVector) { this.queryVector = queryVector; }
	public String getEmbeddingField() { return embeddingField; }
	public void setEmbeddingField(String embeddingField) { this.embeddingField = embeddingField; }
	public List<HybridSearchChannelRequest> getChannels() { return channels; }
	public void setChannels(List<HybridSearchChannelRequest> channels) { this.channels = channels; }
	public Integer getKeywordK() { return keywordK; }
	public void setKeywordK(Integer keywordK) { this.keywordK = keywordK; }
	public Integer getVectorK() { return vectorK; }
	public void setVectorK(Integer vectorK) { this.vectorK = vectorK; }
	public Integer getExactK() { return exactK; }
	public void setExactK(Integer exactK) { this.exactK = exactK; }
	public Integer getPhraseK() { return phraseK; }
	public void setPhraseK(Integer phraseK) { this.phraseK = phraseK; }
	public Integer getTopK() { return topK; }
	public void setTopK(Integer topK) { this.topK = topK; }
	public Integer getNumCandidates() { return numCandidates; }
	public void setNumCandidates(Integer numCandidates) { this.numCandidates = numCandidates; }
	public Integer getRrfK() { return rrfK; }
	public void setRrfK(Integer rrfK) { this.rrfK = rrfK; }
	public Integer getMaxChunksPerDocument() { return maxChunksPerDocument; }
	public void setMaxChunksPerDocument(Integer maxChunksPerDocument) { this.maxChunksPerDocument = maxChunksPerDocument; }
	public Map<String, Double> getChannelWeights() { return channelWeights; }
	public void setChannelWeights(Map<String, Double> channelWeights) { this.channelWeights = channelWeights; }
	public List<String> getSourceExcludes() { return sourceExcludes; }
	public void setSourceExcludes(List<String> sourceExcludes) { this.sourceExcludes = sourceExcludes; }
	public HybridContextWindow getContextWindow() { return contextWindow; }
	public void setContextWindow(HybridContextWindow contextWindow) { this.contextWindow = contextWindow; }
	public Integer getTrackTotalHits() { return trackTotalHits; }
	public void setTrackTotalHits(Integer trackTotalHits) { this.trackTotalHits = trackTotalHits; }
}
