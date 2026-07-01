package com.dylan.agent.api.plan;

import java.util.List;

import com.dylan.agent.api.enums.QueryContextMode;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;

/** QUERY 计划的查询规格，描述过滤条件、返回字段和分页参数。 */
@Schema(description = "QUERY 计划的查询规格，描述过滤条件、返回字段和分页参数")
public class AgentQuerySpec {

    @Schema(description = "过滤条件列表", nullable = true)
    @Size(max = 5)
    private List<AgentFilter> filters;

    @Schema(description = "查询上下文模式（REPLACE/MERGE）", nullable = true)
    private QueryContextMode contextMode;

    @Schema(description = "待移除的字段列表（MERGE 模式使用）", nullable = true)
    @Size(max = 5)
    private List<String> removeFields;

    @Schema(description = "指定返回字段列表，最多 10 个", nullable = true)
    @Size(max = 10)
    private List<String> selectFields;

    @Schema(description = "分页页码，从 1 开始")
    @Min(1)
    private Integer page;

    @Schema(description = "每页大小，1~100")
    @Min(1)
    private Integer size;

    public AgentQuerySpec() {
    }

    public List<AgentFilter> getFilters() { return filters; }
    public void setFilters(List<AgentFilter> filters) { this.filters = filters; }
    public QueryContextMode getContextMode() { return contextMode; }
    public void setContextMode(QueryContextMode contextMode) { this.contextMode = contextMode; }
    public List<String> getRemoveFields() { return removeFields; }
    public void setRemoveFields(List<String> removeFields) { this.removeFields = removeFields; }
    public List<String> getSelectFields() { return selectFields; }
    public void setSelectFields(List<String> selectFields) { this.selectFields = selectFields; }
    public Integer getPage() { return page; }
    public void setPage(Integer page) { this.page = page; }
    public Integer getSize() { return size; }
    public void setSize(Integer size) { this.size = size; }
}
