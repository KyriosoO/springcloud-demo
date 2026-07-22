package com.dylan.baseline.agent.security.authorization;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/** 仅用于Auth字段权威迁移对比的旧字段视图。 */
public record LegacyAuthFieldView(
        Map<String, Set<String>> filterableFields,
        Map<String, Set<String>> displayableFields,
        Map<String, Set<String>> allowedOperators,
        Map<String, Set<String>> allowedFunctions) {

    public LegacyAuthFieldView {
        filterableFields = immutableMap(filterableFields, "filterableFields");
        displayableFields = immutableMap(displayableFields, "displayableFields");
        allowedOperators = immutableMap(allowedOperators, "allowedOperators");
        allowedFunctions = immutableMap(allowedFunctions, "allowedFunctions");
    }

    public static LegacyAuthFieldView empty() {
        return new LegacyAuthFieldView(Map.of(), Map.of(), Map.of(), Map.of());
    }

    public LegacyAuthFieldView intersect(LegacyAuthFieldView other) {
        return new LegacyAuthFieldView(
                intersectMap(filterableFields, other.filterableFields),
                intersectMap(displayableFields, other.displayableFields),
                intersectMap(allowedOperators, other.allowedOperators),
                intersectMap(allowedFunctions, other.allowedFunctions));
    }

    public LegacyAuthFieldView union(LegacyAuthFieldView other) {
        return new LegacyAuthFieldView(
                unionMap(filterableFields, other.filterableFields),
                unionMap(displayableFields, other.displayableFields),
                unionMap(allowedOperators, other.allowedOperators),
                unionMap(allowedFunctions, other.allowedFunctions));
    }

    public boolean isSubsetOf(LegacyAuthFieldView other) {
        return mapIsSubset(filterableFields, other.filterableFields)
                && mapIsSubset(displayableFields, other.displayableFields)
                && mapIsSubset(allowedOperators, other.allowedOperators)
                && mapIsSubset(allowedFunctions, other.allowedFunctions);
    }

    private static boolean mapIsSubset(Map<String, Set<String>> left, Map<String, Set<String>> right) {
        return left.entrySet().stream().allMatch(entry ->
                right.getOrDefault(entry.getKey(), Set.of()).containsAll(entry.getValue()));
    }

    private static Map<String, Set<String>> intersectMap(
            Map<String, Set<String>> left,
            Map<String, Set<String>> right) {
        Map<String, Set<String>> result = new LinkedHashMap<>();
        left.forEach((key, values) -> {
            Set<String> intersection = new TreeSet<>(values);
            intersection.retainAll(right.getOrDefault(key, Set.of()));
            if (!intersection.isEmpty()) {
                result.put(key, intersection);
            }
        });
        return result;
    }

    private static Map<String, Set<String>> unionMap(
            Map<String, Set<String>> left,
            Map<String, Set<String>> right) {
        Map<String, Set<String>> result = mutableCopy(left);
        right.forEach((key, values) -> result.computeIfAbsent(key, ignored -> new TreeSet<>()).addAll(values));
        return result;
    }

    private static Map<String, Set<String>> immutableMap(Map<String, Set<String>> values, String name) {
        if (values == null) {
            throw new IllegalArgumentException(name + " must not be null");
        }
        Map<String, Set<String>> result = new TreeMap<>();
        values.forEach((key, entries) -> {
            if (key == null || key.isBlank() || entries == null
                    || entries.stream().anyMatch(value -> value == null || value.isBlank())) {
                throw new IllegalArgumentException(name + " contains an invalid entry");
            }
            result.put(key, Set.copyOf(new TreeSet<>(entries)));
        });
        return Map.copyOf(result);
    }

    private static Map<String, Set<String>> mutableCopy(Map<String, Set<String>> values) {
        Map<String, Set<String>> result = new TreeMap<>();
        values.forEach((key, entries) -> result.put(key, new TreeSet<>(entries)));
        return result;
    }
}
