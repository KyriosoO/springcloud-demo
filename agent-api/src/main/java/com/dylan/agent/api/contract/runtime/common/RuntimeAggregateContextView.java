package com.dylan.agent.api.contract.runtime.common;

import com.fasterxml.jackson.annotation.JsonTypeName;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AggregateMetricSpec;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * AGGREGATE Context 的只读最小投影。
 */
@Schema(description = "AGGREGATE context 投影")
@JsonTypeName("AGGREGATE")
public final class RuntimeAggregateContextView implements RuntimeContextView {

    @Schema(description = "固定 discriminator", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = "AGGREGATE")
    @NotNull
    private final RuntimeContextType contextType = RuntimeContextType.AGGREGATE;

    @Schema(description = "来源 Invocation 标识", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String sourceInvocationId;

    @Schema(description = "上轮聚合过滤条件", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private List<@Valid AgentFilter> filters = Collections.emptyList();

    @Schema(description = "上轮聚合指标", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    @Size(min = 1)
    private List<@Valid AggregateMetricSpec> metrics = Collections.emptyList();

    @Schema(description = "上轮分组字段", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private List<String> groupByFields = Collections.emptyList();

    @Schema(description = "上轮 maxRows", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Min(1)
    private Integer maxRows;

    public RuntimeAggregateContextView() {
    }

    @Override
    public RuntimeContextType getContextType() { return contextType; }

    @Override
    public String getSourceInvocationId() { return sourceInvocationId; }
    public void setSourceInvocationId(String sourceInvocationId) { this.sourceInvocationId = sourceInvocationId; }
    public List<AgentFilter> getFilters() { return filters == null ? Collections.emptyList() : Collections.unmodifiableList(filters); }
    public void setFilters(List<AgentFilter> filters) { this.filters = filters == null ? null : new ArrayList<>(filters); }
    public List<AggregateMetricSpec> getMetrics() { return metrics == null ? Collections.emptyList() : Collections.unmodifiableList(metrics); }
    public void setMetrics(List<AggregateMetricSpec> metrics) { this.metrics = metrics == null ? null : new ArrayList<>(metrics); }
    public List<String> getGroupByFields() { return groupByFields == null ? Collections.emptyList() : Collections.unmodifiableList(groupByFields); }
    public void setGroupByFields(List<String> groupByFields) { this.groupByFields = groupByFields == null ? null : new ArrayList<>(groupByFields); }
    public Integer getMaxRows() { return maxRows; }
    public void setMaxRows(Integer maxRows) { this.maxRows = maxRows; }
}
