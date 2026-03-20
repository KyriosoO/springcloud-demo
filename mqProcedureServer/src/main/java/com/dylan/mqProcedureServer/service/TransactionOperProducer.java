package com.dylan.mqProcedureServer.service;

import org.apache.rocketmq.spring.core.RocketMQTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.stereotype.Service;

import com.dylan.common.model.trans.TransactionLog;
import com.dylan.common.redis.service.RedisService;

@Service
public class TransactionOperProducer {
	@Autowired
	private RedisService redisService;

	@Autowired
	private RocketMQTemplate rocketMQTemplate;

	public void submitOperation(TransactionLog op) {
		// 1. 写缓存
		String cacheKey = "txn:" + op.getTransId();
		redisService.rPush(cacheKey, op.getPayload());

		// 2. 顺序发送消息到 MQ（同一 transactionId hashKey 保证顺序消费）
		rocketMQTemplate.syncSendOrderly("transaction-topic", MessageBuilder.withPayload(op).build(), op.getTransId() // 同交易顺序消费
		);
	}
}
