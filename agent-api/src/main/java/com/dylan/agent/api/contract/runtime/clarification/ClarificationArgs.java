package com.dylan.agent.api.contract.runtime.clarification;

import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;
import io.swagger.v3.oas.annotations.media.DiscriminatorMapping;
import io.swagger.v3.oas.annotations.media.Schema;

/**
 * ClarificationArgs sealed union。
 * 每个 reasonCode 只绑定一个合法 args subtype。
 */
@Schema(
    description = "ClarificationArgs 联合类型",
    oneOf = {CapabilityChoiceArgs.class, DomainChoiceArgs.class, FieldChoiceArgs.class,
            FieldForbiddenArgs.class, ValueChoiceArgs.class},
    discriminatorProperty = "argType",
    discriminatorMapping = {
        @DiscriminatorMapping(value = "CAPABILITY_CHOICES", schema = CapabilityChoiceArgs.class),
        @DiscriminatorMapping(value = "DOMAIN_CHOICES", schema = DomainChoiceArgs.class),
        @DiscriminatorMapping(value = "FIELD_CHOICES", schema = FieldChoiceArgs.class),
        @DiscriminatorMapping(value = "FIELD_FORBIDDEN", schema = FieldForbiddenArgs.class),
        @DiscriminatorMapping(value = "VALUE_CHOICES", schema = ValueChoiceArgs.class)
    }
)
@JsonTypeInfo(use = JsonTypeInfo.Id.NAME, include = JsonTypeInfo.As.EXISTING_PROPERTY, property = "argType", visible = true)
@JsonSubTypes({
    @JsonSubTypes.Type(value = CapabilityChoiceArgs.class, name = "CAPABILITY_CHOICES"),
    @JsonSubTypes.Type(value = DomainChoiceArgs.class, name = "DOMAIN_CHOICES"),
    @JsonSubTypes.Type(value = FieldChoiceArgs.class, name = "FIELD_CHOICES"),
    @JsonSubTypes.Type(value = FieldForbiddenArgs.class, name = "FIELD_FORBIDDEN"),
    @JsonSubTypes.Type(value = ValueChoiceArgs.class, name = "VALUE_CHOICES")
})
public sealed interface ClarificationArgs
    permits CapabilityChoiceArgs, DomainChoiceArgs, FieldChoiceArgs, FieldForbiddenArgs, ValueChoiceArgs {

    /** 返回 args discriminator。 */
    ClarificationArgType getArgType();
}
