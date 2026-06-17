package com.dylan.employee.event;

import java.util.List;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

import com.dylan.common.kafka.util.KryoUtils;
import com.dylan.employee.service.EmployeeEsService;

/**
 * 员工变更事件消费者，监听消息并同步 Elasticsearch 索引。
 */
@Component
public class EmployeeChangeEventConsumer {
	private final EmployeeEsService employeeEsService;
	private final String embeddingField;

	/**
	 * 创建 EmployeeChangeEventConsumer 实例并注入所需依赖。
	 */
	public EmployeeChangeEventConsumer(EmployeeEsService employeeEsService,
			@Value("${employee.es.embedding-field:embedding}") String embeddingField) {
		this.employeeEsService = employeeEsService;
		this.embeddingField = embeddingField;
	}

	@KafkaListener(
			topics = "${employee.kafka.change-topic:employee-change-topic}",
			groupId = "${employee.kafka.es-sync-group:employee-es-sync-group}",
			containerFactory = "byteKafkaListenerContainerFactory")
	/**
	 * 处理 onMessage 相关逻辑。
	 */
	public void onMessage(List<byte[]> payloads, Acknowledgment ack) {
		for (byte[] payload : payloads) {
			EmployeeChangeEvent event = KryoUtils.deserialize(payload, EmployeeChangeEvent.class);
			handle(event);
		}
		ack.acknowledge();
	}

	/**
	 * 处理 handle 相关逻辑。
	 */
	private void handle(EmployeeChangeEvent event) {
		if (event == null || event.getIdCardNo() == null || event.getIdCardNo().isBlank()) {
			return;
		}
		if (EmployeeChangeEvent.TYPE_DELETE.equalsIgnoreCase(event.getEventType())) {
			employeeEsService.deleteOne(event.getIdCardNo());
			return;
		}
		if (EmployeeChangeEvent.TYPE_UPSERT.equalsIgnoreCase(event.getEventType())) {
			employeeEsService.indexOne(event.getIdCardNo(), embeddingField, null);
		}
	}
}
