package com.dylan.agent.api.plan;

import java.util.List;

import com.dylan.agent.api.enums.AggregateFunction;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

/**
 * AGGREGATE 计划的聚合规格：过滤条件（复用 AgentFilter）、聚合指标、分组字段、排序和全局行数上限。
 */
@Schema(description = "AGGREGATE 计划的聚合规格")
public class AgentAggregateSpec {

    @Schema(description = "预聚合过滤条件列表", nullable = true)
    @Size(max = 5)
    private List<AgentFilter> filters;

    @Schema(description = "聚合指标列表，至少 1 个", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotEmpty
    @Size(max = 5)
    private List<AggregateMetricSpec> metrics;

    @Schema(description = "分组字段列表", nullable = true)
    @Size(max = 2)
    private List<@NotBlank String> groupByFields;

    @Schema(description = "结果排序列表，field 必须来自 groupByFields 或 metric alias", nullable = true)
    private List<AggregateOrderSpec> orderBy;

    @Schema(description = "全局最多返回行数上限", minimum = "1", maximum = "100")
    @Min(1)
    @Max(100)
    private Integer maxRows;

    public AgentAggregateSpec() {
    }

    public List<AgentFilter> getFilters() { return filters; }
    public void setFilters(List<AgentFilter> filters) { this.filters = filters; }
    public List<AggregateMetricSpec> getMetrics() { return metrics; }
    public void setMetrics(List<AggregateMetricSpec> metrics) { this.metrics = metrics; }
    public List<String> getGroupByFields() { return groupByFields; }
    public void setGroupByFields(List<String> groupByFields) { this.groupByFields = groupByFields; }
    public List<AggregateOrderSpec> getOrderBy() { return orderBy; }
    public void setOrderBy(List<AggregateOrderSpec> orderBy) { this.orderBy = orderBy; }
    public Integer getMaxRows() { return maxRows; }
    public void setMaxRows(Integer maxRows) { this.maxRows = maxRows; }
}
