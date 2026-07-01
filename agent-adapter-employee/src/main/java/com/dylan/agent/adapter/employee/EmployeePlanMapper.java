package com.dylan.agent.adapter.employee;

import java.util.ArrayList;
import java.util.List;

import org.springframework.stereotype.Component;

import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.esquery.api.model.SearchAggregate;
import com.dylan.esquery.api.model.SearchFilter;
import com.dylan.esquery.api.model.SearchMetric;
import com.dylan.esquery.api.model.SearchMetricFunction;
import com.dylan.esquery.api.model.SearchRequest;
import com.dylan.esquery.api.model.SearchSort;
import com.dylan.esquery.api.model.SearchSortDirection;

/**
 * 将 ValidatedFilter 映射为下游 EmployeeSearch API 所需的 filter 参数结构。
 * 负责 operator 枚举转换（如 EQ 到 "equals"）以及固定排序规则的注入。
 */
@Component
public class EmployeePlanMapper {

    /** 将 ValidatedFilter 列表映射为下游 EmployeeSearch API 的请求参数。 */
    public SearchRequest toSearchRequest(ValidatedQuery query) {
        SearchRequest req = new SearchRequest();
        req.setFrom((query.getPage() - 1) * query.getSize());
        req.setSize(query.getSize());
        req.setFilters(toFilters(query.getFilters()));
        req.setKeyword(null);
        req.setAggregate(null);
        List<SearchSort> fixedSorts = new ArrayList<>();
        SearchSort sort1 = new SearchSort();
        sort1.setField("memberNo");
        sort1.setDirection(SearchSortDirection.ASC);
        fixedSorts.add(sort1);
        SearchSort sort2 = new SearchSort();
        sort2.setField("idCardNo");
        sort2.setDirection(SearchSortDirection.ASC);
        fixedSorts.add(sort2);
        req.setSorts(fixedSorts);
        return req;
    }

    /** 将聚合查询映射为下游 EmployeeSearch API 的 aggregate 请求。 */
    public SearchRequest toAggregateSearchRequest(ValidatedAggregateQuery query) {
        SearchRequest req = new SearchRequest();
        req.setFrom(0);
        req.setSize(0);
        req.setFilters(toFilters(query.getFilters()));
        req.setKeyword(null);
        req.setSorts(null);

        SearchAggregate aggregate = new SearchAggregate();
        aggregate.setGroupBy(query.getGroupByFields());
        aggregate.setBucketSize(query.getMaxRows());
        aggregate.setMetrics(query.getMetrics().stream()
                .map(this::toMetric)
                .toList());
        req.setAggregate(aggregate);
        return req;
    }

    List<SearchFilter> toFilters(List<ValidatedFilter> validated) {
        List<SearchFilter> result = new ArrayList<>();
        for (ValidatedFilter vf : validated) {
            SearchFilter sf = new SearchFilter();
            sf.setField(vf.getField());
            sf.setOperator(toEmployeeOperator(vf.getOperator()));
            sf.setValue(vf.getValue());
            sf.setValues(vf.getValues().isEmpty() ? null : vf.getValues());
            result.add(sf);
        }
        return result;
    }

    private SearchMetric toMetric(ValidatedAggregateMetric metric) {
        SearchMetric sm = new SearchMetric();
        sm.setAlias(metric.getAlias());
        sm.setField(metric.getField());
        sm.setFunction(SearchMetricFunction.valueOf(metric.getFunction().name()));
        return sm;
    }

    private String toEmployeeOperator(AgentOperator operator) {
        return switch (operator) {
            case EQ -> "equals";
            case CONTAINS -> "contains";
            case CONTAINS_ANY -> "containsAny";
            case STARTS_WITH -> "startsWith";
            case STARTS_WITH_ANY -> "startsWithAny";
            case IN -> "in";
            case GT, LT -> throw new com.dylan.agent.adapter.api.AgentAdapterException(
                    "Employee 域不支持 operator: " + operator);
        };
    }
}
