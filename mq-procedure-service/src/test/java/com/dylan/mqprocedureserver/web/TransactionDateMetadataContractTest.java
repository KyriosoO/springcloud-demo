package com.dylan.mqprocedureserver.web;

import static org.assertj.core.api.Assertions.assertThat;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;

import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;

class TransactionDateMetadataContractTest {

	@Test
	void productionTransactionDateUsesVerifiedSecondPrecision() throws Exception {
		String url = System.getenv("AGENT_TXN_DATE_METADATA_JDBC_URL");
		String username = System.getenv("AGENT_TXN_DATE_METADATA_USERNAME");
		String password = System.getenv("AGENT_TXN_DATE_METADATA_PASSWORD");
		Assumptions.assumeTrue(url != null && username != null && password != null);

		try (Connection connection = DriverManager.getConnection(url, username, password);
				PreparedStatement statement = connection.prepareStatement("""
						select DATA_TYPE, DATETIME_PRECISION
						from information_schema.COLUMNS
						where TABLE_SCHEMA = DATABASE()
						  and TABLE_NAME = 't_transaction'
						  and COLUMN_NAME = 'TRANS_DATE'
						""");
				ResultSet rows = statement.executeQuery()) {
			assertThat(rows.next()).isTrue();
			assertThat(rows.getString("DATA_TYPE")).isEqualTo("datetime");
			assertThat(rows.getInt("DATETIME_PRECISION")).isZero();
			assertThat(rows.next()).isFalse();
		}
	}
}
