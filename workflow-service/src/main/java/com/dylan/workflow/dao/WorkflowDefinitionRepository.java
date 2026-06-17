package com.dylan.workflow.dao;

import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;

import org.springframework.stereotype.Repository;

import com.dylan.workflow.model.WorkflowApprovalType;
import com.dylan.workflow.model.WorkflowDefinition;
import com.dylan.workflow.model.WorkflowNodeDefinition;

/**
 * 本地轻量流程定义仓库；后续可替换为数据库或配置中心实现。
 */
@Repository
public class WorkflowDefinitionRepository {
	/**
	 * 两级会签流程：提交 -> 审核1(会签) -> 审核2(会签) -> 结束。
	 */
	public static final String TWO_LEVEL_COUNTERSIGN = "two-level-countersign";
	/**
	 * 一级或签流程：提交 -> 审核1(或签) -> 结束。
	 */
	public static final String ONE_LEVEL_OR_SIGN = "one-level-or-sign";
	public static final String EMPLOYEE_CREATE = "employee-create";
	public static final String EMPLOYEE_UPDATE = "employee-update";

	/**
	 * 本地流程定义表，key 使用业务类型 domain + "-" + operationType ->workflowDefinitionKey。
	 */
	private final Map<String, WorkflowDefinition> definitions = Map.of(TWO_LEVEL_COUNTERSIGN,
			definition(TWO_LEVEL_COUNTERSIGN, "提交->审核1(会签)->审核2(会签)->结束",
					List.of(node("audit1", "审核1", WorkflowApprovalType.COUNTERSIGN, "dylan", "sherry"),
							node("audit2", "审核2", WorkflowApprovalType.COUNTERSIGN, "reviewer", "admin"))),
			ONE_LEVEL_OR_SIGN,
			definition(ONE_LEVEL_OR_SIGN, "提交->审核1(或签)->结束",
					List.of(node("audit1", "审核1", WorkflowApprovalType.OR_SIGN, "dylan", "sherry"))),
			EMPLOYEE_CREATE,
			definition(EMPLOYEE_CREATE, "员工创建审批",
					List.of(node("audit1", "审核1", WorkflowApprovalType.COUNTERSIGN, "dylan", "sherry"),
							actionNode("audit2", "审核2", WorkflowApprovalType.COUNTERSIGN,
									"employee.change.approved", "reviewer", "admin"))),
			EMPLOYEE_UPDATE,
			definition(EMPLOYEE_UPDATE, "员工更新审批",
					List.of(actionNode("audit1", "审核1", WorkflowApprovalType.OR_SIGN,
							"employee.change.approved", "dylan", "sherry"))));

	/**
	 * 按业务类型获取流程定义。
	 */
	public WorkflowDefinition findByWorkflowDefinitionKey(String workflowDefinitionKey) {
		WorkflowDefinition definition = definitions.get(workflowDefinitionKey);
		if (definition == null) {
			throw new NoSuchElementException("Workflow definition not found for workflowDefinitionKey: " + workflowDefinitionKey);
		}
		return definition;
	}

	private static WorkflowDefinition definition(String definitionKey, String definitionName,
			List<WorkflowNodeDefinition> nodes) {
		WorkflowDefinition definition = new WorkflowDefinition();
		definition.setDefinitionKey(definitionKey);
		definition.setDefinitionName(definitionName);
		definition.setNodes(nodes);
		return definition;
	}

	private static WorkflowNodeDefinition node(String nodeId, String nodeName, WorkflowApprovalType approvalType,
			String... approvers) {
		WorkflowNodeDefinition node = new WorkflowNodeDefinition();
		node.setNodeId(nodeId);
		node.setNodeName(nodeName);
		node.setApprovalType(approvalType);
		node.setApprovers(List.of(approvers));
		return node;
	}

	private static WorkflowNodeDefinition actionNode(String nodeId, String nodeName, WorkflowApprovalType approvalType,
			String approveAction, String... approvers) {
		WorkflowNodeDefinition node = node(nodeId, nodeName, approvalType, approvers);
		node.setApproveAction(approveAction);
		return node;
	}
}
