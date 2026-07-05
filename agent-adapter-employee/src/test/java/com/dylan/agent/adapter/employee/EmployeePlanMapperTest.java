package com.dylan.agent.adapter.employee;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.adapter.api.query.ValidatedSort;
import com.dylan.esquery.api.model.SearchRequest;
import com.dylan.esquery.api.model.SearchSortDirection;

@DisplayName("EmployeePlanMapper")
class EmployeePlanMapperTest {

    private final EmployeePlanMapper mapper = new EmployeePlanMapper();

    @Nested
    @DisplayName("分页映射")
    class PageMapping {

        @Test
        @DisplayName("page 1 size 20 -> from 0")
        void shouldMapPage1ToFrom0() {
            var q = buildQuery(1, 20);
            SearchRequest req = mapper.toSearchRequest(q);
            assertThat(req.getFrom()).isEqualTo(0);
            assertThat(req.getSize()).isEqualTo(20);
        }

        @Test
        @DisplayName("page 3 size 50 -> from 100")
        void shouldMapPage3ToFrom100() {
            var q = buildQuery(3, 50);
            SearchRequest req = mapper.toSearchRequest(q);
            assertThat(req.getFrom()).isEqualTo(100);
        }
    }

    @Nested
    @DisplayName("Operator 映射")
    class OperatorMapping {

        @Test
        @DisplayName("EQ -> equals")
        void shouldMapEq() {
            ValidatedFilter f = new ValidatedFilter("position", AgentOperator.EQ, "HRM", List.of());
            var q = new ValidatedQuery(List.of(f), List.of("chineseName"), 1, 20);
            SearchRequest req = mapper.toSearchRequest(q);
            assertThat(req.getFilters().get(0).getOperator()).isEqualTo("equals");
        }

        @Test
        @DisplayName("CONTAINS -> contains")
        void shouldMapContains() {
            ValidatedFilter f = new ValidatedFilter("chineseName", AgentOperator.CONTAINS, "张", List.of());
            var q = new ValidatedQuery(List.of(f), List.of("chineseName"), 1, 20);
            SearchRequest req = mapper.toSearchRequest(q);
            assertThat(req.getFilters().get(0).getOperator()).isEqualTo("contains");
        }

        @Test
        @DisplayName("STARTS_WITH -> startsWith")
        void shouldMapStartsWith() {
            ValidatedFilter f = new ValidatedFilter("chineseName", AgentOperator.STARTS_WITH, "张", List.of());
            var q = new ValidatedQuery(List.of(f), List.of("chineseName"), 1, 20);
            SearchRequest req = mapper.toSearchRequest(q);
            assertThat(req.getFilters().get(0).getOperator()).isEqualTo("startsWith");
        }

        @Test
        @DisplayName("IN -> in")
        void shouldMapIn() {
            ValidatedFilter f = new ValidatedFilter("memberNo", AgentOperator.IN, null, List.of("E001", "E002"));
            var q = new ValidatedQuery(List.of(f), List.of("chineseName"), 1, 20);
            SearchRequest req = mapper.toSearchRequest(q);
            assertThat(req.getFilters().get(0).getOperator()).isEqualTo("in");
            assertThat(req.getFilters().get(0).getValues()).containsExactly("E001", "E002");
        }
    }

    @Nested
    @DisplayName("固定字段")
    class FixedFields {

        @Test
        @DisplayName("keyword 为空")
        void shouldSetKeywordNull() {
            var q = buildQuery(1, 20);
            SearchRequest req = mapper.toSearchRequest(q);
            assertThat(req.getKeyword()).isNull();
        }

        @Test
        @DisplayName("aggregate 为空")
        void shouldSetAggregateNull() {
            var q = buildQuery(1, 20);
            SearchRequest req = mapper.toSearchRequest(q);
            assertThat(req.getAggregate()).isNull();
        }

        @Test
        @DisplayName("sort 固定为 memberNo ASC, idCardNo ASC")
        void shouldSetFixedSort() {
            var q = buildQuery(1, 20);
            SearchRequest req = mapper.toSearchRequest(q);
            assertThat(req.getSorts()).hasSize(2);
            assertThat(req.getSorts().get(0).getField()).isEqualTo("memberNo");
            assertThat(req.getSorts().get(0).getDirection()).isEqualTo(SearchSortDirection.ASC);
            assertThat(req.getSorts().get(1).getField()).isEqualTo("idCardNo");
            assertThat(req.getSorts().get(1).getDirection()).isEqualTo(SearchSortDirection.ASC);
        }

        @Test
        @DisplayName("映射用户排序并追加 idCardNo 稳定排序")
        void shouldMapValidatedSortsAndAppendTieBreaker() {
            var q = new ValidatedQuery(
                    List.of(new ValidatedFilter("position", AgentOperator.EQ, "HRM", List.of())),
                    List.of("chineseName"),
                    List.of(new ValidatedSort("chineseName", "DESC")),
                    1,
                    20);

            SearchRequest req = mapper.toSearchRequest(q);

            assertThat(req.getSorts()).hasSize(2);
            assertThat(req.getSorts().get(0).getField()).isEqualTo("chineseName");
            assertThat(req.getSorts().get(0).getDirection()).isEqualTo(SearchSortDirection.DESC);
            assertThat(req.getSorts().get(1).getField()).isEqualTo("idCardNo");
            assertThat(req.getSorts().get(1).getDirection()).isEqualTo(SearchSortDirection.ASC);
        }

        @Test
        @DisplayName("聚合请求设置 aggregate 且不设置查询 sort")
        void shouldMapAggregateRequest() {
            var req = mapper.toAggregateSearchRequest(new ValidatedAggregateQuery(
                    List.of(new ValidatedFilter("position", AgentOperator.EQ, "HRM", List.of())),
                    List.of(new ValidatedAggregateMetric("employeeCount", AggregateFunction.COUNT, null)),
                    List.of("position"),
                    List.of(),
                    20));

            assertThat(req.getFrom()).isZero();
            assertThat(req.getSize()).isZero();
            assertThat(req.getSorts()).isNull();
            assertThat(req.getAggregate()).isNotNull();
            assertThat(req.getAggregate().getGroupBy()).containsExactly("position");
            assertThat(req.getAggregate().getMetrics().get(0).getAlias()).isEqualTo("employeeCount");
        }
    }

    private ValidatedQuery buildQuery(int page, int size) {
        ValidatedFilter f = new ValidatedFilter("position", AgentOperator.EQ, "HRM", List.of());
        return new ValidatedQuery(List.of(f), List.of("chineseName", "memberNo", "position"), page, size);
    }
}
