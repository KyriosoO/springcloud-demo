package com.dylan.agent.planning.filter;

import java.util.Map;
import java.util.Set;

import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;

/**
 * 操作符-类型兼容性与 filter 形态约束的单一事实来源。
 * 定义操作符族（多值 vs 单值 vs 无值）、每种字段类型允许的操作符、
 * 以及每个操作符族是 atomic 还是 range。
 *
 * <p>由 {@link FieldConstraintValidator} 和 {@link FilterNormalizer} 使用。
 */
public final class OperatorSemantics {

    public enum OperatorFamily {
        EXACT,
        TEXT,
        RANGE
    }

    public enum FilterSlot {
        ATOMIC,
        LOWER_BOUND,
        UPPER_BOUND
    }

    public enum ValueShape {
        SINGLE,
        MULTI
    }

    public record Profile(
            OperatorFamily family,
            FilterSlot slot,
            ValueShape valueShape,
            Set<AgentFieldType> supportedTypes) {
    }

    private static final Map<AgentOperator, Profile> PROFILES = Map.of(
            AgentOperator.EQ,
            new Profile(
                    OperatorFamily.EXACT,
                    FilterSlot.ATOMIC,
                    ValueShape.SINGLE,
                    Set.of(
                            AgentFieldType.STRING,
                            AgentFieldType.DECIMAL,
                            AgentFieldType.INSTANT)),
            AgentOperator.IN,
            new Profile(
                    OperatorFamily.EXACT,
                    FilterSlot.ATOMIC,
                    ValueShape.MULTI,
                    Set.of(
                            AgentFieldType.STRING,
                            AgentFieldType.DECIMAL,
                            AgentFieldType.INSTANT)),
            AgentOperator.CONTAINS,
            new Profile(
                    OperatorFamily.TEXT,
                    FilterSlot.ATOMIC,
                    ValueShape.SINGLE,
                    Set.of(AgentFieldType.STRING)),
            AgentOperator.CONTAINS_ANY,
            new Profile(
                    OperatorFamily.TEXT,
                    FilterSlot.ATOMIC,
                    ValueShape.MULTI,
                    Set.of(AgentFieldType.STRING)),
            AgentOperator.STARTS_WITH,
            new Profile(
                    OperatorFamily.TEXT,
                    FilterSlot.ATOMIC,
                    ValueShape.SINGLE,
                    Set.of(AgentFieldType.STRING)),
            AgentOperator.STARTS_WITH_ANY,
            new Profile(
                    OperatorFamily.TEXT,
                    FilterSlot.ATOMIC,
                    ValueShape.MULTI,
                    Set.of(AgentFieldType.STRING)),
            AgentOperator.GT,
            new Profile(
                    OperatorFamily.RANGE,
                    FilterSlot.LOWER_BOUND,
                    ValueShape.SINGLE,
                    Set.of(
                            AgentFieldType.DECIMAL,
                            AgentFieldType.INSTANT)),
            AgentOperator.LT,
            new Profile(
                    OperatorFamily.RANGE,
                    FilterSlot.UPPER_BOUND,
                    ValueShape.SINGLE,
                    Set.of(
                            AgentFieldType.DECIMAL,
                            AgentFieldType.INSTANT)));

    private OperatorSemantics() {
    }

    /** 返回操作符的 profile（multi-value/single-value/range）。 */
    public static Profile profileOf(AgentOperator operator) {
        Profile profile = PROFILES.get(operator);
        if (profile == null) {
            throw new IllegalArgumentException(
                    "Unsupported AgentOperator: " + operator);
        }
        return profile;
    }

    /** 判断操作符是否与字段类型兼容。 */
    public static boolean supports(
            AgentOperator operator,
            AgentFieldType fieldType) {
        return profileOf(operator).supportedTypes().contains(fieldType);
    }
}
