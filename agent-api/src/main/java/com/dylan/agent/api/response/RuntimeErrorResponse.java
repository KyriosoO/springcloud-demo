package com.dylan.agent.api.response;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

/** Runtime 错误响应，包含错误码、消息和可选的 requestId。 */
@Schema(description = "Runtime 错误响应")
public class RuntimeErrorResponse {

    @Schema(description = "错误码", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String code;

    @Schema(description = "错误消息", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String message;

    @Schema(description = "关联的请求 ID", nullable = true)
    private String requestId;

    public RuntimeErrorResponse() {
    }

    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }
    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }
}
