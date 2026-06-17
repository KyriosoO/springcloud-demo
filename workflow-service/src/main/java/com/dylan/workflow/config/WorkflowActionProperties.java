package com.dylan.workflow.config;

import java.util.ArrayList;
import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 工作流动作分发配置。
 */
@ConfigurationProperties(prefix = "workflow.action")
public class WorkflowActionProperties {
	/**
	 * 按顺序执行的 dispatcher 名称，例如 log、kafka。
	 */
	private List<String> dispatchers = new ArrayList<>(List.of("kafka"));

	public List<String> getDispatchers() {
		return dispatchers;
	}

	public void setDispatchers(List<String> dispatchers) {
		this.dispatchers = dispatchers;
	}
}
