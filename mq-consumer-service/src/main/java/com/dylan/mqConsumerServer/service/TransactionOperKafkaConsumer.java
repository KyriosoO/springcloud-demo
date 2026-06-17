package com.dylan.mqconsumerserver.service;

import java.util.List;
import java.util.stream.Collectors;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

import com.dylan.common.kafka.util.KryoUtils;
import com.dylan.transaction.api.model.TransactionLog;
import com.dylan.mqconsumerserver.support.TransBatchService;

@Component
public class TransactionOperKafkaConsumer {

	@Autowired
	TransBatchService transBatchService;

	@KafkaListener(topics = "transaction-topic", groupId = "byte-consumer-group", containerFactory = "byteKafkaListenerContainerFactory")
	public void onMessage(List<byte[]> payloads, Acknowledgment ack) {
		List<TransactionLog> logs = payloads.stream().map(KryoUtils::<TransactionLog>deserializeGeneric)
				.collect(Collectors.toList());
		transBatchService.kafkaFlushBatch(logs);
		ack.acknowledge(); // 手动提交 offset
	}
}
