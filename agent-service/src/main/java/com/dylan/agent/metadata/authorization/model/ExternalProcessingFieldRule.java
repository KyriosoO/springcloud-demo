package com.dylan.agent.metadata.authorization.model;

import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.policy.model.SecurityClassificationRef;
import com.dylan.agent.model.MaskType;

import java.util.Objects;
import java.util.Set;

/** Policy 与当前 Permission 求交后的字段外部处理规则。 */
public record ExternalProcessingFieldRule(
        CanonicalFieldRef field,
        SecurityClassificationRef classification,
        MaskType maskType,
        Set<CapabilityOperationType> allowedPurposes) {

    public ExternalProcessingFieldRule {
        Objects.requireNonNull(field, "field must not be null");
        Objects.requireNonNull(classification, "classification must not be null");
        Objects.requireNonNull(maskType, "maskType must not be null");
        allowedPurposes = Set.copyOf(Objects.requireNonNull(allowedPurposes, "allowedPurposes must not be null"));
    }
}
