package com.dylan.employee.event;

import java.util.List;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

import com.dylan.common.kafka.util.KryoUtils;
import com.dylan.employee.service.EmployeeService;
import com.dylan.workflow.web.WorkflowActionMessage;

/**
 * 工作流动作事件消费者，只负责把 MQ 消息可靠写入 Inbox。
 */
@Component
public class WorkflowActionEventConsumer {
	private final EmployeeService employeeService;

	public WorkflowActionEventConsumer(EmployeeService employeeService) {
		this.employeeService = employeeService;
	}

	@KafkaListener(topics = "${workflow.action.topic:workflow-action-employee-topic}", groupId = "${employee.workflow.action-group:employee-workflow-action-group}", containerFactory = "byteKafkaListenerContainerFactory")
	public void onMessage(List<byte[]> payloads, Acknowledgment ack) {
		for (byte[] payload : payloads) {
			WorkflowActionMessage message = KryoUtils.deserialize(payload, WorkflowActionMessage.class);
			employeeService.acceptWorkflowAction(message);
		}
		ack.acknowledge();
	}
}
