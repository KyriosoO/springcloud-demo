package com.dylan.workflow.engine;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.dylan.workflow.dao.WorkflowDefinitionRepository;
import com.dylan.workflow.dao.WorkflowInstanceRepository;
import com.dylan.workflow.model.WorkflowApprovalType;
import com.dylan.workflow.model.WorkflowActionType;
import com.dylan.workflow.model.WorkflowDefinition;
import com.dylan.workflow.model.WorkflowInstance;
import com.dylan.workflow.model.WorkflowNodeDefinition;
import com.dylan.workflow.model.WorkflowNodeInstance;
import com.dylan.workflow.model.WorkflowNodeStatus;
import com.dylan.workflow.model.WorkflowOutboxEvent;
import com.dylan.workflow.model.WorkflowRequest;
import com.dylan.workflow.model.WorkflowStatus;
import com.dylan.workflow.support.WorkflowTodoIdCodec;
import com.dylan.workflow.support.WorkflowTodoToken;

/**
 * 轻量流程引擎，负责创建流程实例、记录审批动作并推进节点。
 */
@Service
public class WorkflowEngine {

	@Autowired
	WorkflowInstanceRepository repository;
	@Autowired
	WorkflowDefinitionRepository definitionRepository;
	@Autowired
	WorkflowActionService actionService;
	@Autowired
	WorkflowTodoIdCodec todoIdCodec;

	/**
	 * 创建流程实例，并初始化第一个待审批节点。
	 * <p>
	 * Outbox 行与流程实例在同一事务中持久化，保证原子性。
	 * 实际的 Kafka 发布是异步的（publishAsync），不会被事务阻塞。
	 */
	@Transactional
	public String submit(WorkflowRequest request) {
		WorkflowInstance instance = new WorkflowInstance();
		instance.setProcessId(UUID.randomUUID().toString());
		instance.setDomain(request.getDomain());
		instance.setOperationType(request.getOperationType());
		instance.setBusinessId(request.getBusinessId());
		instance.setSubmitAction(request.getSubmitAction());
		instance.setStatus(WorkflowStatus.SUBMITTED);
		instance.setPayload(request.getPayload());
		instance.setOperator(request.getOperator());
		instance.setNodes(buildNodeInstances(resolveDefinition(request)));
		instance.setCurrentNodeIndex(0);
		repository.save(instance);
		if (request.getSubmitAction() != null && !request.getSubmitAction().isBlank()) {
			WorkflowOutboxEvent event = actionService.createOutboxEvent(request.getSubmitAction(),
					instance.getProcessId(), instance.getDomain(), instance.getBusinessId(),
					WorkflowActionType.SUBMIT, request.getPayload(), request.getOperator());
			actionService.publishAsync(event);
		}

		return instance.getProcessId();
	}

	/**
	 * 当前操作人同意当前节点；节点满足审批策略后自动推进到下一节点或结束流程。
	 */
	@Transactional
	public void approve(String processId, String operator) {
		approve(processId, operator, null);
	}

	@Transactional
	public void approve(String processId, String operator, String todoId) {
		WorkflowInstance instance = repository.findById(processId);
		ensureProcessActive(instance);
		WorkflowNodeInstance currentNode = hasText(todoId) ? currentNodeForTodo(instance) : currentNode(instance);
		ensureOperatorAllowed(currentNode, operator);
		if (hasText(todoId)) {
			ensureTodoMatches(todoId, processId, operator, instance, currentNode);
		}
		if (!currentNode.getApprovedOperators().add(operator)) {
			throw new IllegalStateException("Operator already approved current node: " + operator);
		}

		instance.setOperator(operator);
		if (isNodeApproved(currentNode)) {
			currentNode.setStatus(WorkflowNodeStatus.APPROVED);
			dispatchOutbox(currentNode.getApproveAction(), instance, WorkflowActionType.APPROVE, operator);
			moveToNextNodeOrComplete(instance);
		}
		repository.update(instance);
	}

	/**
	 * 当前操作人拒绝当前节点；拒绝会直接终止整个流程。
	 */
	@Transactional
	public void reject(String processId, String operator) {
		reject(processId, operator, null);
	}

	@Transactional
	public void reject(String processId, String operator, String todoId) {
		WorkflowInstance instance = repository.findById(processId);
		ensureProcessActive(instance);
		WorkflowNodeInstance currentNode = hasText(todoId) ? currentNodeForTodo(instance) : currentNode(instance);
		ensureOperatorAllowed(currentNode, operator);
		if (hasText(todoId)) {
			ensureTodoMatches(todoId, processId, operator, instance, currentNode);
		}
		currentNode.getRejectedOperators().add(operator);
		currentNode.setStatus(WorkflowNodeStatus.REJECTED);
		instance.setStatus(WorkflowStatus.REJECTED);
		instance.setCurrentNodeIndex(-1);
		instance.setOperator(operator);
		repository.update(instance);
		dispatchOutbox(currentNode.getRejectAction(), instance, WorkflowActionType.REJECT, operator);
	}

	/**
	 * 查询流程实例详情。
	 */
	public WorkflowInstance detail(String processId) {
		return repository.findById(processId);
	}

	/**
	 * 查询指定操作人的待办流程，只返回当前节点仍需该操作人处理的实例。
	 */
	public List<WorkflowInstance> todos(String operator) {
		if (!hasText(operator)) {
			throw new IllegalArgumentException("Operator is required");
		}
		return repository.findAll().stream().filter(instance -> isTodoOf(instance, operator)).toList();
	}

	public WorkflowInstance resolveTodo(String todoId, String operator) {
		if (!hasText(operator)) {
			throw new IllegalArgumentException("Operator is required");
		}
		WorkflowTodoToken token = todoIdCodec.decode(todoId);
		WorkflowInstance instance = repository.findById(token.processId());
		if (instance.getStatus() != WorkflowStatus.SUBMITTED) {
			throw todoChanged();
		}
		WorkflowNodeInstance currentNode = currentNodeForTodo(instance);
		ensureTodoMatches(token, token.processId(), operator, instance, currentNode);
		return instance;
	}

	/**
	 * 根据业务类型解析后端维护的流程定义。
	 */
	private WorkflowDefinition resolveDefinition(WorkflowRequest request) {
		if (!hasText(request.getDomain())) {
			throw new IllegalArgumentException("Business type is required");
		}
		return definitionRepository.findByWorkflowDefinitionKey(request.getDomain() + "-" +request.getOperationType());
	}

	/**
	 * 将流程定义中的节点配置转换为运行态节点。
	 */
	private List<WorkflowNodeInstance> buildNodeInstances(WorkflowDefinition definition) {
		List<WorkflowNodeDefinition> definitions = definition.getNodes();
		if (definitions == null || definitions.isEmpty()) {
			throw new IllegalArgumentException("Workflow definition nodes are required: " + definition.getDefinitionKey());
		}

		List<WorkflowNodeInstance> nodes = new ArrayList<>();
		for (int i = 0; i < definitions.size(); i++) {
			WorkflowNodeDefinition nodeDefinition = definitions.get(i);
			WorkflowNodeInstance node = new WorkflowNodeInstance();
			node.setNodeId(hasText(nodeDefinition.getNodeId()) ? nodeDefinition.getNodeId() : "node-" + (i + 1));
			node.setNodeName(hasText(nodeDefinition.getNodeName()) ? nodeDefinition.getNodeName() : "审批节点" + (i + 1));
			node.setApprovalType(nodeDefinition.getApprovalType() == null ? WorkflowApprovalType.SINGLE
					: nodeDefinition.getApprovalType());
			node.setApprovers(nodeDefinition.getApprovers() == null ? new ArrayList<>()
					: new ArrayList<>(nodeDefinition.getApprovers()));
			node.setApproveAction(nodeDefinition.getApproveAction());
			node.setRejectAction(nodeDefinition.getRejectAction());
			validateNode(node);
			nodes.add(node);
		}
		return nodes;
	}

	/**
	 * 校验节点配置，避免会签/或签没有审批人导致策略无法判断。
	 */
	private void validateNode(WorkflowNodeInstance node) {
		if ((node.getApprovalType() == WorkflowApprovalType.COUNTERSIGN
				|| node.getApprovalType() == WorkflowApprovalType.OR_SIGN) && node.getApprovers().isEmpty()) {
			throw new IllegalArgumentException("Approvers are required for node: " + node.getNodeId());
		}
	}

	/**
	 * 读取当前待处理节点。
	 */
	private WorkflowNodeInstance currentNode(WorkflowInstance instance) {
		int index = instance.getCurrentNodeIndex();
		if (index < 0 || index >= instance.getNodes().size()) {
			throw new IllegalStateException("Workflow has no pending node: " + instance.getProcessId());
		}
		return instance.getNodes().get(index);
	}

	private WorkflowNodeInstance currentNodeForTodo(WorkflowInstance instance) {
		int index = instance.getCurrentNodeIndex();
		if (index < 0 || index >= instance.getNodes().size()) {
			throw todoChanged();
		}
		return instance.getNodes().get(index);
	}

	/**
	 * 判断流程当前节点是否属于指定操作人的待办。
	 */
	private boolean isTodoOf(WorkflowInstance instance, String operator) {
		if (instance.getStatus() != WorkflowStatus.SUBMITTED) {
			return false;
		}
		WorkflowNodeInstance node = currentNode(instance);
		return isTodoOf(node, operator);
	}

	private boolean isTodoOf(WorkflowNodeInstance node, String operator) {
		boolean operatorAllowed = node.getApprovers().isEmpty() || node.getApprovers().contains(operator);
		boolean operatorHandled = node.getApprovedOperators().contains(operator)
				|| node.getRejectedOperators().contains(operator);
		return operatorAllowed && !operatorHandled;
	}

	private void ensureTodoMatches(String todoId, String processId, String operator, WorkflowInstance instance,
			WorkflowNodeInstance currentNode) {
		ensureTodoMatches(todoIdCodec.decode(todoId), processId, operator, instance, currentNode);
	}

	private void ensureTodoMatches(WorkflowTodoToken token, String processId, String operator,
			WorkflowInstance instance, WorkflowNodeInstance currentNode) {
		if (!Objects.equals(token.processId(), processId)
				|| !Objects.equals(token.processId(), instance.getProcessId())
				|| !Objects.equals(token.operator(), operator)
				|| token.currentNodeIndex() != instance.getCurrentNodeIndex()
				|| !Objects.equals(token.currentNodeId(), currentNode.getNodeId())
				|| !isTodoOf(currentNode, operator)) {
			throw todoChanged();
		}
	}

	/**
	 * 校验流程是否仍可审批。
	 */
	private void ensureProcessActive(WorkflowInstance instance) {
		if (instance.getStatus() != WorkflowStatus.SUBMITTED) {
			throw new IllegalStateException("Workflow is already finished: " + instance.getProcessId());
		}
	}

	/**
	 * 校验当前操作人是否在节点审批人范围内。
	 */
	private void ensureOperatorAllowed(WorkflowNodeInstance node, String operator) {
		if (!hasText(operator)) {
			throw new IllegalArgumentException("Operator is required");
		}
		if (!node.getApprovers().isEmpty() && !node.getApprovers().contains(operator)) {
			throw new IllegalArgumentException("Operator is not allowed for current node: " + operator);
		}
	}

	/**
	 * 按节点审批策略判断当前节点是否已通过。
	 */
	private boolean isNodeApproved(WorkflowNodeInstance node) {
		if (node.getApprovalType() == WorkflowApprovalType.COUNTERSIGN) {
			return node.getApprovedOperators().containsAll(node.getApprovers());
		}
		return !node.getApprovedOperators().isEmpty();
	}

	/**
	 * 节点通过后推进下一个节点；没有后续节点时结束流程。
	 */
	private void moveToNextNodeOrComplete(WorkflowInstance instance) {
		int nextIndex = instance.getCurrentNodeIndex() + 1;
		if (nextIndex >= instance.getNodes().size()) {
			instance.setStatus(WorkflowStatus.APPROVED);
			instance.setCurrentNodeIndex(-1);
			return;
		}
		instance.setCurrentNodeIndex(nextIndex);
		instance.setStatus(WorkflowStatus.SUBMITTED);
	}

	/**
	 * 在事务内同步创建 outbox 行，随后异步发布到外部 broker。
	 * <p>
	 * outbox 行的持久化与工作流状态变更在同一事务中——保证原子性。
	 * 实际的 Kafka 发布仅在新事务提交后才异步触发，因此 broker
	 * 故障不会回滚工作流状态，也无法造成幽灵 outbox 事件。
	 */
	private void dispatchOutbox(String actionName, WorkflowInstance instance, WorkflowActionType actionType,
			String operator) {
		if (hasText(actionName)) {
			WorkflowOutboxEvent event = actionService.createOutboxEvent(actionName, instance.getProcessId(),
					instance.getDomain(), instance.getBusinessId(), actionType, instance.getPayload(), operator);
			actionService.publishAsync(event);
		}
	}

	private boolean hasText(String value) {
		return value != null && !value.isBlank();
	}

	private WorkflowTodoChangedException todoChanged() {
		return new WorkflowTodoChangedException(
				"Workflow todo has changed or is no longer assigned to current operator");
	}
}
