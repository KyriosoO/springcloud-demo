package com.dylan.workflow.model;

import java.util.ArrayList;
import java.util.List;

/**
 * 后端维护的流程定义模板。
 */
public class WorkflowDefinition {
	/**
	 * 流程定义编码，通常与 domain + "-" + operationType 对应。
	 */
	private String definitionKey;
	/**
	 * 流程定义名称，便于管理端展示和排查。
	 */
	private String definitionName;
	/**
	 * 按顺序执行的审批节点配置。
	 */
	private List<WorkflowNodeDefinition> nodes = new ArrayList<>();

	public String getDefinitionKey() {
		return definitionKey;
	}

	public void setDefinitionKey(String definitionKey) {
		this.definitionKey = definitionKey;
	}

	public String getDefinitionName() {
		return definitionName;
	}

	public void setDefinitionName(String definitionName) {
		this.definitionName = definitionName;
	}

	public List<WorkflowNodeDefinition> getNodes() {
		return nodes;
	}

	public void setNodes(List<WorkflowNodeDefinition> nodes) {
		this.nodes = nodes;
	}
}
