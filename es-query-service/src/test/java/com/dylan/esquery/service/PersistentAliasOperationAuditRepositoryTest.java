package com.dylan.esquery.service;

import org.junit.jupiter.api.Test;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PersistentAliasOperationAuditRepositoryTest {

	@Test
	void insertsOneRowPerSourceAliasIndex() throws Exception {
		DataSource dataSource = mock(DataSource.class);
		Connection connection1 = mock(Connection.class);
		Connection connection2 = mock(Connection.class);
		PreparedStatement statement1 = mock(PreparedStatement.class);
		PreparedStatement statement2 = mock(PreparedStatement.class);
		when(dataSource.getConnection()).thenReturn(connection1, connection2);
		when(connection1.prepareStatement(anyString())).thenReturn(statement1);
		when(connection2.prepareStatement(anyString())).thenReturn(statement2);
		PersistentAliasOperationAuditRepository repository = new PersistentAliasOperationAuditRepository(dataSource);

		repository.record(audit(List.of("agent-doc-policy-v1", "agent-doc-policy-v0"), "agent-doc-policy-v2", "SUCCESS"));

		verify(statement1).setString(3, "agent-doc-policy-v1");
		verify(statement2).setString(3, "agent-doc-policy-v0");
		verify(statement1).executeUpdate();
		verify(statement2).executeUpdate();
	}

	@Test
	void findsTrustedTargetFromPersistedHistory() throws Exception {
		DataSource dataSource = mock(DataSource.class);
		Connection connection = mock(Connection.class);
		PreparedStatement statement = mock(PreparedStatement.class);
		ResultSet resultSet = mock(ResultSet.class);
		when(dataSource.getConnection()).thenReturn(connection);
		when(connection.prepareStatement(anyString())).thenReturn(statement);
		when(statement.executeQuery()).thenReturn(resultSet);
		when(resultSet.next()).thenReturn(true);
		PersistentAliasOperationAuditRepository repository = new PersistentAliasOperationAuditRepository(dataSource);

		boolean trusted = repository.hasTrustedTarget("agent-doc-policy", "agent-doc-policy-v1");

		assertThat(trusted).isTrue();
		verify(statement).setString(1, "agent-doc-policy");
		verify(statement).setString(2, "agent-doc-policy-v1");
		verify(statement).setString(3, "agent-doc-policy-v1");
	}

	private AliasOperationAudit audit(List<String> fromIndexes, String toIndex, String result) {
		return new AliasOperationAudit(
				"agent-doc-policy",
				"SWITCH",
				fromIndexes,
				toIndex,
				"task-1",
				"digest-1",
				"operator-hash",
				result,
				null,
				10,
				Instant.parse("2026-07-07T00:00:00Z"));
	}
}
