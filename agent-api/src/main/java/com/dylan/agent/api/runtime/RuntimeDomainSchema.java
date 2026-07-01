package com.dylan.agent.api.runtime;

import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

/** 发送给 Runtime 的域 schema 定义，包含域别名、字段列表、默认展示字段和分页/过滤上限。 */
@Schema(description = "域 schema 定义，包含字段列表、默认展示字段和分页/过滤上限")
public class RuntimeDomainSchema {

    @Schema(description = "域标识", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String domain;

    @Schema(description = "域别名列表", nullable = true)
    private List<String> aliases;

    @Schema(description = "字段 schema 列表", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotEmpty
    private List<RuntimeFieldSchema> fields;

    @Schema(description = "默认展示字段", nullable = true)
    private List<String> defaultSelectFields;

    @Schema(description = "最大过滤条件数")
    private int maxFilters;

    @Schema(description = "默认分页大小")
    private int defaultSize;

    @Schema(description = "最大分页大小")
    private int maxSize;

    @Schema(description = "最大结果窗口")
    private int maxResultWindow;

    public RuntimeDomainSchema() {
    }

    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }
    public List<String> getAliases() { return aliases; }
    public void setAliases(List<String> aliases) { this.aliases = aliases; }
    public List<RuntimeFieldSchema> getFields() { return fields; }
    public void setFields(List<RuntimeFieldSchema> fields) { this.fields = fields; }
    public List<String> getDefaultSelectFields() { return defaultSelectFields; }
    public void setDefaultSelectFields(List<String> defaultSelectFields) { this.defaultSelectFields = defaultSelectFields; }
    public int getMaxFilters() { return maxFilters; }
    public void setMaxFilters(int maxFilters) { this.maxFilters = maxFilters; }
    public int getDefaultSize() { return defaultSize; }
    public void setDefaultSize(int defaultSize) { this.defaultSize = defaultSize; }
    public int getMaxSize() { return maxSize; }
    public void setMaxSize(int maxSize) { this.maxSize = maxSize; }
    public int getMaxResultWindow() { return maxResultWindow; }
    public void setMaxResultWindow(int maxResultWindow) { this.maxResultWindow = maxResultWindow; }
}
