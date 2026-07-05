package com.dylan.agent.api.contract.runtime.common;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Plan 阶段的单体 domain schema 安全投影。
 *
 * <p>只包含当前授权可见的字段，不包含 mask、数据库列名、Adapter 实现或完整 Catalog。
 */
@Schema(description = "Domain Schema 投影")
public class RuntimeDomainSchema {

    @Schema(description = "domain 标识", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String domain;

    @Schema(description = "字段列表，field 唯一", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private List<@Valid RuntimeDomainFieldSchema> fields = Collections.emptyList();

    @Schema(description = "默认展示字段", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private List<String> defaultSelectFields = Collections.emptyList();

    @Schema(description = "当前授权可用于 QUERY 排序的字段", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private List<String> sortFields = Collections.emptyList();

    @Schema(description = "默认 page size")
    @Min(1)
    private Integer defaultSize;

    @Schema(description = "最大 page size")
    @Min(1)
    private Integer maxSize;

    public RuntimeDomainSchema() {
    }

    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }
    public List<RuntimeDomainFieldSchema> getFields() { return fields == null ? Collections.emptyList() : Collections.unmodifiableList(fields); }
    public void setFields(List<RuntimeDomainFieldSchema> fields) { this.fields = fields == null ? null : new ArrayList<>(fields); }
    public List<String> getDefaultSelectFields() { return defaultSelectFields == null ? Collections.emptyList() : Collections.unmodifiableList(defaultSelectFields); }
    public void setDefaultSelectFields(List<String> defaultSelectFields) { this.defaultSelectFields = defaultSelectFields == null ? null : new ArrayList<>(defaultSelectFields); }
    public List<String> getSortFields() { return sortFields == null ? Collections.emptyList() : Collections.unmodifiableList(sortFields); }
    public void setSortFields(List<String> sortFields) { this.sortFields = sortFields == null ? null : new ArrayList<>(sortFields); }
    public Integer getDefaultSize() { return defaultSize; }
    public void setDefaultSize(Integer defaultSize) { this.defaultSize = defaultSize; }
    public Integer getMaxSize() { return maxSize; }
    public void setMaxSize(Integer maxSize) { this.maxSize = maxSize; }
}
