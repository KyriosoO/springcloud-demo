package com.dylan.agent.api.plan;

import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

/** DOCUMENT 计划的文档检索、问答和总结规格。 */
@Schema(description = "DOCUMENT 计划的文档检索、问答和总结规格")
public class AgentDocumentSpec {

    @Schema(description = "文档操作类型", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private DocumentPlanOperation operation;

    @Schema(description = "用户查询或总结目标", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    @Size(max = 500)
    private String queryText;

    @Schema(description = "文档过滤条件", nullable = true)
    @Size(max = 10)
    @Valid
    private List<@Valid AgentFilter> filters;

    @Schema(description = "文档排序条件", nullable = true)
    @Size(max = 3)
    @Valid
    private List<@Valid AgentSortSpec> sorts;

    @Schema(description = "检索选项", nullable = true)
    @Valid
    private DocumentRetrievalOptions retrievalOptions;

    @Schema(description = "总结范围；SUMMARIZE 操作必填", nullable = true)
    @Valid
    private DocumentSummaryScope summaryScope;

    @Schema(description = "是否要求引用；ANSWER/SUMMARIZE 固定为 true", nullable = true)
    private Boolean citationRequired;

    public DocumentPlanOperation getOperation() { return operation; }
    public void setOperation(DocumentPlanOperation operation) { this.operation = operation; }
    public String getQueryText() { return queryText; }
    public void setQueryText(String queryText) { this.queryText = queryText; }
    public List<AgentFilter> getFilters() { return filters; }
    public void setFilters(List<AgentFilter> filters) { this.filters = filters; }
    public List<AgentSortSpec> getSorts() { return sorts; }
    public void setSorts(List<AgentSortSpec> sorts) { this.sorts = sorts; }
    public DocumentRetrievalOptions getRetrievalOptions() { return retrievalOptions; }
    public void setRetrievalOptions(DocumentRetrievalOptions retrievalOptions) { this.retrievalOptions = retrievalOptions; }
    public DocumentSummaryScope getSummaryScope() { return summaryScope; }
    public void setSummaryScope(DocumentSummaryScope summaryScope) { this.summaryScope = summaryScope; }
    public Boolean getCitationRequired() { return citationRequired; }
    public void setCitationRequired(Boolean citationRequired) { this.citationRequired = citationRequired; }
}
