package com.dylan.workflow.controller;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.workflow.engine.WorkflowEngine;
import com.dylan.workflow.model.WorkflowInstance;
import com.dylan.workflow.model.WorkflowNodeInstance;
import com.dylan.workflow.model.WorkflowRequest;
import com.dylan.workflow.support.WorkflowTodoIdCodec;
import com.dylan.workflow.web.WorkflowDetailResponse;
import com.dylan.workflow.web.WorkflowNodeDetailResponse;
import com.dylan.workflow.web.WorkflowOperationRequest;
import com.dylan.workflow.web.WorkflowSubmitResponse;
import com.dylan.workflow.web.WorkflowTodoResponse;

@RestController
@RequestMapping("/workflows")
public class WorkflowController {
	private final WorkflowEngine workflowEngine;
	private final WorkflowTodoIdCodec todoIdCodec;

	public WorkflowController(WorkflowEngine workflowEngine, WorkflowTodoIdCodec todoIdCodec) {
		this.workflowEngine = workflowEngine;
		this.todoIdCodec = todoIdCodec;
	}

	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	public WorkflowSubmitResponse submit(@RequestBody WorkflowRequest request) {
		String processId = workflowEngine.submit(request);
		return new WorkflowSubmitResponse(processId);
	}

	@PostMapping("/{processId}/approve")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void approve(@PathVariable String processId, @RequestBody(required = false) WorkflowOperationRequest request) {
		workflowEngine.approve(processId, operatorOf(request), todoIdOf(request));
	}

	@PostMapping("/{processId}/reject")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void reject(@PathVariable String processId, @RequestBody(required = false) WorkflowOperationRequest request) {
		workflowEngine.reject(processId, operatorOf(request), todoIdOf(request));
	}

	@GetMapping("/{processId}")
	public WorkflowDetailResponse detail(@PathVariable String processId) {
		WorkflowInstance instance = workflowEngine.detail(processId);
		WorkflowDetailResponse response = new WorkflowDetailResponse();
		response.setProcessId(instance.getProcessId());
		response.setDomain(instance.getDomain());
		response.setOperationType(instance.getOperationType());
		response.setBusinessId(instance.getBusinessId());
		response.setStatus(instance.getStatus());
		response.setOperator(instance.getOperator());
		response.setPayload(instance.getPayload());
		response.setCurrentNodeIndex(instance.getCurrentNodeIndex());
		response.setCurrentNodeId(currentNodeId(instance));
		response.setNodes(instance.getNodes().stream().map(this::toNodeResponse).toList());
		return response;
	}

	@GetMapping("/todos")
	public List<WorkflowTodoResponse> todos(@RequestParam String operator) {
	    return workflowEngine.todos(operator).stream()
	            .map(instance -> toTodoResponse(instance, operator))
	            .toList();
	}

	@GetMapping("/todos/{todoId}")
	public WorkflowTodoResponse resolveTodo(@PathVariable String todoId, @RequestParam String operator) {
		return toTodoResponse(workflowEngine.resolveTodo(todoId, operator), operator);
	}

	private String operatorOf(WorkflowOperationRequest request) {
		return request == null ? null : request.getOperator();
	}

	private String todoIdOf(WorkflowOperationRequest request) {
		return request == null ? null : request.getTodoId();
	}

	/**
	 * 将节点运行态转换成接口响应，避免直接暴露内部实例对象。
	 */
	private WorkflowNodeDetailResponse toNodeResponse(WorkflowNodeInstance node) {
		WorkflowNodeDetailResponse response = new WorkflowNodeDetailResponse();
		response.setNodeId(node.getNodeId());
		response.setNodeName(node.getNodeName());
		response.setApprovalType(node.getApprovalType());
		response.setStatus(node.getStatus());
		response.setApprovers(node.getApprovers());
		response.setApprovedOperators(node.getApprovedOperators().stream().toList());
		response.setRejectedOperators(node.getRejectedOperators().stream().toList());
		return response;
	}

	/**
	 * 获取当前待审批节点 ID；流程结束时返回 null。
	 */
	private String currentNodeId(WorkflowInstance instance) {
		int index = instance.getCurrentNodeIndex();
		if (index < 0 || index >= instance.getNodes().size()) {
			return null;
		}
		return instance.getNodes().get(index).getNodeId();
	}

	private WorkflowNodeInstance currentNode(WorkflowInstance instance) {
		int index = instance.getCurrentNodeIndex();
		if (index < 0 || index >= instance.getNodes().size()) {
			throw new IllegalStateException("Workflow has no pending node: " + instance.getProcessId());
		}
		return instance.getNodes().get(index);
	}
	
	private WorkflowTodoResponse toTodoResponse(WorkflowInstance instance, String operator) {
	    WorkflowNodeInstance currentNode = currentNode(instance);
	    WorkflowTodoResponse response = new WorkflowTodoResponse();
	    response.setTodoId(todoId(instance, currentNode, operator));
	    response.setProcessId(instance.getProcessId());
	    response.setDomain(instance.getDomain());
	    response.setOperationType(instance.getOperationType());
	    response.setBusinessId(instance.getBusinessId());
	    response.setStatus(instance.getStatus());
	    response.setPayload(instance.getPayload());
	    response.setCurrentNodeIndex(instance.getCurrentNodeIndex());
	    response.setCurrentNodeId(currentNode.getNodeId());
	    response.setCurrentNodeName(currentNode.getNodeName());
	    return response;
	}

	private String todoId(WorkflowInstance instance, WorkflowNodeInstance node, String operator) {
	    return todoIdCodec.encode(instance, node, operator);
	}
}
