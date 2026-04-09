package com.dylan.mqConsumerServer.service;

import java.util.List;
import java.util.stream.Collectors;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

import com.dylan.common.kafka.util.KryoUtils;
import com.dylan.common.model.trans.TransactionLog;
import com.dylan.mqConsumerServer.support.TransBatchService;

@Component
public class TransactionOperKafkaConsumer {

	@Autowired
	TransBatchService transBatchService;
	@Autowired
	private KafkaTemplate<String, Object> objectKafkaTemplate;

	@KafkaListener(topics = "transaction-topic", groupId = "byte-consumer-group", containerFactory = "byteKafkaListenerContainerFactory")
	public void onMessage(List<byte[]> payloads, Acknowledgment ack) {
		List<TransactionLog> logs = payloads.parallelStream().map(KryoUtils::<TransactionLog>deserializeGeneric)
				.collect(Collectors.toList());
		transBatchService.kafkaFlushBatch(logs);
		ack.acknowledge(); // 手动提交 offset
	}
}
