package com.dylan.agent.api.contract.runtime.clarification;

import com.fasterxml.jackson.annotation.JsonTypeName;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import com.dylan.agent.api.contract.runtime.common.RuntimeOutcomeType;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import com.dylan.agent.api.contract.runtime.plan.PlanOutcome;
import com.dylan.agent.api.contract.runtime.route.RouteOutcome;
import jakarta.validation.constraints.NotNull;

/**
 * Route/Plan 双阶段共用的 ClarificationRequired variant。
 *
 * <p>同时实现 RouteOutcome 和 PlanOutcome。不包含 question 字段 ——
 * 最终 question 由 Java Planning Service 在 D03 使用安全模板生成。
 *
 * <p>禁止字段：question、freeTextReason、chainOfThought、Prompt、未授权候选。
 */
@Schema(description = "澄清请求")
@JsonTypeName("CLARIFICATION")
public final class ClarificationRequired implements RouteOutcome, PlanOutcome {

    // 固定 discriminator
    @Schema(description = "固定 discriminator", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = "CLARIFICATION")
    @NotNull
    private final RuntimeOutcomeType outcomeType = RuntimeOutcomeType.CLARIFICATION;

    @Schema(description = "请求关联标识", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String requestId;

    @Schema(description = "澄清原因码", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private ClarificationReasonCode reasonCode;

    @Schema(description = "类型化澄清参数", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private ClarificationArgs args;

    @Schema(description = "操作元数据", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private RuntimeOperationMetadata metadata;

    public ClarificationRequired() {
    }

    // ── 公共 getters (no setters for final fields) ──
    // Note: outcomeType is final, no setter needed; Jackson reads the immutable value.
    // For JSON round-trip, planKind==false, we need all fields to have setters.
    // However ClarificationRequired is recognized by discriminator outcomeType=CLARIFICATION,
    // which is always final. We provide getter only.

    public RuntimeOutcomeType getOutcomeType() { return outcomeType; }

    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }

    public ClarificationReasonCode getReasonCode() { return reasonCode; }
    public void setReasonCode(ClarificationReasonCode reasonCode) { this.reasonCode = reasonCode; }

    public ClarificationArgs getArgs() { return args; }
    public void setArgs(ClarificationArgs args) { this.args = args; }

    public RuntimeOperationMetadata getMetadata() { return metadata; }
    public void setMetadata(RuntimeOperationMetadata metadata) { this.metadata = metadata; }
}
