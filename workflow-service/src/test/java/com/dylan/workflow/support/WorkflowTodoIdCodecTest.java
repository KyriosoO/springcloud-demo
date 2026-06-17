package com.dylan.workflow.support;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

import com.dylan.workflow.model.WorkflowInstance;
import com.dylan.workflow.model.WorkflowNodeInstance;
import com.fasterxml.jackson.databind.ObjectMapper;

class WorkflowTodoIdCodecTest {
	private final WorkflowTodoIdCodec codec = new WorkflowTodoIdCodec(new ObjectMapper());

	@Test
	void encodeAndDecodeRoundTrip() {
		WorkflowInstance instance = new WorkflowInstance();
		instance.setProcessId("process:123");
		instance.setCurrentNodeIndex(2);

		WorkflowNodeInstance node = new WorkflowNodeInstance();
		node.setNodeId("audit/2");

		String todoId = codec.encode(instance, node, "user+name@example.com");

		assertThat(todoId).startsWith("td1_");
		assertThat(todoId).doesNotContain("+", "/", "=");

		WorkflowTodoToken token = codec.decode(todoId);
		assertThat(token.version()).isEqualTo(1);
		assertThat(token.processId()).isEqualTo("process:123");
		assertThat(token.currentNodeIndex()).isEqualTo(2);
		assertThat(token.currentNodeId()).isEqualTo("audit/2");
		assertThat(token.operator()).isEqualTo("user+name@example.com");
	}

	@Test
	void decodeRejectsInvalidTodoId() {
		assertThatThrownBy(() -> codec.decode("bad-token"))
				.isInstanceOf(IllegalArgumentException.class)
				.hasMessageContaining("Invalid workflow todo id");
	}
}
