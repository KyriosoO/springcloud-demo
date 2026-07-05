package com.dylan.agent.api.contract.runtime.common;

import com.fasterxml.jackson.annotation.JsonTypeName;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AgentSortSpec;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * QUERY Context 的只读最小投影。
 *
 * <p>不包含 domain —— domain 由 PlanRequest 独立提供。sourceInvocationId 标识来源。
 */
@Schema(description = "QUERY context 投影")
@JsonTypeName("QUERY")
public final class RuntimeQueryContextView implements RuntimeContextView {

    @Schema(description = "固定 discriminator", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = "QUERY")
    @NotNull
    private final RuntimeContextType contextType = RuntimeContextType.QUERY;

    @Schema(description = "来源 Invocation 标识", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String sourceInvocationId;

    @Schema(description = "上轮查询过滤条件", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private List<@Valid AgentFilter> filters = Collections.emptyList();

    @Schema(description = "上轮查询展示字段", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private List<String> selectFields = Collections.emptyList();

    @Schema(description = "上轮查询排序条件", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private List<@Valid AgentSortSpec> sorts = Collections.emptyList();

    @Schema(description = "上轮 page", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Min(1)
    private Integer page;

    @Schema(description = "上轮 size", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Min(1)
    private Integer size;

    @Schema(description = "上轮查询总数；仅 totalExact=true 时可用于精确分页", nullable = true)
    @Min(0)
    private Long total;

    @Schema(description = "上轮查询总数是否精确", nullable = true)
    private Boolean totalExact;

    @Schema(description = "上轮查询总页数；仅 totalExact=true 时可用于末页计算", nullable = true)
    @Min(1)
    private Integer totalPages;

    public RuntimeQueryContextView() {
    }

    @Override
    public RuntimeContextType getContextType() { return contextType; }

    @Override
    public String getSourceInvocationId() { return sourceInvocationId; }
    public void setSourceInvocationId(String sourceInvocationId) { this.sourceInvocationId = sourceInvocationId; }
    public List<AgentFilter> getFilters() { return filters == null ? Collections.emptyList() : Collections.unmodifiableList(filters); }
    public void setFilters(List<AgentFilter> filters) { this.filters = filters == null ? null : new ArrayList<>(filters); }
    public List<String> getSelectFields() { return selectFields == null ? Collections.emptyList() : Collections.unmodifiableList(selectFields); }
    public void setSelectFields(List<String> selectFields) { this.selectFields = selectFields == null ? null : new ArrayList<>(selectFields); }
    public List<AgentSortSpec> getSorts() { return sorts == null ? Collections.emptyList() : Collections.unmodifiableList(sorts); }
    public void setSorts(List<AgentSortSpec> sorts) { this.sorts = sorts == null ? null : new ArrayList<>(sorts); }
    public Integer getPage() { return page; }
    public void setPage(Integer page) { this.page = page; }
    public Integer getSize() { return size; }
    public void setSize(Integer size) { this.size = size; }
    public Long getTotal() { return total; }
    public void setTotal(Long total) { this.total = total; }
    public Boolean getTotalExact() { return totalExact; }
    public void setTotalExact(Boolean totalExact) { this.totalExact = totalExact; }
    public Integer getTotalPages() { return totalPages; }
    public void setTotalPages(Integer totalPages) { this.totalPages = totalPages; }
}
