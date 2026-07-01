package com.dylan.agent.api.contract.runtime.error;

import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/**
 * Runtime 统一错误响应。
 *
 * <p>不包含：provider 原始响应、Prompt、栈、凭据、Context、权限表达式、retryAfter。
 */
@Schema(description = "Runtime 错误响应")
public class RuntimeErrorResponse {

    @Schema(description = "请求标识（可空：仅请求解析后可得）")
    private String requestId;

    @Schema(description = "错误码", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private RuntimeErrorCode code;

    @Schema(description = "安全固定摘要", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String message;

    @Schema(description = "操作元数据", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private RuntimeOperationMetadata metadata;

    @Schema(description = "不透明诊断标识", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String diagnosticId;

    public RuntimeErrorResponse() {
    }

    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }
    public RuntimeErrorCode getCode() { return code; }
    public void setCode(RuntimeErrorCode code) { this.code = code; }
    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
    public RuntimeOperationMetadata getMetadata() { return metadata; }
    public void setMetadata(RuntimeOperationMetadata metadata) { this.metadata = metadata; }
    public String getDiagnosticId() { return diagnosticId; }
    public void setDiagnosticId(String diagnosticId) { this.diagnosticId = diagnosticId; }
}
