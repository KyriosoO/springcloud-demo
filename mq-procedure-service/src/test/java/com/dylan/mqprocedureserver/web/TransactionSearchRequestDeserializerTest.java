package com.dylan.mqprocedureserver.web;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.math.BigDecimal;

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

	private static ObjectMapper mapper() {
		SimpleModule module = new SimpleModule();
		module.addDeserializer(TransactionSearchRequest.class, new TransactionSearchRequestDeserializer());
		return new ObjectMapper().registerModule(module);
	}
}
