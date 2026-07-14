package com.dylan.agent.api.contract.runtime.common;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import com.dylan.agent.api.plan.AgentFilter;
import com.fasterxml.jackson.annotation.JsonTypeName;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/** DOCUMENT Context 的只读最小投影。 */
@Schema(description = "DOCUMENT context 投影")
@JsonTypeName("DOCUMENT")
public final class RuntimeDocumentContextView implements RuntimeContextView {

    @Schema(description = "固定 discriminator", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = "DOCUMENT")
    @NotNull
    private final RuntimeContextType contextType = RuntimeContextType.DOCUMENT;

    @Schema(description = "来源 Invocation 标识", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String sourceInvocationId;

    @Schema(description = "上轮文档操作", nullable = true)
    private String operation;

    @Schema(description = "上轮文档 domain", nullable = true)
    private String domain;

    @Schema(description = "上轮文档 materialType", nullable = true)
    private String materialType;

    @Schema(description = "上轮文档查询文本", nullable = true)
    private String queryText;

    @Schema(description = "上轮文档过滤条件", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private List<@Valid AgentFilter> filters = Collections.emptyList();

    @Schema(description = "上轮 topK", nullable = true)
    @Min(1)
    private Integer topK;

    @Schema(description = "上轮摘要范围安全视图", nullable = true)
    private String summaryScope;

    public RuntimeDocumentContextView() {
    }

    @Override
    public RuntimeContextType getContextType() { return contextType; }
    @Override
    public String getSourceInvocationId() { return sourceInvocationId; }
    public void setSourceInvocationId(String sourceInvocationId) { this.sourceInvocationId = sourceInvocationId; }
    public String getOperation() { return operation; }
    public void setOperation(String operation) { this.operation = operation; }
    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }
    public String getMaterialType() { return materialType; }
    public void setMaterialType(String materialType) { this.materialType = materialType; }
    public String getQueryText() { return queryText; }
    public void setQueryText(String queryText) { this.queryText = queryText; }
    public List<AgentFilter> getFilters() { return filters == null ? Collections.emptyList() : Collections.unmodifiableList(filters); }
    public void setFilters(List<AgentFilter> filters) { this.filters = filters == null ? null : new ArrayList<>(filters); }
    public Integer getTopK() { return topK; }
    public void setTopK(Integer topK) { this.topK = topK; }
    public String getSummaryScope() { return summaryScope; }
    public void setSummaryScope(String summaryScope) { this.summaryScope = summaryScope; }
}
