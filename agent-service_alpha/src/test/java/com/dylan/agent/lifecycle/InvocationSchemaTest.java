package com.dylan.agent.lifecycle;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;

import org.junit.jupiter.api.Test;

class InvocationSchemaTest {

    @Test
    void d03SchemaContainsInvocationResultContextAndTurnCorrelation() throws Exception {
        String sql;
        try (var stream = getClass().getResourceAsStream("/db/agent-p0.sql")) {
            assertThat(stream).as("db/agent-p0.sql resource").isNotNull();
            sql = new String(stream.readAllBytes(), StandardCharsets.UTF_8);
        }

        assertThat(sql).contains("CREATE TABLE IF NOT EXISTS agent_invocation_record");
        assertThat(sql).contains("CREATE TABLE IF NOT EXISTS agent_invocation_result");
        assertThat(sql).contains("CREATE TABLE IF NOT EXISTS agent_context_record");
        assertThat(sql).contains("created_at DATETIME(3) NOT NULL");
        assertThat(sql).contains("INDEX idx_agent_context_expiry (expires_at, readable)");
        assertThat(sql).contains("CHECK (scope_type = 'CONVERSATION')");
        assertThat(sql).contains("CHECK (record_version >= 0)");
        assertThat(sql).contains("CHECK (readable IN (0, 1))");
        assertThat(sql).contains("invocation_id VARCHAR(64)");
        assertThat(sql).contains("UNIQUE INDEX uk_agent_turn_invocation (invocation_id)");
        assertThat(sql).contains("UNIQUE INDEX uk_agent_invocation_turn (turn_id)");
        assertThat(sql).contains("UNIQUE INDEX uk_agent_invocation_correlation (request_correlation_id)");
        assertThat(sql).contains("UNIQUE INDEX uk_agent_invocation_result_invocation (invocation_id)");
        assertThat(sql).contains("FOREIGN KEY (turn_id) REFERENCES agent_turn(id)");
        assertThat(sql).contains("FOREIGN KEY (invocation_id) REFERENCES agent_invocation_record(id)");
    }

    @Test
    void d03MigrationAddsTurnInvocationCorrelationForExistingInstallations() throws Exception {
        String sql;
        try (var stream = getClass().getResourceAsStream("/db/agent-p0-v1.3.sql")) {
            assertThat(stream).as("db/agent-p0-v1.3.sql resource").isNotNull();
            sql = new String(stream.readAllBytes(), StandardCharsets.UTF_8);
        }

        assertThat(sql).contains("ALTER TABLE agent_turn");
        assertThat(sql).contains("ADD COLUMN invocation_id VARCHAR(64)");
        assertThat(sql).contains("ADD UNIQUE INDEX uk_agent_turn_invocation (invocation_id)");
    }
}
