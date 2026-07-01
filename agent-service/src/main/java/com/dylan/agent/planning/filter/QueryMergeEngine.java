package com.dylan.agent.planning.filter;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.query.ValidatedFilter;

/**
 * QUERY MERGE 操作的确定性合并引擎。
 * 接收上一轮已校验 filter 集合和本轮变更集（filters + removeFields），
 * 产出最终合并 filter 列表。替换语义：传入 atomic 替换该字段全部历史条件；
 * 传入 range 替换全部历史范围；removeFields 完全移除该字段。
 */
@Component
public class QueryMergeEngine {

    private final FieldConstraintValidator constraintValidator;

    public QueryMergeEngine(FieldConstraintValidator constraintValidator) {
        this.constraintValidator = constraintValidator;
    }

    /** 确定性合并：传入 atomic 替换该字段全部历史条件，传入 range 替换全部历史范围，removeFields 完全移除该字段。 */
    public List<ValidatedFilter> merge(
            List<ValidatedFilter> previous,
            List<ValidatedFilter> changes,
            Set<String> removeFields) {

        Map<String, FieldFilterSet> result = deepCopy(
                constraintValidator.groupByField(previous));

        for (String field : removeFields) {
            result.remove(field);
        }

        Map<String, FieldFilterSet> changedByField =
                constraintValidator.groupByField(changes);

        for (var entry : changedByField.entrySet()) {
            String field = entry.getKey();
            FieldFilterSet incoming = entry.getValue();
            FieldFilterSet existing = result.get(field);

            if (incoming.hasAtomic()) {
                FieldFilterSet replacement = new FieldFilterSet();
                replacement.setAtomic(incoming.atomic());
                result.put(field, replacement);
                continue;
            }

            FieldFilterSet target;
            if (existing == null || existing.hasAtomic()) {
                target = new FieldFilterSet();
            } else {
                target = existing.copy();
            }

            if (incoming.lowerBound() != null) {
                target.setLowerBound(incoming.lowerBound());
            }
            if (incoming.upperBound() != null) {
                target.setUpperBound(incoming.upperBound());
            }
            result.put(field, target);
        }

        return flatten(result);
    }

    private Map<String, FieldFilterSet> deepCopy(Map<String, FieldFilterSet> source) {
        Map<String, FieldFilterSet> copy = new LinkedHashMap<>();
        for (var entry : source.entrySet()) {
            copy.put(entry.getKey(), entry.getValue().copy());
        }
        return copy;
    }

    private List<ValidatedFilter> flatten(Map<String, FieldFilterSet> map) {
        List<ValidatedFilter> result = new ArrayList<>();
        for (FieldFilterSet set : map.values()) {
            result.addAll(set.flatten());
        }
        return List.copyOf(result);
    }
}
