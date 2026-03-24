package com.dylan.mqConsumerServer.service;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

import com.dylan.common.model.trans.TransactionLog;
import com.dylan.mqConsumerServer.support.TransBatchService;

@Component
public class TransactionOperKafkaConsumer {

	@Autowired
	TransBatchService transBatchService;

	@KafkaListener(topics = "transaction-topic", groupId = "transaction-consumer-group", containerFactory = "kafkaListenerContainerFactory")
	public void onMessage(List<TransactionLog> logs) {
		transBatchService.kafkaFlushBatch(logs);
	}
}
