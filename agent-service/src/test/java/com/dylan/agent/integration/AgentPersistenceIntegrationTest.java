package com.dylan.agent.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.jdbc.JdbcTestUtils;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import com.dylan.agent.api.enums.AgentErrorCode;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentResponseType;
import com.dylan.agent.api.runtime.RuntimeTurn;
import com.dylan.agent.conversation.ConversationService;
import com.dylan.agent.conversation.ConversationHandle;
import com.dylan.agent.conversation.TurnHandle;
import com.dylan.agent.exception.AgentConversationNotFoundException;
import com.dylan.agent.exception.AgentInternalException;
import com.dylan.agent.model.TurnStatus;
import com.dylan.agent.persistence.mapper.AgentConversationMapper;
import com.dylan.agent.persistence.mapper.AgentTurnMapper;

@SpringBootTest(properties = {
        "spring.config.import=",
        "spring.cloud.config.enabled=false",
        "eureka.client.enabled=false"
})
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Testcontainers(disabledWithoutDocker = true)
@DisplayName("AgentPersistentIntegrationTest")
class AgentPersistenceIntegrationTest {

    @Container
    static MySQLContainer<?> mysql = new MySQLContainer<>("mysql:8.0")
            .withDatabaseName("test_agent")
            .withUsername("test")
            .withPassword("test")
            .withReuse(true);

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", mysql::getJdbcUrl);
        registry.add("spring.datasource.username", mysql::getUsername);
        registry.add("spring.datasource.password", mysql::getPassword);
        registry.add("spring.sql.init.mode", () -> "always");
        registry.add("spring.sql.init.schema-locations", () -> "classpath:db/agent-p0.sql");
    }

    @TestConfiguration
    static class TestClockConfig {
        @Bean
        @Primary
        Clock testClock() {
            return Clock.fixed(Instant.parse("2026-06-18T10:00:00Z"), ZoneOffset.UTC);
        }
    }

    @Autowired private ConversationService conversationService;
    @Autowired private AgentConversationMapper conversationMapper;
    @Autowired private AgentTurnMapper turnMapper;
    @Autowired private JdbcTemplate jdbcTemplate;
    @Autowired private javax.sql.DataSource dataSource;
    @Autowired private Clock clock;

    private String userId;
    private String otherUserId;

    @BeforeEach
    void setUp() {
        userId = "user-" + UUID.randomUUID().toString().substring(0, 8);
        otherUserId = "other-" + UUID.randomUUID().toString().substring(0, 8);
        // 清理测试数据
        JdbcTestUtils.deleteFromTables(jdbcTemplate, "agent_turn", "agent_conversation");
    }

    @Nested
    @DisplayName("SQL 初始化")
    class SqlInit {

        @Test
        @DisplayName("脚本可重复执行且两张表可查询")
        void shouldInitializeTwiceAndHaveBothTables() {
            new ResourceDatabasePopulator(new ClassPathResource("db/agent-p0.sql")).execute(dataSource);
            // 表存在即可执行无异常的查询
            var convCount = JdbcTestUtils.countRowsInTable(jdbcTemplate, "agent_conversation");
            var turnCount = JdbcTestUtils.countRowsInTable(jdbcTemplate, "agent_turn");
            assertThat(convCount).isGreaterThanOrEqualTo(0);
            assertThat(turnCount).isGreaterThanOrEqualTo(0);
            assertThat(jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM information_schema.columns " +
                    "WHERE table_schema = DATABASE() AND table_name = 'agent_turn' AND column_name = 'turn_seq'",
                    Integer.class)).isEqualTo(1);
        }
    }

    @Nested
    @DisplayName("Conversation 归属")
    class ConversationOwnership {

        @Test
        @DisplayName("创建新会话")
        void shouldCreateNewConversation() {
            ConversationHandle handle = conversationService.openConversation(null, userId);
            assertThat(handle.conversationId()).isNotBlank();

            var entity = conversationMapper.selectOwned(handle.conversationId(), userId);
            assertThat(entity).isNotNull();
            assertThat(entity.getUserId()).isEqualTo(userId);
        }

        @Test
        @DisplayName("加载自己的会话成功")
        void shouldLoadOwnConversation() {
            ConversationHandle created = conversationService.openConversation(null, userId);
            ConversationHandle loaded = conversationService.openConversation(created.conversationId(), userId);
            assertThat(loaded.conversationId()).isEqualTo(created.conversationId());
        }

        @Test
        @DisplayName("加载他人会话拒绝")
        void shouldRejectOtherUserConversation() {
            ConversationHandle created = conversationService.openConversation(null, userId);
            assertThatThrownBy(() -> conversationService.openConversation(created.conversationId(), otherUserId))
                    .isInstanceOf(AgentConversationNotFoundException.class);
        }

        @Test
        @DisplayName("不存在的会话 ID 拒绝")
        void shouldRejectNonExistentId() {
            assertThatThrownBy(() -> conversationService.openConversation("non-existent-id", userId))
                    .isInstanceOf(AgentConversationNotFoundException.class);
        }
    }

    @Nested
    @DisplayName("Turn 状态和 CAS")
    class TurnLifecycle {

        @Test
        @DisplayName("成功 Turn 状态流转")
        void shouldUpdateToSucceeded() {
            ConversationHandle conv = conversationService.openConversation(null, userId);
            TurnHandle turn = conversationService.startTurn(conv.conversationId(), userId, "查询员工");

            conversationService.completeSuccess(turn.turnId(), AgentIntent.QUERY,
                    AgentResponseType.RESULT, "找到 0 条记录。", null);

            // 验证数据库状态
            var rows = jdbcTemplate.queryForList(
                    "SELECT status, intent, response_type, assistant_message FROM agent_turn WHERE id = ?",
                    turn.turnId());
            assertThat(rows).hasSize(1);
            assertThat(rows.get(0).get("status")).isEqualTo(TurnStatus.SUCCEEDED.name());
        }

        @Test
        @DisplayName("失败 Turn 状态流转")
        void shouldUpdateToFailed() {
            ConversationHandle conv = conversationService.openConversation(null, userId);
            TurnHandle turn = conversationService.startTurn(conv.conversationId(), userId, "测试");

            conversationService.completeFailure(turn.turnId(), AgentErrorCode.AGENT_INTERNAL_ERROR, "错误");

            var rows = jdbcTemplate.queryForList(
                    "SELECT status, error_code FROM agent_turn WHERE id = ?", turn.turnId());
            assertThat(rows.get(0).get("status")).isEqualTo(TurnStatus.FAILED.name());
            assertThat(rows.get(0).get("error_code")).isEqualTo(AgentErrorCode.AGENT_INTERNAL_ERROR.name());
        }

        @Test
        @DisplayName("重复完成同一 Turn 失败 (CAS)")
        void shouldRejectDoubleCompletion() {
            ConversationHandle conv = conversationService.openConversation(null, userId);
            TurnHandle turn = conversationService.startTurn(conv.conversationId(), userId, "测试");
            conversationService.completeFailure(turn.turnId(), AgentErrorCode.AGENT_INTERNAL_ERROR, "错误");

            // CAS 更新应失败（status 已不是 PROCESSING）
            assertThatThrownBy(() -> conversationService.completeSuccess(
                    turn.turnId(), AgentIntent.QUERY, AgentResponseType.RESULT, "消息", null))
                    .isInstanceOf(AgentInternalException.class);
        }
    }

    @Nested
    @DisplayName("最近 Turn 顺序")
    class RecentTurnOrdering {

        @Test
        @DisplayName("按时间倒序取最近 N 条并在 Java 中正序返回")
        void shouldReturnRecentInCorrectOrder() {
            ConversationHandle conv = conversationService.openConversation(null, userId);

            TurnHandle t1 = conversationService.startTurn(conv.conversationId(), userId, "第一轮问题");
            conversationService.completeSuccess(t1.turnId(), AgentIntent.CLARIFY,
                    AgentResponseType.CLARIFY, "第一轮回答", null);

            TurnHandle t2 = conversationService.startTurn(conv.conversationId(), userId, "第二轮问题");
            conversationService.completeSuccess(t2.turnId(), AgentIntent.QUERY,
                    AgentResponseType.RESULT, "第二轮回答", null);

            List<RuntimeTurn> turns = conversationService.loadRecentTurns(conv.conversationId(), userId, 6);
            // 应包含 4 条：USER(1) ASSISTANT(1) USER(2) ASSISTANT(2)，按时间正序
            assertThat(turns).hasSize(4);
            assertThat(turns.get(0).getContent()).isEqualTo("第一轮问题");
            assertThat(turns.get(1).getContent()).isEqualTo("第一轮回答");
            assertThat(turns.get(2).getContent()).isEqualTo("第二轮问题");
            assertThat(turns.get(3).getContent()).isEqualTo("第二轮回答");
        }
    }

    @Nested
    @DisplayName("外键约束")
    class ForeignKeyConstraint {

        @Test
        @DisplayName("Turn 必须关联存在的 Conversation")
        void shouldEnforceForeignKey() {
            assertThatThrownBy(() -> jdbcTemplate.update(
                    "INSERT INTO agent_turn (id, conversation_id, user_id, user_message, status, created_at) " +
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    UUID.randomUUID().toString(), "non-existent-conv", userId, "测试",
                    TurnStatus.PROCESSING.name(), LocalDateTime.now(clock)))
                    .isNotNull(); // 外键约束触发异常
        }
    }

    @Nested
    @DisplayName("过期清理")
    class Cleanup {

        @Test
        @DisplayName("删除超过保留期的 Turn，再删除无 Turn 的 Conversation")
        void shouldCleanupExpiredData() {
            ConversationHandle conv = conversationService.openConversation(null, userId);
            TurnHandle turn = conversationService.startTurn(conv.conversationId(), userId, "test");
            conversationService.completeSuccess(turn.turnId(), AgentIntent.QUERY,
                    AgentResponseType.RESULT, "done", null);

            // 截止时间早于数据 → 不删除
            int deleted = conversationService.cleanupExpired(LocalDateTime.now(clock).minusDays(1));
            assertThat(deleted).isEqualTo(0);

            // 截止时间晚于数据 → 删除
            int deleted2 = conversationService.cleanupExpired(LocalDateTime.now(clock).plusDays(1));
            assertThat(deleted2).isGreaterThan(0);
        }
    }
}
