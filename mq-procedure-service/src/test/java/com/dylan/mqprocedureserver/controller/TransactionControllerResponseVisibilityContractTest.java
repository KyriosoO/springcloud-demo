package com.dylan.mqprocedureserver.controller;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.InputStream;
import java.math.BigDecimal;
import java.nio.file.Path;
import java.util.Date;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

import org.junit.jupiter.api.Test;

import com.dylan.transaction.api.model.Transaction;
import com.dylan.transaction.api.query.TransactionSearchResponse;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

class TransactionControllerResponseVisibilityContractTest {
	private final ObjectMapper objectMapper = new ObjectMapper();

	@Test
	void fullSerializedResponseMatchesVersionedVisibilityFixture() throws Exception {
		JsonNode fixture = fixture("/contracts/transaction-search-response-visibility-v1.json");
		Transaction row = syntheticRow();
		TransactionSearchResponse response = new TransactionSearchResponse();
		response.setRows(List.of(row));
		response.setTotal(1);
		response.setTotalExact(true);
		response.setPage(1);
		response.setSize(20);
		JsonNode actual = objectMapper.valueToTree(response);

		assertThat(fieldNames(actual)).containsExactlyElementsOf(textSet(fixture.path("topLevelFields")));
		assertThat(fieldNames(actual.path("rows").get(0)))
				.containsExactlyElementsOf(textSet(fixture.path("rowFields")));
		assertThat(fixture.path("allowedRoles")).extracting(JsonNode::asText)
				.containsExactly("ADMIN", "VIEWER");
	}

	@Test
	void callerInventoryFreezesTheOnlyRepositoryHttpConsumer() throws Exception {
		JsonNode fixture = fixture("/contracts/transaction-search-callers-v1.json");
		assertThat(fixture.path("callers")).hasSize(1);
		assertThat(fixture.path("callers").get(0).path("callerId").asText())
				.isEqualTo("agent-runtime.transaction.search");
		assertThat(repositoryFile(fixture.path("callers").get(0).path("source").asText())).isRegularFile();
		assertThat(repositoryFile(fixture.path("transportIntermediaries").get(0).path("source").asText()))
				.isRegularFile();
		assertThat(fixture.path("declaredExternalLegacyCallers")).isEmpty();
	}

	private static Path repositoryFile(String relativePath) {
		return Path.of("..").resolve(relativePath).normalize();
	}

	private JsonNode fixture(String path) throws Exception {
		try (InputStream input = getClass().getResourceAsStream(path)) {
			return objectMapper.readTree(input);
		}
	}

	private static Set<String> fieldNames(JsonNode node) {
		Set<String> names = new TreeSet<>();
		node.fieldNames().forEachRemaining(names::add);
		return names;
	}

	private static Set<String> textSet(JsonNode array) {
		Set<String> values = new TreeSet<>();
		array.forEach(node -> values.add(node.asText()));
		return values;
	}

	private static Transaction syntheticRow() {
		Transaction row = new Transaction();
		row.setTransId("synthetic-id");
		row.setTransType("synthetic-type");
		row.setTransDate(new Date(0));
		row.setAmount(new BigDecimal("1.00"));
		row.setTransDateGt(new Date(1));
		row.setTransDateLt(new Date(2));
		row.setAmountGt(new BigDecimal("0.01"));
		row.setAmountLt(new BigDecimal("2.00"));
		row.setTransTypeContains("synthetic");
		return row;
	}
}
