package com.dylan.workflow.engine;

import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import com.dylan.workflow.dao.WorkflowOutboxRepository;
import com.dylan.workflow.model.WorkflowActionType;
import com.dylan.workflow.model.WorkflowOutboxEvent;
import com.dylan.workflow.model.WorkflowOutboxStatus;
import com.dylan.workflow.web.WorkflowActionMessage;

@Service
public class WorkflowActionService {
	private static final Logger log = LoggerFactory.getLogger(WorkflowActionService.class);

	private final WorkflowActionDispatchChain dispatchChain;
	private final WorkflowOutboxRepository outboxRepository;

	public WorkflowActionService(WorkflowActionDispatchChain dispatchChain, WorkflowOutboxRepository outboxRepository) {
		this.dispatchChain = dispatchChain;
		this.outboxRepository = outboxRepository;
	}

	/**
	 * 在 WorkflowEngine 的同一事务中同步创建并持久化 outbox 行。
	 * <p>
	 * 这保证 outbox 事实与工作流状态变更是原子性的——两者要么一起提交，
	 * 要么一起回滚。消除了此前 @Async 延迟创建 outbox 行时可能丢事件的窗口。
	 *
	 * @return 已持久化的事件 ID
	 */
	public WorkflowOutboxEvent createOutboxEvent(String actionName, String processId, String domain,
			String businessId, WorkflowActionType actionType, Object payload, String operator) {
		String eventId = UUID.randomUUID().toString();
		WorkflowActionMessage message = new WorkflowActionMessage();
		message.setEventId(eventId);
		message.setActionName(actionName);
		message.setProcessId(processId);
		message.setDomain(domain);
		message.setBusinessId(businessId);
		message.setActionType(actionType);
		message.setPayload(payload);
		message.setOperator(operator);

		WorkflowOutboxEvent event = new WorkflowOutboxEvent();
		event.setEventId(eventId);
		event.setMessage(message);
		outboxRepository.save(event); // 在当前事务中同步持久化
		return event;
	}

	/**
	 * 异步发布 outbox 事件给外部 broker（Kafka）。
	 * <p>
	 * 发布是异步的，因此慢速或不可用的 broker 不会阻塞 WorkflowEngine
	 * 的事务。如果发布失败，事件状态保持 PENDING 以供 retryOutboxEvents 重试。
	 */
	@Async("workflowAsyncExecutor")
	public void publishAsync(WorkflowOutboxEvent event) {
		try {
			publish(event);
		} catch (Exception e) {
			log.error("Workflow action publish failed, eventId={}", event.getEventId(), e);
		}
	}

	/**
	 * 定时重投本地 Outbox 中尚未成功投递的事件。
	 */
	@Scheduled(fixedDelayString = "${workflow.action.outbox-retry-delay-ms:5000}")
	public void retryOutboxEvents() {
		for (WorkflowOutboxEvent event : outboxRepository.findRetryable()) {
			try {
				publish(event);
			} catch (Exception e) {
				log.error("Workflow outbox retry failed, eventId={}", event.getEventId(), e);
			}
		}
	}

	private void publish(WorkflowOutboxEvent event) {
		event.setAttempts(event.getAttempts() + 1);
		try {
			dispatchChain.dispatch(event);
			event.setStatus(WorkflowOutboxStatus.DISPATCHED);
			event.setLastError(null);
			outboxRepository.save(event);
		} catch (RuntimeException e) {
			event.setStatus(WorkflowOutboxStatus.FAILED);
			event.setLastError(e.getMessage());
			outboxRepository.save(event);
			throw e;
		}
	}
}
