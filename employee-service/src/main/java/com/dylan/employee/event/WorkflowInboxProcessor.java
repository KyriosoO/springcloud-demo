package com.dylan.employee.event;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import com.dylan.employee.dao.EmployeeWorkflowInboxRepository;
import com.dylan.employee.model.EmployeeWorkflowInboxMessage;
import com.dylan.employee.service.EmployeeService;

/**
 * 定时重放员工服务 Inbox 中尚未处理成功的工作流事件。
 */
@Component
public class WorkflowInboxProcessor {
	private static final Logger log = LoggerFactory.getLogger(WorkflowInboxProcessor.class);

	private final EmployeeWorkflowInboxRepository inboxRepository;
	private final EmployeeService employeeService;

	public WorkflowInboxProcessor(EmployeeWorkflowInboxRepository inboxRepository, EmployeeService employeeService) {
		this.inboxRepository = inboxRepository;
		this.employeeService = employeeService;
	}

	@Scheduled(fixedDelayString = "${employee.workflow.inbox-retry-delay-ms:5000}")
	public void retryInboxMessages() {
		for (EmployeeWorkflowInboxMessage message : inboxRepository.findRetryable()) {
			try {
				employeeService.processWorkflowInboxMessage(message);
			} catch (RuntimeException e) {
				log.error("Employee workflow inbox retry failed, eventId={}", message.getEventId(), e);
			}
		}
	}
}
