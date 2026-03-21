package com.dylan.mqConsumerServer.service;

import org.apache.rocketmq.spring.annotation.RocketMQMessageListener;
import org.apache.rocketmq.spring.core.RocketMQListener;
import org.apache.rocketmq.spring.core.RocketMQTemplate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import com.dylan.common.model.order.OrderMessage;
import com.dylan.common.model.order.OrderResult;

@Service
@RocketMQMessageListener(topic = "order-topic", selectorExpression = "create", consumerGroup = "order-consumer-group")
public class OrderCreateConsumer implements RocketMQListener<OrderMessage> {
	Logger log = LoggerFactory.getLogger(OrderCreateConsumer.class);

	@Autowired
	private RocketMQTemplate rocketMQTemplate;
	@Autowired
	private StockOperService stockOperService;

	// 消息批量累积
	private int batch = 0;

	// 消费订单消息
	@Override
	public void onMessage(OrderMessage order) {
		StockOperService.DeductResult result = stockOperService.deductStock(order.getProductId(), order.getOrderId(),
				order.getQuantity());
		System.out.println(batch);
		if (batch < 8) {
			batch ++;
			throw new RuntimeException();
		}
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