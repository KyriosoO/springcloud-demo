package com.dylan.agent.api.contract.runtime.clarification;

import io.swagger.v3.oas.annotations.media.Schema;

/** ClarificationArgs sealed union 的 discriminator 值。 */
@Schema(description = "ClarificationArgs 子类型")
public enum ClarificationArgType {

    @Schema(description = "capability 候选列表")
    CAPABILITY_CHOICES,

    @Schema(description = "domain 候选列表")
    DOMAIN_CHOICES,

    @Schema(description = "字段候选列表")
    FIELD_CHOICES,

    @Schema(description = "字段禁止访问")
    FIELD_FORBIDDEN,

    @Schema(description = "值候选列表")
    VALUE_CHOICES
}
