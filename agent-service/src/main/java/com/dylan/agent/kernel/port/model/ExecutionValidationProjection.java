package com.dylan.agent.kernel.port.model;

import com.dylan.agent.adapter.api.AdapterRole;

import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/** Domain metadata projection available to validators. */
public final class ExecutionValidationProjection {

    private static final ExecutionValidationProjection NONE =
            new ExecutionValidationProjection(null, null, Map.of(), List.of(), 0, 0, "NO_DOMAIN");

    private final Optional<AdapterRole> adapterRole;
    private final Optional<String> domain;
    private final Map<String, ExecutionFieldRule> fieldRules;
    private final List<String> defaultSelectFields;
    private final int maxPageSize;
    private final int maxResultRows;
    private final String projectionVersion;

    public ExecutionValidationProjection(AdapterRole adapterRole,
                                         String domain,
                                         Map<String, ExecutionFieldRule> fieldRules,
                                         List<String> defaultSelectFields,
                                         int maxPageSize,
                                         int maxResultRows,
                                         String projectionVersion) {
        if ((adapterRole == null) != (domain == null)) {
            throw new IllegalArgumentException("adapterRole and domain must appear together");
        }
        this.adapterRole = Optional.ofNullable(adapterRole);
        this.domain = Optional.ofNullable(domain);
        this.fieldRules = Map.copyOf(fieldRules == null ? Map.of() : fieldRules);
        this.defaultSelectFields = List.copyOf(defaultSelectFields == null ? List.of() : defaultSelectFields);
        this.maxPageSize = maxPageSize;
        this.maxResultRows = maxResultRows;
        this.projectionVersion = Objects.requireNonNull(projectionVersion);
    }

    public static ExecutionValidationProjection none() {
        return NONE;
    }

    public Optional<AdapterRole> adapterRole() { return adapterRole; }
    public Optional<String> domain() { return domain; }
    public Map<String, ExecutionFieldRule> fieldRules() { return fieldRules; }
    public List<String> defaultSelectFields() { return defaultSelectFields; }
    public int maxPageSize() { return maxPageSize; }
    public int maxResultRows() { return maxResultRows; }
    public String projectionVersion() { return projectionVersion; }
}
