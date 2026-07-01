package com.dylan.agent.planning.filter;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView.DomainView;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView.FieldView;

/**
 * 对已校验 filter 的字段级约束校验。
 *
 * <p>确保 filter 字段与 removeFields 互斥、最终 filter 集合范围一致性
 * （DECIMAL/INSTANT 字段 GT < LT）、操作符族重叠规则。
 */
@Component
public class FieldConstraintValidator {

    /** 校验变更集中的 filter 字段不与 removeFields 冲突（互斥）。 */
    public void validateChanges(
            List<ValidatedFilter> changes,
            Set<String> removeFields) {
        Map<String, FieldFilterSet> byField = groupByField(changes);
        Set<String> changeFields = byField.keySet();
        for (String field : changeFields) {
            if (removeFields.contains(field)) {
                throw new AgentPlanValidationException(
                        "字段 " + field + " 不能同时出现在 filters 和 removeFields。");
            }
        }
    }

    /** 校验最终 filter 集合的范围一致性（DECIMAL/INSTANT 的 GT < LT）和操作符族重叠规则。 */
    public void validateFinalQuery(
            List<ValidatedFilter> filters,
            DomainView domain) {
        if (filters.isEmpty()) {
            throw new AgentPlanValidationException("MERGE 后查询条件不能为空。");
        }
        Map<String, FieldFilterSet> byField = groupByField(filters);
        for (var entry : byField.entrySet()) {
            String field = entry.getKey();
            FieldFilterSet set = entry.getValue();
            if (set.lowerBound() != null && set.upperBound() != null) {
                FieldView fp = domain.requireField(field);
                validateRange(field, set, fp);
            }
        }
    }

    Map<String, FieldFilterSet> groupByField(List<ValidatedFilter> filters) {
        Map<String, FieldFilterSet> result = new LinkedHashMap<>();
        for (ValidatedFilter filter : filters) {
            OperatorSemantics.Profile profile = OperatorSemantics.profileOf(filter.getOperator());
            String field = filter.getField();
            FieldFilterSet set = result.computeIfAbsent(field, k -> new FieldFilterSet());

            switch (profile.slot()) {
                case ATOMIC -> {
                    if (set.hasAtomic()) {
                        String existingOp = set.atomic().getOperator().name();
                        throw new AgentPlanValidationException(
                                "字段 " + field + " 在同一查询中存在多个普通条件：" + existingOp + ", " + filter.getOperator() + "。");
                    }
                    if (set.hasRange()) {
                        throw new AgentPlanValidationException(
                                "字段 " + field + " 的普通条件不能与 GT/LT 范围条件同时存在。");
                    }
                    set.setAtomic(filter);
                }
                case LOWER_BOUND -> {
                    if (set.hasAtomic()) {
                        throw new AgentPlanValidationException(
                                "字段 " + field + " 的普通条件不能与 GT/LT 范围条件同时存在。");
                    }
                    if (set.lowerBound() != null) {
                        throw new AgentPlanValidationException(
                                "字段 " + field + " 在同一查询中存在重复的 GT 下界。");
                    }
                    set.setLowerBound(filter);
                }
                case UPPER_BOUND -> {
                    if (set.hasAtomic()) {
                        throw new AgentPlanValidationException(
                                "字段 " + field + " 的普通条件不能与 GT/LT 范围条件同时存在。");
                    }
                    if (set.upperBound() != null) {
                        throw new AgentPlanValidationException(
                                "字段 " + field + " 在同一查询中存在重复的 LT 上界。");
                    }
                    set.setUpperBound(filter);
                }
            }
        }
        return result;
    }

    private void validateRange(String field, FieldFilterSet set, FieldView fp) {
        String lowerValue = set.lowerBound().getValue();
        String upperValue = set.upperBound().getValue();

        int comparison = switch (fp.type()) {
            case DECIMAL -> new BigDecimal(lowerValue).compareTo(new BigDecimal(upperValue));
            case INSTANT -> Instant.parse(lowerValue).compareTo(Instant.parse(upperValue));
            case STRING -> throw new AgentPlanValidationException(
                    "STRING 字段 " + field + " 不支持范围条件。");
        };

        if (comparison >= 0) {
            throw new AgentPlanValidationException(
                    "字段 " + field + " 的范围无效，GT 下界必须小于 LT 上界。");
        }
    }
}
