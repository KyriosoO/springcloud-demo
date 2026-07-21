package com.dylan.agent.api.plan;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Min;

/** 文档生成式回答和总结选项。 */
@Schema(description = "文档生成式回答和总结选项")
public class DocumentGenerationOptions {

    @Schema(description = "是否请求生成式回答或总结", nullable = true)
    private Boolean enabled;

    @Schema(description = "最大输出字符数", nullable = true)
    @Min(1)
    private Integer maxOutputChars;

    @Schema(description = "生成失败策略", nullable = true)
    private DocumentGenerationFailurePolicy failurePolicy;

    public Boolean getEnabled() { return enabled; }
    public void setEnabled(Boolean enabled) { this.enabled = enabled; }
    public Integer getMaxOutputChars() { return maxOutputChars; }
    public void setMaxOutputChars(Integer maxOutputChars) { this.maxOutputChars = maxOutputChars; }
    public DocumentGenerationFailurePolicy getFailurePolicy() { return failurePolicy; }
    public void setFailurePolicy(DocumentGenerationFailurePolicy failurePolicy) { this.failurePolicy = failurePolicy; }
}
