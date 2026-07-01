package com.dylan.agent.metadata.authorization.model;

import java.util.*;

/**
 * Execution 阶段与当前的权限交集范围。
 */
public final class ExecutionScope {

    private final String subjectRef;
    private final Set<String> allowedCapabilityIds;
    private final Set<String> allowedDomains;
    private final Map<String, Set<String>> allowedFields;
    private final Map<String, String> fieldMasks; // field -> mask type

    public ExecutionScope(
            String subjectRef,
            Set<String> allowedCapabilityIds, Set<String> allowedDomains,
            Map<String, Set<String>> allowedFields, Map<String, String> fieldMasks) {
        this.subjectRef = Objects.requireNonNull(subjectRef);
        this.allowedCapabilityIds = Set.copyOf(allowedCapabilityIds);
        this.allowedDomains = Set.copyOf(allowedDomains);
        this.allowedFields = Map.copyOf(allowedFields);
        this.fieldMasks = Map.copyOf(fieldMasks);
    }

    public String subjectRef() { return subjectRef; }
    public Set<String> allowedCapabilityIds() { return allowedCapabilityIds; }
    public Set<String> allowedDomains() { return allowedDomains; }
    public Map<String, Set<String>> allowedFields() { return allowedFields; }
    public Map<String, String> fieldMasks() { return fieldMasks; }
}
