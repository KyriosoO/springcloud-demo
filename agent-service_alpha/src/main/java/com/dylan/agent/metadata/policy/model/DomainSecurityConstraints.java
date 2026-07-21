package com.dylan.agent.metadata.policy.model;

import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.model.MaskType;

import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/** Policy 拥有的静态 field security constraints；field/operator/function facts 归 D04 拥有。 */
public record DomainSecurityConstraints(
        Set<CapabilityOperationType> externalProcessingPurposes,
        Map<CanonicalFieldRef, FieldSecurityConstraint> fields) {
    public DomainSecurityConstraints {
        externalProcessingPurposes = Set.copyOf(Objects.requireNonNull(
                externalProcessingPurposes, "externalProcessingPurposes must not be null"));
        fields = Map.copyOf(Objects.requireNonNull(fields, "fields must not be null"));
    }

    public record FieldSecurityConstraint(
            boolean filterAllowed,
            boolean displayAllowed,
            Set<AgentOperator> allowedOperators,
            Set<String> allowedFunctions,
            Optional<MaskType> requiredMask,
            SecurityClassificationRef classification,
            Set<CapabilityOperationType> externalProcessingPurposes) {
        public FieldSecurityConstraint {
            allowedOperators = Set.copyOf(Objects.requireNonNull(allowedOperators, "allowedOperators must not be null"));
            allowedFunctions = copyNonBlankSet(allowedFunctions, "allowedFunctions");
            requiredMask = Objects.requireNonNull(requiredMask, "requiredMask must not be null");
            classification = Objects.requireNonNull(classification, "classification must not be null");
            externalProcessingPurposes = Set.copyOf(Objects.requireNonNull(
                    externalProcessingPurposes, "externalProcessingPurposes must not be null"));
        }

        private static Set<String> copyNonBlankSet(Set<String> source, String name) {
            Objects.requireNonNull(source, name + " must not be null");
            return source.stream()
                    .map(value -> {
                        Objects.requireNonNull(value, name + " element must not be null");
                        String normalized = value.trim();
                        if (normalized.isEmpty()) {
                            throw new IllegalArgumentException(name + " element must not be blank");
                        }
                        return normalized;
                    })
                    .collect(Collectors.toUnmodifiableSet());
        }
    }
}
