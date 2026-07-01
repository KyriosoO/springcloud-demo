package com.dylan.agent.api.contract.runtime.plan;

import com.dylan.agent.api.contract.runtime.common.*;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Plan 阶段请求。
 *
 * <p>只包含 Java 已解析 capability/planKind 的最小投影。
 * 不包含：其他 capability descriptor、完整 Context Envelope、Authorization Snapshot、
 * ResultRef payload、Handler/Adapter、最终执行授权。
 */
@Schema(description = "Plan 请求")
public class PlanRequest {

    @Schema(description = "请求关联标识（与 Route 同一次 invocation）", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String requestId;

    @Schema(description = "唯一 contract generation 版本", requiredMode = Schema.RequiredMode.REQUIRED,
        allowableValues = AgentRuntimeContract.VERSION)
    @NotBlank
    private String contractVersion;

    @Schema(description = "用户消息", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    @Size(min = 1, max = 8000)
    private String message;

    @Schema(description = "历史 turn 投影，最多 20 条", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Size(max = 20)
    private List<@Valid RuntimeTurnProjection> history = Collections.emptyList();

    @Schema(description = "Java 已校验的 capabilityId", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String capabilityId;

    @Schema(description = "来自 Resolved Registration 的 planKind", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private AgentPlanKind planKind;

    @Schema(description = "已选 capability 描述符（仅含已选单项）", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private RuntimeCapabilityRoutingDescriptor capability;

    @Schema(description = "输入 schema 引用（JSON Pointer）", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String inputSchemaRef;

    @Schema(description = "已选 domain，NONE 时必为空")
    private String domain;

    @Schema(description = "已选 domain 的 schema 投影，非空时 domain 必须一致")
    @Valid
    private RuntimeDomainSchema domainSchema;

    @Schema(description = "Context View 列表，contextType 唯一", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private List<@Valid RuntimeContextView> contextViews = Collections.emptyList();

    @Schema(description = "绝对 deadline（与 Route 相同且不可延长）", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private Instant absoluteDeadline;

    @Schema(description = "repair 上限 [0,3]", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Min(0)
    @Max(3)
    private Integer repairLimit;

    public PlanRequest() {
    }

    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }
    public String getContractVersion() { return contractVersion; }
    public void setContractVersion(String contractVersion) { this.contractVersion = contractVersion; }
    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
    public List<RuntimeTurnProjection> getHistory() { return history == null ? Collections.emptyList() : Collections.unmodifiableList(history); }
    public void setHistory(List<RuntimeTurnProjection> history) { this.history = history == null ? null : new ArrayList<>(history); }
    public String getCapabilityId() { return capabilityId; }
    public void setCapabilityId(String capabilityId) { this.capabilityId = capabilityId; }
    public AgentPlanKind getPlanKind() { return planKind; }
    public void setPlanKind(AgentPlanKind planKind) { this.planKind = planKind; }
    public RuntimeCapabilityRoutingDescriptor getCapability() { return capability; }
    public void setCapability(RuntimeCapabilityRoutingDescriptor capability) { this.capability = capability; }
    public String getInputSchemaRef() { return inputSchemaRef; }
    public void setInputSchemaRef(String inputSchemaRef) { this.inputSchemaRef = inputSchemaRef; }
    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }
    public RuntimeDomainSchema getDomainSchema() { return domainSchema; }
    public void setDomainSchema(RuntimeDomainSchema domainSchema) { this.domainSchema = domainSchema; }
    public List<RuntimeContextView> getContextViews() { return contextViews == null ? Collections.emptyList() : Collections.unmodifiableList(contextViews); }
    public void setContextViews(List<RuntimeContextView> contextViews) { this.contextViews = contextViews == null ? null : new ArrayList<>(contextViews); }
    public Instant getAbsoluteDeadline() { return absoluteDeadline; }
    public void setAbsoluteDeadline(Instant absoluteDeadline) { this.absoluteDeadline = absoluteDeadline; }
    public Integer getRepairLimit() { return repairLimit; }
    public void setRepairLimit(Integer repairLimit) { this.repairLimit = repairLimit; }
}
