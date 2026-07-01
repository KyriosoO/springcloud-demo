package com.dylan.agent.adapter.transaction;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.plan.AggregateOrderSpec;
import com.dylan.transaction.api.model.AggregateRequest;
import com.dylan.transaction.api.model.Transaction;
import com.dylan.transaction.api.query.TransactionSearchRequest;
import com.dylan.transaction.api.query.TransactionSearchResponse;

import feign.FeignException;
import feign.Request;
import feign.Response;

class TransactionAgentAdapterTest {

    private final TransactionAgentClient client = mock(TransactionAgentClient.class);
    private final TransactionAgentAdapter adapter = new TransactionAgentAdapter(
            new TransactionPlanMapper(), client, new TransactionSearchResponseMapper(),
            new TransactionAggregateResponseMapper());

    @Test
    void shouldCallFeignAndMapResponse() {
        Transaction row = new Transaction();
        row.setTransId("T001");
        row.setTransType("PAY");
        row.setTransDate(Date.from(Instant.parse("2026-06-22T00:00:00Z")));
        row.setAmount(new BigDecimal("12.50"));
        TransactionSearchResponse response = new TransactionSearchResponse();
        response.setRows(List.of(row));
        response.setTotal(1);
        response.setTotalExact(true);
        response.setPage(1);
        response.setSize(20);
        when(client.search(any())).thenReturn(response);

        var result = adapter.query(query());

        ArgumentCaptor<TransactionSearchRequest> request =
                ArgumentCaptor.forClass(TransactionSearchRequest.class);
        verify(client).search(request.capture());
        assertThat(request.getValue().getCondition().getTransTypeContains()).isEqualTo("PAY");
        assertThat(result.getRows().getFirst()).containsAllEntriesOf(Map.of(
                "transId", "T001",
                "transType", "PAY",
                "transDate", "2026-06-22T00:00:00Z",
                "amount", new BigDecimal("12.50")));
    }

    @Test
    void shouldConvertFeignFailureWithoutLeakingBody() {
        Request request = Request.create(Request.HttpMethod.POST, "/txn/search", Map.of(),
                null, StandardCharsets.UTF_8, null);
        FeignException downstream = FeignException.errorStatus("search",
                Response.builder()
                        .request(request)
                        .status(500)
                        .reason("Internal Server Error")
                        .headers(Map.of())
                        .body("secret downstream response", StandardCharsets.UTF_8)
                        .build());
        when(client.search(any())).thenThrow(downstream);

        assertThatThrownBy(() -> adapter.query(query()))
                .isInstanceOf(AgentAdapterException.class)
                .hasMessage("Transaction 服务查询失败。")
                .hasMessageNotContaining("secret downstream response");
    }

    @Test
    void shouldCallAggregateAndMapMetricAliases() {
        when(client.aggregate(any())).thenReturn(Map.of("groups", List.of(
                Map.of("transType", "PAY", "sumAmount", new BigDecimal("12.50"), "count", 2),
                Map.of("transType", "REFUND", "sumAmount", new BigDecimal("8.00"), "count", 1))));

        var result = adapter.aggregate(aggregateQuery());

        ArgumentCaptor<AggregateRequest> request = ArgumentCaptor.forClass(AggregateRequest.class);
        verify(client).aggregate(request.capture());
        assertThat(request.getValue().getCondition().getTransType()).isEqualTo("PAY");
        assertThat(request.getValue().getGroupBy()).containsExactly("transType");
        assertThat(request.getValue().getMetrics()).containsExactly("SUM:amount", "COUNT");
        assertThat(result.getRows()).hasSize(2);
        assertThat(result.getRows().get(0)).containsAllEntriesOf(Map.of(
                "transType", "PAY",
                "totalAmount", new BigDecimal("12.50"),
                "countRecords", 2));
    }

    private ValidatedQuery query() {
        return new ValidatedQuery(
                List.of(new ValidatedFilter(
                        "transType", AgentOperator.CONTAINS, "PAY", List.of())),
                List.of("transId", "transType", "transDate", "amount"),
                1, 20);
    }

    private ValidatedAggregateQuery aggregateQuery() {
        AggregateOrderSpec order = new AggregateOrderSpec();
        order.setField("totalAmount");
        order.setDirection("DESC");
        return new ValidatedAggregateQuery(
                List.of(new ValidatedFilter("transType", AgentOperator.EQ, "PAY", List.of())),
                List.of(
                        new ValidatedAggregateMetric("totalAmount", AggregateFunction.SUM, "amount"),
                        new ValidatedAggregateMetric("countRecords", AggregateFunction.COUNT, null)),
                List.of("transType"),
                List.of(order),
                20);
    }
}
