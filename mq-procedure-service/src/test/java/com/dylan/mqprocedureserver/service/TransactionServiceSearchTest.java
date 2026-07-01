package com.dylan.mqprocedureserver.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.math.BigDecimal;
import java.util.Date;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.mqprocedureserver.config.TransactionSearchProperties;
import com.dylan.mqprocedureserver.mapper.TransactionMapper;
import com.dylan.transaction.api.model.Transaction;
import com.dylan.transaction.api.query.TransactionSearchRequest;
import com.dylan.transaction.api.query.TransactionSearchResponse;

@DisplayName("TransactionService.search()")
class TransactionServiceSearchTest {

    private StubTransactionMapper mapper;
    private TransactionSearchProperties props;
    private TransactionService service;

    @BeforeEach
    void setUp() {
        mapper = new StubTransactionMapper();
        props = new TransactionSearchProperties();
        props.setMaxExactTotal(100); // 测试用较小阈值
        service = new TransactionService(mapper, props);
    }

    @Nested
    @DisplayName("正常场景")
    class Success {

        @Test
        @DisplayName("正常分页查询")
        void shouldReturnPagedResult() {
            mapper.countUpToResult = 50;
            mapper.queryResults = List.of(createTx("T001"), createTx("T002"));

            TransactionSearchResponse resp = service.search(makeRequest("PAY", null, null, 1, 20));

            assertThat(resp.getTotal()).isEqualTo(50);
            assertThat(resp.isTotalExact()).isTrue();
            assertThat(resp.getRows()).hasSize(2);
            assertThat(resp.getPage()).isEqualTo(1);
            assertThat(resp.getSize()).isEqualTo(20);
        }

        @Test
        @DisplayName("total 为 0 时不查询 rows")
        void shouldReturnEmptyWhenTotalZero() {
            mapper.countUpToResult = 0;

            TransactionSearchResponse resp = service.search(makeRequest("PAY", null, null, 1, 20));

            assertThat(resp.getTotal()).isEqualTo(0);
            assertThat(resp.isTotalExact()).isTrue();
            assertThat(resp.getRows()).isEmpty();
        }

        @Test
        @DisplayName("匹配数小于阈值时返回精确 total")
        void shouldReturnExactWhenBelowThreshold() {
            mapper.countUpToResult = 50; // < maxExactTotal(100)

            TransactionSearchResponse resp = service.search(makeRequest("PAY", null, null, 1, 20));

            assertThat(resp.isTotalExact()).isTrue();
            assertThat(resp.getTotal()).isEqualTo(50);
        }

        @Test
        @DisplayName("匹配数等于阈值时仍返回精确 total")
        void shouldReturnExactWhenEqualToThreshold() {
            mapper.countUpToResult = 100; // == maxExactTotal(100)

            TransactionSearchResponse resp = service.search(makeRequest("PAY", null, null, 1, 20));

            assertThat(resp.isTotalExact()).isTrue();
            assertThat(resp.getTotal()).isEqualTo(100);
        }

        @Test
        @DisplayName("匹配数大于阈值时返回下界")
        void shouldReturnLowerBoundWhenAboveThreshold() {
            mapper.countUpToResult = 101; // > maxExactTotal(100)

            TransactionSearchResponse resp = service.search(makeRequest("PAY", null, null, 1, 20));

            assertThat(resp.isTotalExact()).isFalse();
            assertThat(resp.getTotal()).isEqualTo(100); // clamped to threshold
        }

        @Test
        @DisplayName("修改测试配置阈值后使用新值")
        void shouldUseInjectedThresholdNotHardcoded() {
            props.setMaxExactTotal(50);
            mapper.countUpToResult = 51;

            TransactionSearchResponse resp = service.search(makeRequest("PAY", null, null, 1, 20));

            assertThat(resp.isTotalExact()).isFalse();
            assertThat(resp.getTotal()).isEqualTo(50);
        }
    }

    @Nested
    @DisplayName("拒绝场景")
    class Rejection {

        @Test
        @DisplayName("page 非法拒绝")
        void shouldRejectInvalidPage() {
            assertThatThrownBy(() -> service.search(makeRequest("T001", null, null, 0, 20)))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("page");
        }

        @Test
        @DisplayName("size 非法拒绝")
        void shouldRejectInvalidSize() {
            assertThatThrownBy(() -> service.search(makeRequest("T001", null, null, 1, 101)))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("size");
        }

        @Test
        @DisplayName("空条件拒绝")
        void shouldRejectEmptyCondition() {
            TransactionSearchRequest req = new TransactionSearchRequest();
            req.setCondition(new Transaction());
            req.setPage(1);
            req.setSize(20);
            assertThatThrownBy(() -> service.search(req))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("条件");
        }

        @Test
        @DisplayName("offset 溢出拒绝")
        void shouldRejectOffsetOverflow() {
            assertThatThrownBy(() -> service.search(makeRequest("T001", null, null, Integer.MAX_VALUE, 100)))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("溢出");
        }
    }

    private TransactionSearchRequest makeRequest(String transId, BigDecimal amountGt, BigDecimal amountLt, int page, int size) {
        TransactionSearchRequest req = new TransactionSearchRequest();
        Transaction c = new Transaction();
        c.setTransId(transId);
        if (amountGt != null) c.setAmountGt(amountGt);
        if (amountLt != null) c.setAmountLt(amountLt);
        req.setCondition(c);
        req.setPage(page);
        req.setSize(size);
        return req;
    }

    private Transaction createTx(String id) {
        Transaction t = new Transaction();
        t.setTransId(id);
        t.setTransType("PAY");
        t.setTransDate(new Date());
        t.setAmount(BigDecimal.valueOf(100));
        return t;
    }

    static class StubTransactionMapper implements TransactionMapper {
        long countUpToResult;
        List<Transaction> queryResults = List.of();

        @Override
        public long countUpTo(Transaction condition, int limit) {
            return countUpToResult;
        }

        @Override
        public List<Transaction> query(Transaction condition, Integer offset, Integer size) {
            return queryResults;
        }

        @Override public List<Transaction> fetchAll() { return List.of(); }
        @Override public Transaction findByCondition(Transaction condition) { return null; }
        @Override public java.util.Map<String, Object> aggregate(Transaction condition) { return java.util.Map.of(); }
        @Override public java.util.List<java.util.Map<String, Object>> aggregateDynamic(
                Transaction condition, String selectClause, String groupByClause) { return List.of(); }
        @Override public int insert(Transaction t) { return 0; }
        @Override public int update(Transaction t) { return 0; }
        @Override public int deleteByTransId(String id) { return 0; }
    }
}
