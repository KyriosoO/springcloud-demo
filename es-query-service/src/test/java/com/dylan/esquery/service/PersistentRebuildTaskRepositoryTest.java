package com.dylan.esquery.service;

import org.junit.jupiter.api.Test;

import javax.sql.DataSource;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Timestamp;
import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PersistentRebuildTaskRepositoryTest {

    @Test
    void insertsTaskAndMapsQueryResult() throws Exception {
        DataSource dataSource = mock(DataSource.class);
        Connection insertConnection = mock(Connection.class);
        Connection selectConnection = mock(Connection.class);
        PreparedStatement insertStatement = mock(PreparedStatement.class);
        PreparedStatement selectStatement = mock(PreparedStatement.class);
        ResultSet resultSet = taskResultSet(true);
        when(dataSource.getConnection()).thenReturn(insertConnection, selectConnection);
        when(insertConnection.prepareStatement(anyString())).thenReturn(insertStatement);
        when(selectConnection.prepareStatement(anyString())).thenReturn(selectStatement);
        when(selectStatement.executeQuery()).thenReturn(resultSet);
        PersistentRebuildTaskRepository repository = new PersistentRebuildTaskRepository(dataSource);

        repository.create("task-1", "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        var task = repository.findById("task-1");

        verify(insertStatement).setString(1, "task-1");
        verify(insertStatement).setString(2, "agent-doc-policy");
        verify(insertStatement).setString(3, "agent-doc-policy-v2");
        verify(insertStatement).executeUpdate();
        verify(selectStatement).setString(1, "task-1");
        assertThat(task.getTaskId()).isEqualTo("task-1");
        assertThat(task.getTargetIndex()).isEqualTo("agent-doc-policy-v2");
        assertThat(task.getValidationStatus()).isEqualTo("PASSED");
        assertThat(task.getValidationDigest()).isEqualTo("digest-1");
    }

    @Test
    void updatesValidationStateWithDigest() throws Exception {
        DataSource dataSource = mock(DataSource.class);
        Connection selectConnection = mock(Connection.class);
        Connection updateConnection = mock(Connection.class);
        PreparedStatement selectStatement = mock(PreparedStatement.class);
        PreparedStatement updateStatement = mock(PreparedStatement.class);
        ResultSet resultSet = taskResultSet(true);
        when(dataSource.getConnection()).thenReturn(selectConnection, updateConnection);
        when(selectConnection.prepareStatement(anyString())).thenReturn(selectStatement);
        when(updateConnection.prepareStatement(anyString())).thenReturn(updateStatement);
        when(selectStatement.executeQuery()).thenReturn(resultSet);
        PersistentRebuildTaskRepository repository = new PersistentRebuildTaskRepository(dataSource);

        repository.markValidationPassed("task-1", "digest-2", "LOCAL_DOCUMENT_INDEX_VALIDATION_V1");

        verify(updateStatement).setString(5, "PASSED");
        verify(updateStatement).setString(6, "digest-2");
        verify(updateStatement).setString(8, "LOCAL_DOCUMENT_INDEX_VALIDATION_V1");
        verify(updateStatement).setString(10, "task-1");
        verify(updateStatement).executeUpdate();
    }

    @Test
    void rejectsMissingTask() throws Exception {
        DataSource dataSource = mock(DataSource.class);
        Connection connection = mock(Connection.class);
        PreparedStatement statement = mock(PreparedStatement.class);
        ResultSet resultSet = taskResultSet(false);
        when(dataSource.getConnection()).thenReturn(connection);
        when(connection.prepareStatement(anyString())).thenReturn(statement);
        when(statement.executeQuery()).thenReturn(resultSet);
        PersistentRebuildTaskRepository repository = new PersistentRebuildTaskRepository(dataSource);

        assertThatThrownBy(() -> repository.findById("missing"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("not found");
    }

    @Test
    void migrationResourceDefinesDocumentRebuildTaskTable() throws Exception {
        try (var input = getClass().getResourceAsStream("/db/migration/V1__create_document_rebuild_task.sql")) {
            String sql = new String(input.readAllBytes(), StandardCharsets.UTF_8);

            assertThat(sql).contains("create table if not exists document_rebuild_task");
            assertThat(sql).contains("validation_digest");
            assertThat(sql).contains("idx_document_rebuild_task_target_index");
            assertThat(sql).contains("create table if not exists document_alias_operation_audit");
            assertThat(sql).contains("idx_document_alias_operation_target");
        }
    }

    @Test
    void v2MigrationAddsAliasProfileAuditFields() throws Exception {
        try (var input = getClass().getResourceAsStream("/db/migration/V2__add_document_alias_profile_audit_fields.sql")) {
            String sql = new String(input.readAllBytes(), StandardCharsets.UTF_8);

            assertThat(sql).contains("alter table document_alias_operation_audit");
            assertThat(sql).contains("domain");
            assertThat(sql).contains("material_type");
            assertThat(sql).contains("profile_version");
            assertThat(sql).contains("index_version");
            assertThat(sql).contains("idx_document_alias_operation_profile");
        }
    }

    @Test
    void v3MigrationAddsAliasGoldValidationAuditFields() throws Exception {
        try (var input = getClass().getResourceAsStream(
                "/db/migration/V3__add_document_alias_gold_validation_fields.sql")) {
            String sql = new String(input.readAllBytes(), StandardCharsets.UTF_8);

            assertThat(sql).contains("gold_set_version");
            assertThat(sql).contains("validation_report_id_prefix");
            assertThat(sql).contains("idx_document_alias_operation_gold");
        }
    }

    private ResultSet taskResultSet(boolean hasRow) throws Exception {
        ResultSet resultSet = mock(ResultSet.class);
        when(resultSet.next()).thenReturn(hasRow, false);
        if (hasRow) {
            Instant now = Instant.parse("2026-07-07T00:00:00Z");
            when(resultSet.getString("task_id")).thenReturn("task-1");
            when(resultSet.getString("index_name")).thenReturn("agent-doc-policy");
            when(resultSet.getString("target_index")).thenReturn("agent-doc-policy-v2");
            when(resultSet.getString("type")).thenReturn("FULL");
            when(resultSet.getString("status")).thenReturn("SUCCESS");
            when(resultSet.getLong("total_indexed")).thenReturn(3L);
            when(resultSet.getString("last_cursor")).thenReturn("cursor-3");
            when(resultSet.getString("error_message")).thenReturn(null);
            when(resultSet.getString("validation_status")).thenReturn("PASSED");
            when(resultSet.getString("validation_digest")).thenReturn("digest-1");
            when(resultSet.getTimestamp("validated_at")).thenReturn(Timestamp.from(now));
            when(resultSet.getString("validation_message")).thenReturn("LOCAL_DOCUMENT_INDEX_VALIDATION_V1");
            when(resultSet.getTimestamp("created_at")).thenReturn(Timestamp.from(now));
            when(resultSet.getTimestamp("updated_at")).thenReturn(Timestamp.from(now));
        }
        return resultSet;
    }
}
