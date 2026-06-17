package com.dylan.mqconsumerserver.service;

import org.apache.rocketmq.spring.annotation.RocketMQMessageListener;
import org.apache.rocketmq.spring.core.RocketMQListener;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
@RocketMQMessageListener(topic = "order-topic", selectorExpression = "txTest", consumerGroup = "tx-consumer-group")
public class TxConsumer implements RocketMQListener<String> {

	Logger log = LoggerFactory.getLogger(TxConsumer.class);

	// 消费订单消息
	@Override
	public void onMessage(String message) {
		System.out.println(message);
	}
}