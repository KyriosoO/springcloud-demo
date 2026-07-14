package com.dylan.agent.kernel.port.model;

import com.dylan.agent.adapter.api.AdapterRole;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/** Validator 可使用的 domain metadata projection。 */
public final class ExecutionValidationProjection {

    private static final ExecutionValidationProjection NONE =
            new ExecutionValidationProjection(null, null, Map.of(), List.of(), Set.of(), "NO_DOMAIN");

    private final Optional<AdapterRole> adapterRole;
    private final Optional<String> domain;
    private final Map<String, ExecutionFieldRule> fieldRules;
    private final List<String> defaultSelectFields;
    private final Set<String> sortFields;
    private final String projectionVersion;

    public ExecutionValidationProjection(AdapterRole adapterRole,
                                         String domain,
                                         Map<String, ExecutionFieldRule> fieldRules,
                                         List<String> defaultSelectFields,
                                         Set<String> sortFields,
                                         String projectionVersion) {
        if ((adapterRole == null) != (domain == null)) {
            throw new IllegalArgumentException("adapterRole and domain must appear together");
        }
        this.adapterRole = Optional.ofNullable(adapterRole);
        this.domain = Optional.ofNullable(domain).map(value -> requireNonBlank(value, "domain"));
        this.fieldRules = copyFieldRules(fieldRules);
        this.defaultSelectFields = copyDefaultSelectFields(defaultSelectFields);
        this.sortFields = copySortFields(sortFields, this.fieldRules);
        this.projectionVersion = requireNonBlank(projectionVersion, "projectionVersion");
    }

    public ExecutionValidationProjection(AdapterRole adapterRole,
                                         String domain,
                                         Map<String, ExecutionFieldRule> fieldRules,
                                         List<String> defaultSelectFields,
                                         String projectionVersion) {
        this(adapterRole, domain, fieldRules, defaultSelectFields, Set.of(),
                projectionVersion);
    }

    public static ExecutionValidationProjection none() {
        return NONE;
    }

    public Optional<AdapterRole> adapterRole() { return adapterRole; }
    public Optional<String> domain() { return domain; }
    public Map<String, ExecutionFieldRule> fieldRules() { return fieldRules; }
    public List<String> defaultSelectFields() { return defaultSelectFields; }
    public Set<String> sortFields() { return sortFields; }
    public String projectionVersion() { return projectionVersion; }

    private static Map<String, ExecutionFieldRule> copyFieldRules(Map<String, ExecutionFieldRule> source) {
        if (source == null || source.isEmpty()) {
            return Map.of();
        }
        Map<String, ExecutionFieldRule> copy = new LinkedHashMap<>();
        source.forEach((key, rule) -> {
            String normalizedKey = requireNonBlank(key, "fieldRules key");
            ExecutionFieldRule nonNullRule = Objects.requireNonNull(rule, "field rule must not be null");
            if (!normalizedKey.equals(nonNullRule.field())) {
                throw new IllegalArgumentException("fieldRules key must match rule.field");
            }
            copy.put(normalizedKey, nonNullRule);
        });
        return Map.copyOf(copy);
    }

    private static List<String> copyDefaultSelectFields(List<String> source) {
        if (source == null || source.isEmpty()) {
            return List.of();
        }
        return source.stream()
                .map(value -> requireNonBlank(value, "defaultSelectFields element"))
                .collect(Collectors.toUnmodifiableList());
    }

    private static Set<String> copySortFields(Set<String> source, Map<String, ExecutionFieldRule> fieldRules) {
        if (source == null || source.isEmpty()) {
            return Set.of();
        }
        Set<String> normalized = source.stream()
                .map(value -> requireNonBlank(value, "sortFields element"))
                .collect(Collectors.toUnmodifiableSet());
        if (!fieldRules.keySet().containsAll(normalized)) {
            throw new IllegalArgumentException("sortFields must be fieldRules subset");
        }
        return normalized;
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
