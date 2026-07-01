package com.dylan.agent.api.runtime;

import java.util.List;

import com.dylan.agent.api.plan.AgentFilter;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

/** 上轮成功查询的上下文，传递回 Runtime 用于 MERGE 判断。包含来源 turn、domain、filter、selectFields 和分页。 */
@Schema(description = "上轮成功查询的上下文，传递回 Runtime 用于 MERGE 判断")
public class RuntimeQueryContext {

    @Schema(description = "来源 turn ID", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String sourceTurnId;

    @Schema(description = "查询域", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String domain;

    @Schema(description = "上轮过滤条件", nullable = true)
    private List<AgentFilter> filters;

    @Schema(description = "上轮返回字段", nullable = true)
    private List<String> selectFields;

    @Schema(description = "上轮页码")
    @Min(1)
    private int page;

    @Schema(description = "上轮分页大小")
    @Min(1)
    private int size;

    public RuntimeQueryContext() {
    }

    public String getSourceTurnId() { return sourceTurnId; }
    public void setSourceTurnId(String sourceTurnId) { this.sourceTurnId = sourceTurnId; }
    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }
    public List<AgentFilter> getFilters() { return filters; }
    public void setFilters(List<AgentFilter> filters) { this.filters = filters; }
    public List<String> getSelectFields() { return selectFields; }
    public void setSelectFields(List<String> selectFields) { this.selectFields = selectFields; }
    public int getPage() { return page; }
    public void setPage(int page) { this.page = page; }
    public int getSize() { return size; }
    public void setSize(int size) { this.size = size; }
}
