package com.dylan.agent.api.plan;

import java.math.BigDecimal;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Min;

/** 文档检索选项。 */
@Schema(description = "文档检索选项")
public class DocumentRetrievalOptions {

    @Schema(description = "证据条数上限", nullable = true)
    @Min(1)
    private Integer topK;

    @Schema(description = "检索模式，默认 KEYWORD", nullable = true)
    private DocumentRetrievalMode retrievalMode;

    @Schema(description = "关键词召回权重，0 到 1", nullable = true)
    @DecimalMin("0.0")
    @DecimalMax("1.0")
    private BigDecimal keywordWeight;

    @Schema(description = "向量召回权重，0 到 1", nullable = true)
    @DecimalMin("0.0")
    @DecimalMax("1.0")
    private BigDecimal vectorWeight;

    @Schema(description = "最小相关度分数", nullable = true)
    private BigDecimal minScore;

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
    public BigDecimal getKeywordWeight() { return keywordWeight; }
    public void setKeywordWeight(BigDecimal keywordWeight) { this.keywordWeight = keywordWeight; }
    public BigDecimal getVectorWeight() { return vectorWeight; }
    public void setVectorWeight(BigDecimal vectorWeight) { this.vectorWeight = vectorWeight; }
    public BigDecimal getMinScore() { return minScore; }
    public void setMinScore(BigDecimal minScore) { this.minScore = minScore; }
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
