package com.dylan.agent.adapter.transaction;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.math.BigDecimal;
import java.util.Date;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.transaction.api.model.Transaction;
import com.dylan.transaction.api.query.TransactionSearchResponse;

@DisplayName("TransactionSearchResponseMapper")
class TransactionSearchResponseMapperTest {

    private final TransactionSearchResponseMapper mapper = new TransactionSearchResponseMapper();

    @Nested
    @DisplayName("正常映射")
    class Success {

        @Test
        @DisplayName("只输出四个业务字段")
        void shouldOnlyOutputBusinessFields() {
            Transaction t = createTx("T001", "PAY", new Date(), BigDecimal.valueOf(100));
            TransactionSearchResponse resp = createResponse(List.of(t), 1, true, 1, 20);

            AdapterQueryResult result = mapper.toAdapterQueryResult(resp, query(1, 20));

            assertThat(result.getRows()).hasSize(1);
            Map<String, Object> row = result.getRows().get(0);
            assertThat(row).containsOnlyKeys("transId", "transType", "transDate", "amount");
            assertThat(row.get("transId")).isEqualTo("T001");
            assertThat(row.get("transType")).isEqualTo("PAY");
        }

        @Test
        @DisplayName("total/totalExact/page/size 正常映射")
        void shouldMapMetadata() {
            TransactionSearchResponse resp = createResponse(List.of(createTx("T001", "PAY", new Date(), BigDecimal.ONE)),
                    42, false, 3, 15);

            AdapterQueryResult result = mapper.toAdapterQueryResult(resp, query(3, 15));

            assertThat(result.getTotal()).isEqualTo(42);
            assertThat(result.isTotalExact()).isFalse();
            assertThat(result.getPage()).isEqualTo(3);
            assertThat(result.getSize()).isEqualTo(15);
        }
    }

    @Nested
    @DisplayName("拒绝场景")
    class Rejection {

        @Test
        @DisplayName("null response 拒绝")
        void shouldRejectNullResponse() {
            assertThatThrownBy(() -> mapper.toAdapterQueryResult(null, query(1, 20)))
                    .isInstanceOf(AgentAdapterException.class);
        }

        @Test
        @DisplayName("null rows 拒绝")
        void shouldRejectNullRows() {
            TransactionSearchResponse resp = new TransactionSearchResponse();
            resp.setPage(1);
            resp.setSize(20);
            assertThatThrownBy(() -> mapper.toAdapterQueryResult(resp, query(1, 20)))
                    .isInstanceOf(AgentAdapterException.class)
                    .hasMessageContaining("rows");
        }

        @Test
        @DisplayName("响应 rows 超过 size 拒绝")
        void shouldRejectExcessiveRows() {
            TransactionSearchResponse resp = createResponse(
                    List.of(createTx("T001", "PAY", new Date(), BigDecimal.ONE),
                            createTx("T002", "PAY", new Date(), BigDecimal.TEN),
                            createTx("T003", "PAY", new Date(), BigDecimal.ONE)),
                    3, true, 1, 2);

            assertThatThrownBy(() -> mapper.toAdapterQueryResult(resp, query(1, 2)))
                    .isInstanceOf(AgentAdapterException.class)
                    .hasMessageContaining("size");
        }

        @Test
        @DisplayName("page/size 不一致拒绝")
        void shouldRejectMismatchedPageSize() {
            TransactionSearchResponse resp = createResponse(List.of(), 0, true, 1, 20);
            assertThatThrownBy(() -> mapper.toAdapterQueryResult(resp, query(2, 20)))
                    .isInstanceOf(AgentAdapterException.class)
                    .hasMessageContaining("不一致");
        }
    }

    private Transaction createTx(String id, String type, Date date, BigDecimal amount) {
        Transaction t = new Transaction();
        t.setTransId(id);
        t.setTransType(type);
        t.setTransDate(date);
        t.setAmount(amount);
        return t;
    }

    private TransactionSearchResponse createResponse(List<Transaction> rows, long total,
                                                      boolean totalExact, int page, int size) {
        TransactionSearchResponse resp = new TransactionSearchResponse();
        resp.setRows(rows);
        resp.setTotal(total);
        resp.setTotalExact(totalExact);
        resp.setPage(page);
        resp.setSize(size);
        return resp;
    }

    private ValidatedQuery query(int page, int size) {
        return new ValidatedQuery(List.of(),
                List.of("transId", "transType", "transDate", "amount"), page, size);
    }
}
