package com.dylan.agent.adapter.employee;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.List;

import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.plan.AggregateOrderSpec;
import com.fasterxml.jackson.databind.ObjectMapper;

@DisplayName("EmployeeSearchResponseParser")
class EmployeeSearchResponseParserTest {

    private final ObjectMapper mapper = new ObjectMapper();
    private final EmployeeSearchResponseParser parser = new EmployeeSearchResponseParser(mapper);

    @Nested
    @DisplayName("正常解析")
    class SuccessfulParsing {

        @Test
        @DisplayName("正常 hits 解析成功")
        void shouldParseNormalHits() {
            String body = """
                {"hits":{"total":{"value":2,"relation":"eq"},"hits":[{"_source":{"chineseName":"张三","memberNo":"E001"}},{"_source":{"chineseName":"李四","memberNo":"E002"}}]}}
                """;
            AdapterQueryResult result = parser.parse(body, 1, 20, 2097152);
            assertThat(result.getRows()).hasSize(2);
            assertThat(result.getTotal()).isEqualTo(2);
            assertThat(result.getRows().get(0).get("chineseName")).isEqualTo("张三");
        }

        @Test
        @DisplayName("total 对象形式兼容")
        void shouldHandleTotalObject() {
            String body = """
                {"hits":{"total":{"value":5,"relation":"eq"},"hits":[]}}
                """;
            AdapterQueryResult result = parser.parse(body, 1, 20, 2097152);
            assertThat(result.getTotal()).isEqualTo(5);
        }

        @Test
        @DisplayName("total 数字形式兼容")
        void shouldHandleTotalNumber() {
            String body = """
                {"hits":{"total":3,"hits":[]}}
                """;
            AdapterQueryResult result = parser.parse(body, 1, 20, 2097152);
            assertThat(result.getTotal()).isEqualTo(3);
        }

        @Test
        @DisplayName("聚合 buckets 展平成功")
        void shouldParseAggregateBuckets() {
            String body = """
                {"aggregations":{"group_by_0_position":{"buckets":[{"key":"HRM","doc_count":2,"employeeCount":{"value":2}},{"key":"DEV","doc_count":1,"employeeCount":{"value":1}}]}}}
                """;
            AggregateOrderSpec order = new AggregateOrderSpec();
            order.setField("employeeCount");
            order.setDirection("DESC");
            var result = parser.parseAggregate(body, new ValidatedAggregateQuery(
                    List.of(),
                    List.of(new ValidatedAggregateMetric("employeeCount", AggregateFunction.COUNT, null)),
                    List.of("position"),
                    List.of(order),
                    20), 2097152);

            assertThat(result.getRows()).hasSize(2);
            assertThat(result.getRows().get(0)).containsEntry("position", "HRM");
            assertThat(result.getRows().get(0)).containsEntry("employeeCount", 2L);
            assertThat(result.isPartial()).isFalse();
        }
    }

    @Nested
    @DisplayName("拒绝场景")
    class RejectionScenarios {

        @Test
        @DisplayName("total relation 为 gte 时作为下界返回")
        void shouldAcceptGteRelationAsLowerBound() {
            String body = """
                {"hits":{"total":{"value":10000,"relation":"gte"},"hits":[]}}
                """;
            AdapterQueryResult result = parser.parse(body, 1, 20, 2097152);
            assertThat(result.getTotal()).isEqualTo(10000);
            assertThat(result.isTotalExact()).isFalse();
        }

        @Test
        @DisplayName("缺少 hits 报错")
        void shouldRejectMissingHits() {
            String body = "{}";
            assertThatThrownBy(() -> parser.parse(body, 1, 20, 2097152))
                    .isInstanceOf(AgentAdapterException.class)
                    .hasMessageContaining("hits");
        }

        @Test
        @DisplayName("null body 报错")
        void shouldRejectNullBody() {
            assertThatThrownBy(() -> parser.parse(null, 1, 20, 2097152))
                    .isInstanceOf(AgentAdapterException.class);
        }

        @Test
        @DisplayName("响应超限拒绝")
        void shouldRejectOversizedResponse() {
            String body = "a".repeat(100);
            assertThatThrownBy(() -> parser.parse(body, 1, 20, 1))
                    .isInstanceOf(AgentAdapterException.class)
                    .hasMessageContaining("大小");
        }

        @Test
        @DisplayName("非法的 JSON 拒绝")
        void shouldRejectInvalidJson() {
            assertThatThrownBy(() -> parser.parse("not json", 1, 20, 2097152))
                    .isInstanceOf(AgentAdapterException.class);
        }

        @Test
        @DisplayName("返回行数超出请求 size 拒绝")
        void shouldRejectRowCountExceedingSize() {
            String body = """
                {"hits":{"total":{"value":3,"relation":"eq"},"hits":[{"_source":{"a":"1"}},{"_source":{"a":"2"}},{"_source":{"a":"3"}},{"_source":{"a":"4"}}]}}
                """;
            assertThatThrownBy(() -> parser.parse(body, 1, 2, 2097152))
                    .isInstanceOf(AgentAdapterException.class)
                    .hasMessageContaining("行数");
        }
    }

    @Nested
    @DisplayName("ES 元数据过滤")
    class EsMetadataFilter {

        @Test
        @DisplayName("不返回 _score 等 ES 元数据")
        void shouldExcludeEsMetadata() {
            String body = """
                {"hits":{"total":{"value":1,"relation":"eq"},"hits":[{"_score":1.5,"_source":{"chineseName":"张三"}}]}}
                """;
            AdapterQueryResult result = parser.parse(body, 1, 20, 2097152);
            assertThat(result.getRows().get(0)).doesNotContainKey("_score");
            assertThat(result.getRows().get(0)).containsKey("chineseName");
        }
    }
}
