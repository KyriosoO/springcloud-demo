package com.dylan.employee.event;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import com.dylan.common.kafka.util.KryoUtils;

/**
 * 员工变更事件发布器，在员工数据变化后发送同步消息。
 */
@Service
public class EmployeeChangeEventPublisher {
	private final KafkaTemplate<String, byte[]> kafkaTemplate;
	private final String topic;

	/**
	 * 创建 EmployeeChangeEventPublisher 实例并注入所需依赖。
	 */
	public EmployeeChangeEventPublisher(
			@Qualifier("byteKafkaTemplate") KafkaTemplate<String, byte[]> kafkaTemplate,
			@Value("${employee.kafka.change-topic:employee-change-topic}") String topic) {
		this.kafkaTemplate = kafkaTemplate;
		this.topic = topic;
	}

	/**
	 * 发布业务变更事件。
	 */
	public void publishUpsert(String idCardNo) {
		publish(EmployeeChangeEvent.upsert(idCardNo));
	}

	/**
	 * 发布业务变更事件。
	 */
	public void publishDelete(String idCardNo) {
		publish(EmployeeChangeEvent.delete(idCardNo));
	}

	/**
	 * 发布业务变更事件。
	 */
	private void publish(EmployeeChangeEvent event) {
		kafkaTemplate.send(topic, event.getIdCardNo(), KryoUtils.serialize(event));
	}
}
