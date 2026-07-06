package com.dylan.esquery.api.model;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * 混合检索融合后的文档证据。
 */
public class HybridSearchHit {
	private String documentId;
	private String chunkId;
	private Integer chunkIndex;
	private String title;
	private String sourceType;
	private String section;
	private Integer page;
	private String sourceUri;
	private String snippet;
	private String content;
	private List<String> contextBefore;
	private List<String> contextAfter;
	private Integer charStart;
	private Integer charEnd;
	private Integer keywordRank;
	private Integer vectorRank;
	private BigDecimal score;
	private BigDecimal rrfScore;
	private List<String> retrievalChannels;
	private Map<String, Object> metadata;

	public String getDocumentId() { return documentId; }
	public void setDocumentId(String documentId) { this.documentId = documentId; }
	public String getChunkId() { return chunkId; }
	public void setChunkId(String chunkId) { this.chunkId = chunkId; }
	public Integer getChunkIndex() { return chunkIndex; }
	public void setChunkIndex(Integer chunkIndex) { this.chunkIndex = chunkIndex; }
	public String getTitle() { return title; }
	public void setTitle(String title) { this.title = title; }
	public String getSourceType() { return sourceType; }
	public void setSourceType(String sourceType) { this.sourceType = sourceType; }
	public String getSection() { return section; }
	public void setSection(String section) { this.section = section; }
	public Integer getPage() { return page; }
	public void setPage(Integer page) { this.page = page; }
	public String getSourceUri() { return sourceUri; }
	public void setSourceUri(String sourceUri) { this.sourceUri = sourceUri; }
	public String getSnippet() { return snippet; }
	public void setSnippet(String snippet) { this.snippet = snippet; }
	public String getContent() { return content; }
	public void setContent(String content) { this.content = content; }
	public List<String> getContextBefore() { return contextBefore; }
	public void setContextBefore(List<String> contextBefore) { this.contextBefore = contextBefore; }
	public List<String> getContextAfter() { return contextAfter; }
	public void setContextAfter(List<String> contextAfter) { this.contextAfter = contextAfter; }
	public Integer getCharStart() { return charStart; }
	public void setCharStart(Integer charStart) { this.charStart = charStart; }
	public Integer getCharEnd() { return charEnd; }
	public void setCharEnd(Integer charEnd) { this.charEnd = charEnd; }
	public Integer getKeywordRank() { return keywordRank; }
	public void setKeywordRank(Integer keywordRank) { this.keywordRank = keywordRank; }
	public Integer getVectorRank() { return vectorRank; }
	public void setVectorRank(Integer vectorRank) { this.vectorRank = vectorRank; }
	public BigDecimal getScore() { return score; }
	public void setScore(BigDecimal score) { this.score = score; }
	public BigDecimal getRrfScore() { return rrfScore; }
	public void setRrfScore(BigDecimal rrfScore) { this.rrfScore = rrfScore; }
	public List<String> getRetrievalChannels() { return retrievalChannels; }
	public void setRetrievalChannels(List<String> retrievalChannels) { this.retrievalChannels = retrievalChannels; }
	public Map<String, Object> getMetadata() { return metadata; }
	public void setMetadata(Map<String, Object> metadata) { this.metadata = metadata; }
}
