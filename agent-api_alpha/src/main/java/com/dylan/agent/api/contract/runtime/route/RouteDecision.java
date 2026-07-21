package com.dylan.agent.api.contract.runtime.route;

import com.fasterxml.jackson.annotation.JsonTypeName;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import com.dylan.agent.api.contract.runtime.common.RuntimeOutcomeType;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/**
 * Route 阶段的候选选择。
 *
 * <p>只选择 capabilityId 和候选 domain，不携带 planKind、AgentPlan、权限表达式或自由推理文本。
 */
@Schema(description = "Route 决策")
@JsonTypeName("DECISION")
public final class RouteDecision implements RouteOutcome {

    @Schema(description = "固定 discriminator", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = "DECISION")
    @NotNull
    private final RuntimeOutcomeType outcomeType = RuntimeOutcomeType.DECISION;

    @Schema(description = "请求关联标识", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String requestId;

    @Schema(description = "选定的 capabilityId", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String capabilityId;

    @Schema(description = "候选 domain，NONE/OPTIONAL 时可空")
    private String domain;

    @Schema(description = "操作元数据", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private RuntimeOperationMetadata metadata;

    public RouteDecision() {
    }

    @Override
    public RuntimeOutcomeType getOutcomeType() { return outcomeType; }

    @Override
    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }

    public String getCapabilityId() { return capabilityId; }
    public void setCapabilityId(String capabilityId) { this.capabilityId = capabilityId; }

    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }

    @Override
    public RuntimeOperationMetadata getMetadata() { return metadata; }
    public void setMetadata(RuntimeOperationMetadata metadata) { this.metadata = metadata; }
}
