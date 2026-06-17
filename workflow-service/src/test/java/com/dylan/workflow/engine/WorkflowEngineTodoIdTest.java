package com.dylan.workflow.engine;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.dylan.workflow.dao.WorkflowDefinitionRepository;
import com.dylan.workflow.dao.WorkflowInstanceRepository;
import com.dylan.workflow.model.WorkflowApprovalType;
import com.dylan.workflow.model.WorkflowInstance;
import com.dylan.workflow.model.WorkflowNodeInstance;
import com.dylan.workflow.model.WorkflowStatus;
import com.dylan.workflow.support.WorkflowTodoIdCodec;
import com.fasterxml.jackson.databind.ObjectMapper;

class WorkflowEngineTodoIdTest {
	private WorkflowEngine engine;
	private WorkflowInstanceRepository repository;
	private WorkflowTodoIdCodec codec;

	@BeforeEach
	void setUp() {
		repository = mock(WorkflowInstanceRepository.class);
		codec = new WorkflowTodoIdCodec(new ObjectMapper());
		engine = new WorkflowEngine();
		engine.repository = repository;
		engine.definitionRepository = mock(WorkflowDefinitionRepository.class);
		engine.actionService = mock(WorkflowActionService.class);
		engine.todoIdCodec = codec;
	}

	@Test
	void resolveTodoReturnsCurrentTodo() {
		WorkflowInstance instance = pendingInstance("process-1", "audit1", "dylan");
		String todoId = codec.encode(instance, instance.getNodes().get(0), "dylan");
		when(repository.findById("process-1")).thenReturn(instance);

		WorkflowInstance resolved = engine.resolveTodo(todoId, "dylan");

		assertThat(resolved).isSameAs(instance);
	}

	@Test
	void approveWithValidTodoIdUpdatesWorkflow() {
		WorkflowInstance instance = pendingInstance("process-1", "audit1", "dylan");
		String todoId = codec.encode(instance, instance.getNodes().get(0), "dylan");
		when(repository.findById("process-1")).thenReturn(instance);

		engine.approve("process-1", "dylan", todoId);

		assertThat(instance.getNodes().get(0).getApprovedOperators()).containsExactly("dylan");
		assertThat(instance.getStatus()).isEqualTo(WorkflowStatus.APPROVED);
		assertThat(instance.getCurrentNodeIndex()).isEqualTo(-1);
		verify(repository).update(instance);
	}

	@Test
	void approveWithChangedTodoIdFails() {
		WorkflowInstance oldInstance = pendingInstance("process-1", "audit1", "dylan");
		String staleTodoId = codec.encode(oldInstance, oldInstance.getNodes().get(0), "dylan");

		WorkflowInstance currentInstance = pendingInstance("process-1", "audit2", "dylan");
		when(repository.findById("process-1")).thenReturn(currentInstance);

		assertThatThrownBy(() -> engine.approve("process-1", "dylan", staleTodoId))
				.isInstanceOf(WorkflowTodoChangedException.class)
				.hasMessageContaining("Workflow todo has changed");
	}

	private WorkflowInstance pendingInstance(String processId, String nodeId, String operator) {
		WorkflowNodeInstance node = new WorkflowNodeInstance();
		node.setNodeId(nodeId);
		node.setNodeName(nodeId);
		node.setApprovalType(WorkflowApprovalType.SINGLE);
		node.setApprovers(List.of(operator));

		WorkflowInstance instance = new WorkflowInstance();
		instance.setProcessId(processId);
		instance.setStatus(WorkflowStatus.SUBMITTED);
		instance.setCurrentNodeIndex(0);
		instance.setNodes(List.of(node));
		return instance;
	}
}
