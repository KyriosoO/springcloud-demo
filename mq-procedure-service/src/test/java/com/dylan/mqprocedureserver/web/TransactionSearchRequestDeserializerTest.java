package com.dylan.mqprocedureserver.web;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.math.BigDecimal;
import java.time.Instant;

import org.junit.jupiter.api.Test;

import com.dylan.transaction.api.query.TransactionSearchRequest;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.module.SimpleModule;

class TransactionSearchRequestDeserializerTest {
	private final ObjectMapper objectMapper = mapper();

	@Test
	void bindsJsonNumberDirectlyToBigDecimal() throws Exception {
		TransactionSearchRequest request = objectMapper.readValue(
				"{\"condition\":{\"amountGt\":1234567890123456.1234},\"page\":1,\"size\":20}",
				TransactionSearchRequest.class);
		assertThat(request.getCondition().getAmountGt())
				.isEqualTo(new BigDecimal("1234567890123456.1234"));
		assertThat(request.getCondition().getAmountGt().scale()).isEqualTo(4);
	}

	@Test
	void rejectsQuotedAmountWire() {
		assertThatThrownBy(() -> objectMapper.readValue(
				"{\"condition\":{\"amount\":\"100.00\"},\"page\":1,\"size\":20}",
				TransactionSearchRequest.class)).isInstanceOf(Exception.class);
	}

	@Test
	void preservesExplicitOffsetsForExactAndOpenIntervalDates() throws Exception {
		TransactionSearchRequest request = objectMapper.readValue(
				"""
				{"condition":{"transDate":"2026-08-25T09:00:00+08:00",
				"transDateGt":"2026-08-25T08:00:00+08:00",
				"transDateLt":"2026-08-25T10:00:00+08:00"},"page":2,"size":20}
				""",
				TransactionSearchRequest.class);

		assertThat(request.getCondition().getTransDate().toInstant())
				.isEqualTo(Instant.parse("2026-08-25T01:00:00Z"));
		assertThat(request.getCondition().getTransDateGt().toInstant())
				.isEqualTo(Instant.parse("2026-08-25T00:00:00Z"));
		assertThat(request.getCondition().getTransDateLt().toInstant())
				.isEqualTo(Instant.parse("2026-08-25T02:00:00Z"));
		assertThat(request.getPage()).isEqualTo(2);
	}

	@Test
	void preservesEquivalentDateInstantsAcrossExplicitOffsets() throws Exception {
		TransactionSearchRequest request = objectMapper.readValue(
				"""
				{"condition":{"transDateGt":"2026-08-25T09:00:00+08:00",
				"transDateLt":"2026-08-25T02:00:01+00:00"},"page":1,"size":20}
				""",
				TransactionSearchRequest.class);

		assertThat(request.getCondition().getTransDateGt().getTime())
				.isLessThan(request.getCondition().getTransDateLt().getTime());
	}

	private static ObjectMapper mapper() {
		SimpleModule module = new SimpleModule();
		module.addDeserializer(TransactionSearchRequest.class, new TransactionSearchRequestDeserializer());
		return new ObjectMapper().registerModule(module);
	}
}
