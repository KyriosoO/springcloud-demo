package com.dylan.mqProcedureServer.service;

import org.apache.rocketmq.spring.annotation.RocketMQMessageListener;
import org.apache.rocketmq.spring.core.RocketMQListener;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@RocketMQMessageListener(topic = "order-topic", selectorExpression = "timeout", consumerGroup = "order-timeout-group")
@Service
public class OrderTimeoutMQListener implements RocketMQListener<String> {

	@Autowired
	OrderService orderService;

	@Override
	public void onMessage(String message) {
		String expiredKey = message.toString(); // e.g., order:timeout:12345
		if (!expiredKey.startsWith(OrderService.ORDER_KEY_PREFIX + OrderService.ORDER_TIMEOUT_PREFIX)) {
			return;
		}
		String orderId = expiredKey.split(":")[2];
		orderService.handlerOrderTimeout(orderId);
	}

}
