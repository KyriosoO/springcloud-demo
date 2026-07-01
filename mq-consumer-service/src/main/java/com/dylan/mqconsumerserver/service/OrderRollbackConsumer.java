package com.dylan.mqconsumerserver.service;

import org.apache.rocketmq.spring.annotation.RocketMQMessageListener;
import org.apache.rocketmq.spring.core.RocketMQListener;
import org.apache.rocketmq.spring.core.RocketMQTemplate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import com.dylan.order.api.model.OrderMessage;
import com.dylan.order.api.model.OrderResult;
import com.dylan.common.redis.service.RedisService;
import com.dylan.mqconsumerserver.support.StockOperService;

@Service
@RocketMQMessageListener(topic = "order-topic", selectorExpression = "rollback", consumerGroup = "order-fallback-group")
public class OrderRollbackConsumer implements RocketMQListener<OrderMessage> {

	Logger log = LoggerFactory.getLogger(OrderRollbackConsumer.class);

	@Autowired
	private RocketMQTemplate rocketMQTemplate;
	@Autowired
	private StockOperService stockOperService;
	@Autowired
	RedisService redisService;

	// 消费订单消息
	@Override
	public void onMessage(OrderMessage order) {
		StockOperService.IncreaseResult result = stockOperService.increaseStock(order.getProductId(),
				order.getOrderId(), order.getQuantity());
		switch (result) {
		case SUCCESS:
			// 成功，什么都不做
			System.out.println("库存回退成功" + redisService.get("stock:" + order.getProductId()));
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