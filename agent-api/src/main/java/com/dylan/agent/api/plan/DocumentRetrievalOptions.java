package com.dylan.agent.api.plan;

import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Min;

/** 文档检索选项。 */
@Schema(description = "文档检索选项")
public class DocumentRetrievalOptions {

    @Schema(description = "证据条数上限", nullable = true)
    @Min(1)
    private Integer topK;

    @Schema(description = "检索模式；未显式指定时由 Java 文档配置和 retrievalProfile 决定", nullable = true)
    private DocumentRetrievalMode retrievalMode;

    @Schema(description = "资料类型，例如 policy、notice、faq", nullable = true)
    private String materialType;

    @Schema(description = "检索 profile 标识，由 Java 侧校验并冻结", nullable = true)
    private String retrievalProfile;

    @Schema(description = "召回通道列表，例如 BM25、EXACT、PHRASE、DENSE_VECTOR", nullable = true)
    private List<String> retrievalChannels;

    @Schema(description = "请求级 rerank 启用建议，最终由 Java profile 配置裁剪", nullable = true)
    private Boolean rerankEnabled;

    @Schema(description = "页码，从 1 开始", nullable = true)
    @Min(1)
    private Integer page;

    @Schema(description = "每页大小", nullable = true)
    @Min(1)
    private Integer size;

    @Schema(description = "关键词召回候选数", nullable = true)
    @Min(1)
    private Integer keywordK;

    @Schema(description = "向量召回候选数", nullable = true)
    @Min(1)
    private Integer vectorK;

    @Schema(description = "RRF 平滑常量", nullable = true)
    @Min(1)
    private Integer rrfK;

    @Schema(description = "向量召回候选池大小", nullable = true)
    @Min(1)
    private Integer numCandidates;

    public Integer getTopK() { return topK; }
    public void setTopK(Integer topK) { this.topK = topK; }
    public DocumentRetrievalMode getRetrievalMode() { return retrievalMode; }
    public void setRetrievalMode(DocumentRetrievalMode retrievalMode) { this.retrievalMode = retrievalMode; }
    public String getMaterialType() { return materialType; }
    public void setMaterialType(String materialType) { this.materialType = materialType; }
    public String getRetrievalProfile() { return retrievalProfile; }
    public void setRetrievalProfile(String retrievalProfile) { this.retrievalProfile = retrievalProfile; }
    public List<String> getRetrievalChannels() { return retrievalChannels; }
    public void setRetrievalChannels(List<String> retrievalChannels) { this.retrievalChannels = retrievalChannels; }
    public Boolean getRerankEnabled() { return rerankEnabled; }
    public void setRerankEnabled(Boolean rerankEnabled) { this.rerankEnabled = rerankEnabled; }
    public Integer getPage() { return page; }
    public void setPage(Integer page) { this.page = page; }
    public Integer getSize() { return size; }
    public void setSize(Integer size) { this.size = size; }
    public Integer getKeywordK() { return keywordK; }
    public void setKeywordK(Integer keywordK) { this.keywordK = keywordK; }
    public Integer getVectorK() { return vectorK; }
    public void setVectorK(Integer vectorK) { this.vectorK = vectorK; }
    public Integer getRrfK() { return rrfK; }
    public void setRrfK(Integer rrfK) { this.rrfK = rrfK; }
    public Integer getNumCandidates() { return numCandidates; }
    public void setNumCandidates(Integer numCandidates) { this.numCandidates = numCandidates; }
}
