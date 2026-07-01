package com.dylan.agent.api.contract.runtime.route;

import com.dylan.agent.api.contract.runtime.common.RuntimeCapabilityRoutingDescriptor;
import com.dylan.agent.api.contract.runtime.common.AgentRuntimeContract;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainRoutingProjection;
import com.dylan.agent.api.contract.runtime.common.RuntimeProfileBehaviorProjection;
import com.dylan.agent.api.contract.runtime.common.RuntimeTurnProjection;
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
 * Route 阶段请求。
 *
 * <p>不包含：Context View、完整 Domain Schema、Plan schema、Authorization Snapshot、JWT、Handler/Adapter。
 * 用户消息在入库前已经规范化（trim ≤8000），此处不做二次截断。
 */
@Schema(description = "Route 请求")
public class RouteRequest {

    @Schema(description = "不透明请求标识", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    @Size(min = 1, max = 128)
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

    @Schema(description = "Profile 行为投影", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private RuntimeProfileBehaviorProjection profileBehavior;

    @Schema(description = "当前可用 capability 投影，非空，capabilityId 唯一", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Size(min = 1)
    private List<@Valid RuntimeCapabilityRoutingDescriptor> capabilities = Collections.emptyList();

    @Schema(description = "Route 阶段 domain 投影，domain 唯一", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private List<@Valid RuntimeDomainRoutingProjection> domains = Collections.emptyList();

    @Schema(description = "绝对 deadline（ISO-8601）", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private Instant absoluteDeadline;

    @Schema(description = "repair 上限 [0,3]，部署策略可进一步收紧", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Min(0)
    @Max(3)
    private Integer repairLimit;

    public RouteRequest() {
    }

    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }
    public String getContractVersion() { return contractVersion; }
    public void setContractVersion(String contractVersion) { this.contractVersion = contractVersion; }
    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
    public List<RuntimeTurnProjection> getHistory() { return history == null ? Collections.emptyList() : Collections.unmodifiableList(history); }
    public void setHistory(List<RuntimeTurnProjection> history) { this.history = history == null ? null : new ArrayList<>(history); }
    public RuntimeProfileBehaviorProjection getProfileBehavior() { return profileBehavior; }
    public void setProfileBehavior(RuntimeProfileBehaviorProjection profileBehavior) { this.profileBehavior = profileBehavior; }
    public List<RuntimeCapabilityRoutingDescriptor> getCapabilities() { return capabilities == null ? Collections.emptyList() : Collections.unmodifiableList(capabilities); }
    public void setCapabilities(List<RuntimeCapabilityRoutingDescriptor> capabilities) { this.capabilities = capabilities == null ? null : new ArrayList<>(capabilities); }
    public List<RuntimeDomainRoutingProjection> getDomains() { return domains == null ? Collections.emptyList() : Collections.unmodifiableList(domains); }
    public void setDomains(List<RuntimeDomainRoutingProjection> domains) { this.domains = domains == null ? null : new ArrayList<>(domains); }
    public Instant getAbsoluteDeadline() { return absoluteDeadline; }
    public void setAbsoluteDeadline(Instant absoluteDeadline) { this.absoluteDeadline = absoluteDeadline; }
    public Integer getRepairLimit() { return repairLimit; }
    public void setRepairLimit(Integer repairLimit) { this.repairLimit = repairLimit; }
}
