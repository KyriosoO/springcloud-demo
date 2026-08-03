package com.dylan.mqprocedureserver.service;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.math.BigDecimal;
import java.io.InputStream;

import org.junit.jupiter.api.Test;

import com.dylan.transaction.api.model.Transaction;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

class TransactionAmountContractTest {

	@Test
	void acceptsExactDecimal50Scale2BoundariesWithoutChangingValue() {
		assertAccepted("0");
		assertAccepted("0.01");
		assertAccepted("-0.01");
		assertAccepted("999999999999999999999999999999999999999999999999.99");
	}

	@Test
	void rejectsBeforeMapperWhenScaleOrIntegerDigitsExceedTheOwnedColumn() {
		assertRejected("0.001");
		assertRejected("1000000000000000000000000000000000000000000000000");
	}

	@Test
	void constantsMatchTheVersionedProductionMetadataSnapshot() throws Exception {
		try (InputStream input = getClass().getResourceAsStream(
				"/contracts/transaction-amount-column-v1.json")) {
			JsonNode fixture = new ObjectMapper().readTree(input);
			org.assertj.core.api.Assertions.assertThat(fixture.path("dataType").asText()).isEqualTo("decimal");
			org.assertj.core.api.Assertions.assertThat(fixture.path("precision").asInt())
					.isEqualTo(TransactionAmountContract.PRECISION);
			org.assertj.core.api.Assertions.assertThat(fixture.path("scale").asInt())
					.isEqualTo(TransactionAmountContract.SCALE);
		}
	}

	private static void assertAccepted(String value) {
		Transaction condition = new Transaction();
		BigDecimal amount = new BigDecimal(value);
		condition.setAmount(amount);
		assertThatCode(() -> TransactionAmountContract.validateSearchCondition(condition))
				.doesNotThrowAnyException();
		org.assertj.core.api.Assertions.assertThat(condition.getAmount()).isSameAs(amount);
	}

	private static void assertRejected(String value) {
		Transaction condition = new Transaction();
		condition.setAmount(new BigDecimal(value));
		assertThatThrownBy(() -> TransactionAmountContract.validateSearchCondition(condition))
				.isInstanceOf(IllegalArgumentException.class);
	}
}
