package com.dylan.agent.api.capability;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

/** Capability 输入/输出契约引用，使用逻辑 schema 名，不强绑定 Java class 名。 */
@Schema(description = "Capability 输入/输出契约引用")
public class CapabilityContractRef {

    @Schema(description = "契约逻辑名，例如 AgentPlan.query、AgentPlan.aggregate、ClarifySpec、AgentQueryResult、AgentAggregateResult", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String schema;

    @Schema(description = "契约版本号", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String version;

    public CapabilityContractRef() {
    }

    public String getSchema() { return schema; }
    public void setSchema(String schema) { this.schema = schema; }
    public String getVersion() { return version; }
    public void setVersion(String version) { this.version = version; }
}
