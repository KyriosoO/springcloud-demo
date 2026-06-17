package com.dylan.mqconsumerserver.service;


import org.apache.rocketmq.common.message.Message;
import org.apache.rocketmq.spring.annotation.RocketMQMessageListener;
import org.apache.rocketmq.spring.core.RocketMQListener;
import org.apache.rocketmq.spring.core.RocketMQTemplate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import com.dylan.common.kafka.util.KryoUtils;
import com.dylan.order.api.model.OrderMessage;
import com.dylan.order.api.model.OrderResult;
import com.dylan.mqconsumerserver.support.StockOperService;

@Service
@RocketMQMessageListener(topic = "order-topic", selectorExpression = "create", consumerGroup = "order-consumer-group")
public class OrderCreateConsumer implements RocketMQListener<Message> {
	Logger log = LoggerFactory.getLogger(OrderCreateConsumer.class);

	@Autowired
	private RocketMQTemplate rocketMQTemplate;
	@Autowired
	private StockOperService stockOperService;

	// 消费订单消息
	@Override
	public void onMessage(Message message) {
		OrderMessage order;
		byte[] payload = message.getBody();
		order = KryoUtils.deserializeGeneric(payload);
		StockOperService.DeductResult result = stockOperService.deductStock(order.getProductId(), order.getOrderId(),
				order.getQuantity());
		switch (result) {
		case SUCCESS:
			rocketMQTemplate.convertAndSend("order-topic:feedback", new OrderResult(order.getOrderId(), "UNPAID"));
			break;
		case OUT_OF_STOCK:
			rocketMQTemplate.convertAndSend("order-topic:feedback",
					new OrderResult(order.getOrderId(), "FAIL", "库存不足"));
			break;
		case ALREADY_PROCESSED:
			// 幂等，什么都不做
			break;
		case STOCK_NOT_EXIST:
			rocketMQTemplate.convertAndSend("order-topic:feedback",
					new OrderResult(order.getOrderId(), "FAIL", "商品已下架"));
			break;
		}
	}
}