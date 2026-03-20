package com.dylan.mqProcedureServer.service;

import org.apache.rocketmq.spring.annotation.RocketMQMessageListener;
import org.apache.rocketmq.spring.core.RocketMQListener;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import com.dylan.common.model.order.OrderResult;
import com.dylan.common.redis.service.RedisService;

@Component
@RocketMQMessageListener(topic = "order-topic", selectorExpression = "feedback", consumerGroup = "stock-feedback-group")
public class OrderStockFeedbackConsumer implements RocketMQListener<OrderResult> {
	Logger log = LoggerFactory.getLogger(OrderStockFeedbackConsumer.class);

	@Autowired
	OrderService orderService;
	@Autowired
	RedisService redisService;

	@Override
	public void onMessage(OrderResult result) {
		orderService.handlerOrderFeedback(result);
	}
}
