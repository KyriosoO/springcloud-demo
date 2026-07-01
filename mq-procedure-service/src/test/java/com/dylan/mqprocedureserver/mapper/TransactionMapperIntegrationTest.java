package com.dylan.mqprocedureserver.mapper;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Date;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mybatis.spring.boot.test.autoconfigure.MybatisTest;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringBootConfiguration;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import com.dylan.transaction.api.model.Transaction;

import org.mybatis.spring.annotation.MapperScan;

@MybatisTest(properties = {
        "spring.config.import=",
        "spring.cloud.config.enabled=false",
        "mybatis.mapper-locations=classpath:com/dylan/mqprocedureserver/mapper/*.xml"
})
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Testcontainers(disabledWithoutDocker = true)
@ContextConfiguration(classes = TransactionMapperIntegrationTest.TestApplication.class)
class TransactionMapperIntegrationTest {

    @SpringBootConfiguration
    @EnableAutoConfiguration
    @MapperScan(basePackageClasses = TransactionMapper.class)
    static class TestApplication {
    }

    @Container
    static final MySQLContainer<?> MYSQL = new MySQLContainer<>("mysql:8.0")
            .withDatabaseName("transaction_test")
            .withUsername("test")
            .withPassword("test");

    @DynamicPropertySource
    static void datasource(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", MYSQL::getJdbcUrl);
        registry.add("spring.datasource.username", MYSQL::getUsername);
        registry.add("spring.datasource.password", MYSQL::getPassword);
        registry.add("spring.datasource.driver-class-name", MYSQL::getDriverClassName);
    }

    @Autowired
    private JdbcTemplate jdbc;

    @Autowired
    private TransactionMapper mapper;

    @BeforeEach
    void setUpSchema() {
        jdbc.execute("drop table if exists t_transaction");
        jdbc.execute("""
                create table t_transaction (
                  TRANS_ID varchar(64) primary key,
                  TRANS_TYPE varchar(64) not null,
                  TRANS_DATE datetime not null,
                  AMOUNT decimal(50,2) not null
                )
                """);
    }

    @Test
    void shouldUseIdenticalConditionsForCountAndQuery() {
        insert("T001", "PAYMENT", "2026-06-22T01:00:00Z", "150.00");
        insert("T002", "PAYMENT", "2026-06-22T02:00:00Z", "250.00");
        insert("T003", "REFUND", "2026-06-22T03:00:00Z", "350.00");
        insert("T004", "PAYMENT", "2026-06-24T01:00:00Z", "450.00");

        Transaction condition = new Transaction();
        condition.setTransTypeContains("PAY");
        condition.setAmountGt(new BigDecimal("100"));
        condition.setAmountLt(new BigDecimal("300"));
        condition.setTransDateGt(Date.from(Instant.parse("2026-06-22T00:00:00Z")));
        condition.setTransDateLt(Date.from(Instant.parse("2026-06-23T00:00:00Z")));

        long count = mapper.countUpTo(condition, 101);
        List<Transaction> rows = mapper.query(condition, 0, 20);

        assertThat(count).isEqualTo(2);
        assertThat(rows).extracting(Transaction::getTransId)
                .containsExactly("T002", "T001");
    }

    @Test
    void shouldLimitCountAndProvideStablePagesWithoutDuplicates() {
        for (int i = 1; i <= 5; i++) {
            insert("T00" + i, "PAYMENT", "2026-06-22T01:00:00Z", i + ".00");
        }
        Transaction condition = new Transaction();
        condition.setTransTypeContains("PAY");

        assertThat(mapper.countUpTo(condition, 3)).isEqualTo(3);
        List<Transaction> firstPage = mapper.query(condition, 0, 2);
        List<Transaction> secondPage = mapper.query(condition, 2, 2);

        assertThat(firstPage).extracting(Transaction::getTransId)
                .containsExactly("T001", "T002");
        assertThat(secondPage).extracting(Transaction::getTransId)
                .containsExactly("T003", "T004");
    }

    @Test
    void shouldKeepLegacyQueryUnpaged() {
        insert("T001", "PAYMENT", "2026-06-22T01:00:00Z", "1.00");
        insert("T002", "PAYMENT", "2026-06-22T02:00:00Z", "2.00");
        Transaction condition = new Transaction();
        condition.setTransType("PAYMENT");

        assertThat(mapper.query(condition, null, null)).hasSize(2);
    }

    private void insert(String id, String type, String instant, String amount) {
        jdbc.update("""
                insert into t_transaction (TRANS_ID, TRANS_TYPE, TRANS_DATE, AMOUNT)
                values (?, ?, ?, ?)
                """,
                id, type, Timestamp.from(Instant.parse(instant)), new BigDecimal(amount));
    }
}
