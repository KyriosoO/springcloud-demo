package com.dylan.mqConsumerServer.service;

import org.apache.rocketmq.spring.annotation.ConsumeMode;
import org.apache.rocketmq.spring.annotation.RocketMQMessageListener;
import org.apache.rocketmq.spring.core.RocketMQListener;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import com.dylan.common.model.trans.TransactionLog;
import com.dylan.mqConsumerServer.support.TransBatchService;

@Service
@EnableScheduling
@RocketMQMessageListener(topic = "transaction-topic", consumerGroup = "transaction-consumer-group", consumeMode = ConsumeMode.ORDERLY)
public class TransactionOperMQConsumer implements RocketMQListener<TransactionLog> {

	@Autowired
	TransBatchService transBatchService;

	private static final int BATCH_SIZE = 100;

	@Override
	public void onMessage(TransactionLog log) {
		transBatchService.mqFlushBatch(false, BATCH_SIZE, log);
	}

// 定时 flush，防止长时间不满 BATCH_SIZE
	@Scheduled(fixedDelay = 10000)
	public void flushBatchByTime() {
		transBatchService.mqFlushBatch(true, BATCH_SIZE, null);
	}
}
