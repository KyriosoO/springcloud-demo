package com.dylan.mqProcedureServer.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.stereotype.Service;

@Service
public class OrderTimeoutRedisListener implements MessageListener {

	@Autowired
	OrderService orderService;

	@Override
	public void onMessage(Message message, byte[] pattern) {
		String expiredKey = message.toString(); // e.g., order:timeout:12345
		if (!expiredKey.startsWith(OrderService.ORDER_KEY_PREFIX + OrderService.ORDER_TIMEOUT_PREFIX)) {
			return;
		}
		String orderId = expiredKey.split(":")[2];
		orderService.handlerOrderTimeout(orderId);
	}

}
