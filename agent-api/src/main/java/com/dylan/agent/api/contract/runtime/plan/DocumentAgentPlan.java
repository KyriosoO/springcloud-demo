package com.dylan.agent.api.contract.runtime.plan;

import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.plan.AgentDocumentSpec;
import com.fasterxml.jackson.annotation.JsonTypeName;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;

/** DOCUMENT 结构化计划。 */
@Schema(description = "DOCUMENT Plan 子类型")
@JsonTypeName("DOCUMENT")
public non-sealed class DocumentAgentPlan implements AgentPlan {

    @Schema(description = "固定 discriminator", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = "DOCUMENT")
    @NotNull
    private final AgentPlanKind planKind = AgentPlanKind.DOCUMENT;

    @Schema(description = "文档规格", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private AgentDocumentSpec document;

    public DocumentAgentPlan() {
    }

    @Override
    public AgentPlanKind getPlanKind() { return planKind; }

    public AgentDocumentSpec getDocument() { return document; }
    public void setDocument(AgentDocumentSpec document) { this.document = document; }
}
