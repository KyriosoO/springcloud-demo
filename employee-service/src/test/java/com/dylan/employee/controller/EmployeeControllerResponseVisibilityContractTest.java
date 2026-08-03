package com.dylan.employee.controller;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.InputStream;
import java.lang.reflect.Method;
import java.nio.file.Path;
import java.util.Set;
import java.util.TreeSet;

import org.junit.jupiter.api.Test;

import com.dylan.employee.model.Employee;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

class EmployeeControllerResponseVisibilityContractTest {

	private final ObjectMapper objectMapper = new ObjectMapper();

	@Test
	void serializedFullFieldSetMatchesVersionedVisibilityFixture() throws Exception {
		JsonNode fixture = fixture("/contracts/employee-detail-response-visibility-v1.json");
		Employee employee = allFieldsSynthetic();
		Set<String> actual = new TreeSet<>();
		objectMapper.valueToTree(employee).fieldNames().forEachRemaining(actual::add);
		Set<String> expected = new TreeSet<>();
		fixture.path("fields").forEach(node -> expected.add(node.asText()));

		assertThat(fixture.path("allowedRoles")).extracting(JsonNode::asText)
				.containsExactly("ADMIN", "VIEWER");
		assertThat(actual).containsExactlyElementsOf(expected);
		assertThat(actual).hasSize(58);
	}

	@Test
	void callerInventoryFreezesTheOnlyRepositoryHttpConsumer() throws Exception {
		JsonNode fixture = fixture("/contracts/employee-detail-callers-v1.json");
		assertThat(fixture.path("callers")).hasSize(1);
		assertThat(fixture.path("callers").get(0).path("callerId").asText())
				.isEqualTo("agent-runtime.employee.detail");
		assertThat(repositoryFile(fixture.path("callers").get(0).path("source").asText())).isRegularFile();
		assertThat(repositoryFile(fixture.path("nonHttpInternalConsumers").get(0).path("source").asText()))
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

	private static Employee allFieldsSynthetic() throws Exception {
		Employee employee = new Employee();
		for (Method method : Employee.class.getMethods()) {
			if (method.getName().startsWith("set") && method.getParameterCount() == 1
					&& method.getParameterTypes()[0] == String.class) {
				method.invoke(employee, "synthetic-" + method.getName());
			}
		}
		return employee;
	}
}
