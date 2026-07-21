package com.dylan.agent.adapter.transaction;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.math.BigDecimal;
import java.util.Date;
import java.util.List;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.adapter.api.query.ValidatedSort;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.transaction.api.query.TransactionSearchRequest;

@DisplayName("TransactionPlanMapper")
class TransactionPlanMapperTest {

    private final TransactionPlanMapper mapper = new TransactionPlanMapper();

    @Nested
    @DisplayName("字段映射")
    class FieldMapping {

        @Test
        @DisplayName("transId EQ")
        void shouldMapTransIdEq() {
            TransactionSearchRequest req = mapper.toSearchRequest(
                    buildQuery(singleFilter("transId", AgentOperator.EQ, "T10001", null)));

            assertThat(req.getCondition().getTransId()).isEqualTo("T10001");
            assertThat(req.getPage()).isEqualTo(1);
            assertThat(req.getSize()).isEqualTo(20);
        }

        @Test
        @DisplayName("transType EQ")
        void shouldMapTransTypeEq() {
            TransactionSearchRequest req = mapper.toSearchRequest(
                    buildQuery(singleFilter("transType", AgentOperator.EQ, "PAY", null)));

            assertThat(req.getCondition().getTransType()).isEqualTo("PAY");
        }

        @Test
        @DisplayName("transType CONTAINS")
        void shouldMapTransTypeContains() {
            TransactionSearchRequest req = mapper.toSearchRequest(
                    buildQuery(singleFilter("transType", AgentOperator.CONTAINS, "PAY", null)));

            assertThat(req.getCondition().getTransTypeContains()).isEqualTo("PAY");
        }

        @Test
        @DisplayName("amount EQ")
        void shouldMapAmountEq() {
            TransactionSearchRequest req = mapper.toSearchRequest(
                    buildQuery(singleFilter("amount", AgentOperator.EQ, "100.50", null)));

            assertThat(req.getCondition().getAmount()).isEqualTo(new BigDecimal("100.50"));
        }

        @Test
        @DisplayName("amount GT")
        void shouldMapAmountGt() {
            TransactionSearchRequest req = mapper.toSearchRequest(
                    buildQuery(singleFilter("amount", AgentOperator.GT, "100", null)));

            assertThat(req.getCondition().getAmountGt()).isEqualTo(new BigDecimal("100"));
        }

        @Test
        @DisplayName("amount LT")
        void shouldMapAmountLt() {
            TransactionSearchRequest req = mapper.toSearchRequest(
                    buildQuery(singleFilter("amount", AgentOperator.LT, "1000", null)));

            assertThat(req.getCondition().getAmountLt()).isEqualTo(new BigDecimal("1000"));
        }

        @Test
        @DisplayName("transDate GT")
        void shouldMapTransDateGt() {
            TransactionSearchRequest req = mapper.toSearchRequest(
                    buildQuery(singleFilter("transDate", AgentOperator.GT,
                            "2026-06-21T16:00:00Z", null)));

            assertThat(req.getCondition().getTransDateGt())
                    .isEqualTo(Date.from(java.time.Instant.parse("2026-06-21T16:00:00Z")));
        }

        @Test
        @DisplayName("transDate LT")
        void shouldMapTransDateLt() {
            TransactionSearchRequest req = mapper.toSearchRequest(
                    buildQuery(singleFilter("transDate", AgentOperator.LT,
                            "2026-06-22T00:00:00Z", null)));

            assertThat(req.getCondition().getTransDateLt()).isNotNull();
        }

        @Test
        @DisplayName("聚合请求 metrics 映射")
        void shouldMapAggregateMetrics() {
            var req = mapper.toAggregateRequest(new ValidatedAggregateQuery(
                    List.of(singleFilter("amount", AgentOperator.GT, "100", null).get(0)),
                    List.of(
                            new ValidatedAggregateMetric("totalAmount", AggregateFunction.SUM, "amount"),
                            new ValidatedAggregateMetric("countRecords", AggregateFunction.COUNT, null)),
                    List.of("transType"),
                    List.of(),
                    20));

            assertThat(req.getCondition().getAmountGt()).isEqualTo(new BigDecimal("100"));
            assertThat(req.getGroupBy()).containsExactly("transType");
            assertThat(req.getMetrics()).containsExactly("SUM:amount", "COUNT");
        }

        @Test
        @DisplayName("排序映射到 transaction 请求")
        void shouldMapValidatedSorts() {
            TransactionSearchRequest req = mapper.toSearchRequest(new ValidatedQuery(
                    singleFilter("amount", AgentOperator.GT, "100", null),
                    List.of("transId", "amount"),
                    List.of(new ValidatedSort("amount", "DESC")),
                    1,
                    20));

            assertThat(req.getSorts()).singleElement().satisfies(sort -> {
                assertThat(sort.getField()).isEqualTo("amount");
                assertThat(sort.getDirection()).isEqualTo("DESC");
            });
        }
    }

    @Nested
    @DisplayName("拒绝场景")
    class Rejection {

        @Test
        @DisplayName("非法 BigDecimal 拒绝")
        void shouldRejectInvalidBigDecimal() {
            assertThatThrownBy(() -> mapper.toSearchRequest(
                    buildQuery(singleFilter("amount", AgentOperator.EQ, "not-a-number", null))))
                    .isInstanceOf(AgentAdapterException.class)
                    .hasMessageContaining("金额");
        }

        @Test
        @DisplayName("科学计数法金额拒绝")
        void shouldRejectScientificDecimal() {
            assertThatThrownBy(() -> mapper.toSearchRequest(
                    buildQuery(singleFilter("amount", AgentOperator.EQ, "1E+10", null))))
                    .isInstanceOf(AgentAdapterException.class)
                    .hasMessageContaining("金额");
        }

        @Test
        @DisplayName("非 ISO-8601 时间拒绝")
        void shouldRejectNonIsoDateTime() {
            assertThatThrownBy(() -> mapper.toSearchRequest(
                    buildQuery(singleFilter("transDate", AgentOperator.GT, "2026/06/22", null))))
                    .isInstanceOf(AgentAdapterException.class)
                    .hasMessageContaining("时间");
        }

        @Test
        @DisplayName("非规范化时区时间拒绝")
        void shouldRejectNonCanonicalOffsetDateTime() {
            assertThatThrownBy(() -> mapper.toSearchRequest(
                    buildQuery(singleFilter(
                            "transDate", AgentOperator.GT, "2026-06-22T00:00:00+08:00", null))))
                    .isInstanceOf(AgentAdapterException.class)
                    .hasMessageContaining("UTC");
        }

        @Test
        @DisplayName("UTC 小数秒时间拒绝")
        void shouldRejectFractionalUtcDateTime() {
            assertThatThrownBy(() -> mapper.toSearchRequest(
                    buildQuery(singleFilter(
                            "transDate", AgentOperator.GT, "2026-06-22T00:00:00.001Z", null))))
                    .isInstanceOf(AgentAdapterException.class)
                    .hasMessageContaining("UTC");
        }

        @Test
        @DisplayName("transId 不支持 GT 拒绝")
        void shouldRejectGtOnTransId() {
            assertThatThrownBy(() -> mapper.toSearchRequest(
                    buildQuery(singleFilter("transId", AgentOperator.GT, "T10001", null))))
                    .isInstanceOf(AgentAdapterException.class)
                    .hasMessageContaining("GT");
        }

        @Test
        @DisplayName("transDate 不支持 EQ 拒绝")
        void shouldRejectEqOnTransDate() {
            assertThatThrownBy(() -> mapper.toSearchRequest(
                    buildQuery(singleFilter("transDate", AgentOperator.EQ, "2026-06-22T00:00:00Z", null))))
                    .isInstanceOf(AgentAdapterException.class)
                    .hasMessageContaining("EQ");
        }
    }

    private ValidatedQuery buildQuery(List<ValidatedFilter> filters) {
        return new ValidatedQuery(filters,
                List.of("transId", "transType", "transDate", "amount"), 1, 20);
    }

    private List<ValidatedFilter> singleFilter(String field, AgentOperator op, String value, List<String> values) {
        return List.of(new ValidatedFilter(field, op, value, values));
    }
}
