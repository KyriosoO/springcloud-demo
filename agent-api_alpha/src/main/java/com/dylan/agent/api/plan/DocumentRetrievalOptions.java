package com.dylan.agent.api.plan;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Min;

/** 文档检索选项。 */
@Schema(description = "文档检索选项")
public class DocumentRetrievalOptions {

    @Schema(description = "证据条数上限", nullable = true)
    @Min(1)
    private Integer topK;

    @Schema(description = "资料类型，例如 policy、notice、faq", nullable = true)
    private String materialType;

    @Schema(description = "页码，从 1 开始", nullable = true)
    @Min(1)
    private Integer page;

    @Schema(description = "每页大小", nullable = true)
    @Min(1)
    private Integer size;

    public Integer getTopK() { return topK; }
    public void setTopK(Integer topK) { this.topK = topK; }
    public String getMaterialType() { return materialType; }
    public void setMaterialType(String materialType) { this.materialType = materialType; }
    public Integer getPage() { return page; }
    public void setPage(Integer page) { this.page = page; }
    public Integer getSize() { return size; }
    public void setSize(Integer size) { this.size = size; }
}
