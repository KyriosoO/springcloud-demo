package com.dylan.agent.api.plan;

import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;

/** 文档总结范围。 */
@Schema(description = "文档总结范围")
public class DocumentSummaryScope {

    @Schema(description = "限定文档 ID 列表", nullable = true)
    @Size(max = 20)
    private List<String> documentIds;

    @Schema(description = "时间范围表达式", nullable = true)
    private String timeRange;

    @Schema(description = "章节提示", nullable = true)
    @Size(max = 10)
    private List<String> sectionHints;

    @Schema(description = "最大摘要字符数", nullable = true)
    @Min(1)
    private Integer maxSummaryChars;

    public List<String> getDocumentIds() { return documentIds; }
    public void setDocumentIds(List<String> documentIds) { this.documentIds = documentIds; }
    public String getTimeRange() { return timeRange; }
    public void setTimeRange(String timeRange) { this.timeRange = timeRange; }
    public List<String> getSectionHints() { return sectionHints; }
    public void setSectionHints(List<String> sectionHints) { this.sectionHints = sectionHints; }
    public Integer getMaxSummaryChars() { return maxSummaryChars; }
    public void setMaxSummaryChars(Integer maxSummaryChars) { this.maxSummaryChars = maxSummaryChars; }
}
