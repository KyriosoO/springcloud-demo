package com.dylan.workflow.engine;

import java.util.concurrent.ExecutionException;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

import com.dylan.common.kafka.util.KryoUtils;
import com.dylan.workflow.model.WorkflowOutboxEvent;

/**
 * Kafka 动作事件分发器，负责把 Outbox 事件投递到 MQ。
 */
@Component
public class KafkaWorkflowActionDispatcher implements WorkflowActionDispatcher {
	private final KafkaTemplate<String, byte[]> kafkaTemplate;
	private String topic;

	public KafkaWorkflowActionDispatcher(@Qualifier("byteKafkaTemplate") KafkaTemplate<String, byte[]> kafkaTemplate,
			@Value("${workflow.action.topic:workflow-action-@-topic}") String topic) {
		this.kafkaTemplate = kafkaTemplate;
		this.topic = topic;
	}

	@Override
	public String name() {
		return "kafka";
	}

	@Override
	public void dispatch(WorkflowOutboxEvent event) {
		try {
			topic = topic.replace("@", event.getMessage().getDomain());
			kafkaTemplate.send(topic, event.getMessage().getBusinessId(), KryoUtils.serialize(event.getMessage())).get();
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			throw new IllegalStateException("Workflow action dispatch interrupted: " + event.getEventId(), e);
		} catch (ExecutionException e) {
			throw new IllegalStateException("Workflow action dispatch failed: " + event.getEventId(), e);
		}
	}
}
