package com.dylan.agent.planning.filter;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;

/**
 * 将 Runtime 原始 AgentFilter 规范化为验证通过的 ValidatedFilter。
 * 逐操作符校验值形态（单值 vs values 数组），按字段类型校验值格式
 * （DECIMAL 精度/标度, INSTANT ISO-8601 时区, STRING 长度），
 * 去除控制字符，规范化为标准表示。
 */
@Component
public class FilterNormalizer {

    private static final Pattern CONTROL_CHARS = Pattern.compile("[\\x00-\\x1F\\x7F]");
    private static final Pattern WILDCARD_META = Pattern.compile("[*?\\\\]");
    private static final Pattern PLAIN_DECIMAL = Pattern.compile("[+-]?\\d+(?:\\.\\d+)?");

    private final AgentProperties properties;

    public FilterNormalizer(AgentProperties properties) {
        this.properties = properties;
    }

    /** 批量规范化所有 AgentFilter，调用 normalize() 逐个处理。 */
    public List<ValidatedFilter> normalizeAll(
            List<AgentFilter> filters,
            Map<String, ExecutionFieldRule> fieldRules) {
        if (filters == null || filters.isEmpty()) {
            return List.of();
        }
        List<ValidatedFilter> result = new ArrayList<>(filters.size());
        for (AgentFilter filter : filters) {
            result.add(normalize(filter, fieldRules));
        }
        return List.copyOf(result);
    }

    /** 规范化单个 AgentFilter：校验 value/values 形态、按字段类型校验值格式、去除控制字符、规范化 decimal/instant 表示。 */
    public ValidatedFilter normalize(AgentFilter filter, Map<String, ExecutionFieldRule> fieldRules) {
        if (filter == null || filter.getField() == null || filter.getField().isBlank()) {
            throw new AgentPlanValidationException("filter field 为空。");
        }
        if (filter.getOperator() == null) {
            throw new AgentPlanValidationException("filter operator 为空。");
        }

        String field = filter.getField().trim();
        ExecutionFieldRule rule = fieldRules.get(field);
        if (rule == null) {
            throw new AgentPlanValidationException("未知 filter field: " + field);
        }
        if (!rule.allowedOperators().contains(filter.getOperator())) {
            throw new AgentPlanValidationException(
                    "字段 " + field + " 不支持 operator: " + filter.getOperator());
        }
        if (!OperatorSemantics.supports(filter.getOperator(), rule.fieldType())) {
            throw new AgentPlanValidationException(
                    "字段 " + field + " 的 operator " + filter.getOperator()
                    + " 与字段类型 " + rule.fieldType() + " 不兼容。");
        }

        OperatorSemantics.Profile profile = OperatorSemantics.profileOf(filter.getOperator());
        return switch (profile.valueShape()) {
            case SINGLE -> validateSingleValue(field, filter, rule);
            case MULTI -> validateMultiValue(field, filter, rule);
        };
    }

    private ValidatedFilter validateSingleValue(String field, AgentFilter filter, ExecutionFieldRule rule) {
        if (filter.getValues() != null && !filter.getValues().isEmpty()) {
            throw new AgentPlanValidationException(filter.getOperator() + " 不允许 values。");
        }
        String value = normalizeValue(filter.getValue(), rule);
        if (filter.getOperator() == AgentOperator.CONTAINS
                && WILDCARD_META.matcher(value).find()) {
            throw new AgentPlanValidationException("CONTAINS 不允许 ES wildcard 元字符。");
        }
        return new ValidatedFilter(field, filter.getOperator(), value, List.of());
    }

    private ValidatedFilter validateMultiValue(String field, AgentFilter filter, ExecutionFieldRule rule) {
        if (filter.getValue() != null && !filter.getValue().isBlank()) {
            throw new AgentPlanValidationException(filter.getOperator() + " 不允许 value。");
        }
        if (filter.getValues() == null || filter.getValues().isEmpty()) {
            throw new AgentPlanValidationException(filter.getOperator() + " 需要非空 values。");
        }

        Set<String> values = new LinkedHashSet<>();
        for (String rawValue : filter.getValues()) {
            String normalized = normalizeValue(rawValue, rule);
            if (filter.getOperator() == AgentOperator.CONTAINS_ANY
                    && WILDCARD_META.matcher(normalized).find()) {
                throw new AgentPlanValidationException(
                        "CONTAINS_ANY 不允许 ES wildcard 元字符。");
            }
            values.add(normalized);
        }

        if (values.size() > properties.getQuery().getMaxInValues()) {
            throw new AgentPlanValidationException(
                    filter.getOperator() + " values 数量超过上限 "
                    + properties.getQuery().getMaxInValues());
        }

        if (filter.getOperator() == AgentOperator.IN) {
            return new ValidatedFilter(field, AgentOperator.IN, null, new ArrayList<>(values));
        }
        return new ValidatedFilter(field, filter.getOperator(), null, new ArrayList<>(values));
    }

    String normalizeValue(String value, ExecutionFieldRule rule) {
        if (value == null || value.isBlank()) {
            throw new AgentPlanValidationException("filter value 不能为空。");
        }
        String normalized = value.trim();
        if (normalized.length() > properties.getQuery().getMaxFilterValueLength()) {
            throw new AgentPlanValidationException("filter value 超过长度上限。");
        }
        if (CONTROL_CHARS.matcher(normalized).find()) {
            throw new AgentPlanValidationException("filter value 不允许控制字符。");
        }
        return switch (rule.fieldType()) {
            case STRING -> normalized;
            case DECIMAL -> normalizeDecimal(normalized, rule);
            case INSTANT -> normalizeInstant(normalized);
        };
    }

    private String normalizeDecimal(String value, ExecutionFieldRule rule) {
        if (!PLAIN_DECIMAL.matcher(value).matches()) {
            throw new AgentPlanValidationException(
                    "无效的 DECIMAL 值: " + value + "，仅允许普通十进制格式。");
        }
        BigDecimal decimal;
        try {
            decimal = new BigDecimal(value).stripTrailingZeros();
        } catch (NumberFormatException e) {
            throw new AgentPlanValidationException("无效的 DECIMAL 值: " + value);
        }

        Integer precisionLimit = rule.precision().orElse(null);
        Integer scaleLimit = rule.scale().orElse(null);
        if (precisionLimit == null || scaleLimit == null) {
            throw new AgentPlanValidationException("DECIMAL 字段缺少精度配置。");
        }

        int scale = Math.max(decimal.scale(), 0);
        int integerDigits = Math.max(decimal.precision() - decimal.scale(), 0);
        int integerLimit = precisionLimit - scaleLimit;
        if (scale > scaleLimit || integerDigits > integerLimit) {
            throw new AgentPlanValidationException(
                    "DECIMAL 值超出 precision=" + precisionLimit
                    + ", scale=" + scaleLimit + " 的范围。");
        }
        return decimal.signum() == 0 ? "0" : decimal.toPlainString();
    }

    private String normalizeInstant(String value) {
        try {
            OffsetDateTime parsed = OffsetDateTime.parse(
                    value, DateTimeFormatter.ISO_OFFSET_DATE_TIME);
            if (parsed.getNano() != 0) {
                throw new AgentPlanValidationException("INSTANT 不允许小数秒。");
            }
            if (parsed.getOffset().getTotalSeconds() % 60 != 0) {
                throw new AgentPlanValidationException("INSTANT 时区偏移必须精确到分钟。");
            }
            return parsed.toInstant().toString();
        } catch (DateTimeParseException e) {
            throw new AgentPlanValidationException(
                    "无效的 INSTANT 值: " + value + "，需为 ISO-8601 含时区格式");
        }
    }
}
