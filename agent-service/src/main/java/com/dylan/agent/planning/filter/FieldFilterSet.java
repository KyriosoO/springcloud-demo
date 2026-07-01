package com.dylan.agent.planning.filter;

import java.util.ArrayList;
import java.util.List;

import com.dylan.agent.adapter.api.query.ValidatedFilter;

/**
 * 包级私有辅助类，跟踪 MERGE 操作中单个字段的 atomic/range 状态。
 * 设置 atomic 时清空 range（lowerBound/upperBound = null），反之亦然。
 */
final class FieldFilterSet {

    private ValidatedFilter atomic;
    private ValidatedFilter lowerBound;
    private ValidatedFilter upperBound;

    ValidatedFilter atomic() { return atomic; }
    ValidatedFilter lowerBound() { return lowerBound; }
    ValidatedFilter upperBound() { return upperBound; }

    boolean isEmpty() { return atomic == null && lowerBound == null && upperBound == null; }
    boolean hasAtomic() { return atomic != null; }
    boolean hasRange() { return lowerBound != null || upperBound != null; }

    void setAtomic(ValidatedFilter filter) {
        this.atomic = filter;
        this.lowerBound = null;
        this.upperBound = null;
    }

    void setLowerBound(ValidatedFilter filter) { this.lowerBound = filter; }
    void setUpperBound(ValidatedFilter filter) { this.upperBound = filter; }

    void clear() {
        this.atomic = null;
        this.lowerBound = null;
        this.upperBound = null;
    }

    void clearAtomic() { this.atomic = null; }
    void clearRange() {
        this.lowerBound = null;
        this.upperBound = null;
    }

    FieldFilterSet copy() {
        FieldFilterSet c = new FieldFilterSet();
        c.atomic = this.atomic;
        c.lowerBound = this.lowerBound;
        c.upperBound = this.upperBound;
        return c;
    }

    List<ValidatedFilter> flatten() {
        if (atomic != null) {
            return List.of(atomic);
        }
        List<ValidatedFilter> result = new ArrayList<>(2);
        if (lowerBound != null) {
            result.add(lowerBound);
        }
        if (upperBound != null) {
            result.add(upperBound);
        }
        return List.copyOf(result);
    }
}
