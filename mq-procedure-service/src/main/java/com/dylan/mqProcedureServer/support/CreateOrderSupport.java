package com.dylan.mqprocedureserver.support;

import org.apache.rocketmq.client.exception.MQBrokerException;
import org.apache.rocketmq.client.exception.MQClientException;
import org.apache.rocketmq.common.message.Message;
import org.apache.rocketmq.remoting.exception.RemotingException;
import org.apache.rocketmq.spring.core.RocketMQTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import com.dylan.common.kafka.util.KryoUtils;
import com.dylan.order.api.model.OrderMessage;
import com.dylan.order.api.model.OrderStatus;
import com.dylan.common.redis.service.RedisService;
import com.dylan.mqprocedureserver.model.OrderResp;
import com.dylan.mqprocedureserver.service.OrderService;

@Component
public class CreateOrderSupport {
	@Autowired
	RedisService redisService;
	@Autowired
	RocketMQTemplate rocketMQTemplate;

	public OrderMessage buildOrder(String userId, Integer quantity, String productId, String orderId) {
		OrderMessage order = new OrderMessage();
		order.reset(orderId, userId, productId, quantity, null);
		return order;
	}

	public void saveOrderToRedis(OrderMessage order) {
		redisService.set(OrderService.ORDER_KEY_PREFIX + order.getOrderId(), order);
	}

	public void sendOrderCreateMq(OrderMessage order)
			throws MQClientException, RemotingException, MQBrokerException, InterruptedException {
		byte[] payload = KryoUtils.serialize(order);
		Message msg = new Message("order-topic", "create", payload);
		msg.setKeys(order.getOrderId());
		rocketMQTemplate.getProducer().send(msg);
	}

	public void markMqSendFail(String orderId) {
		OrderMessage latest = (OrderMessage) redisService.get(OrderService.ORDER_KEY_PREFIX + orderId);
		if (latest != null) {
			latest.setOrderStatus(OrderStatus.FAIL.name());
			redisService.set(OrderService.ORDER_KEY_PREFIX + orderId, latest);
		}
	}

	public OrderResp buildAcceptedResp(OrderMessage order) {
		return new OrderResp(order.getOrderId(), order.getUserId(), "订单已受理，处理中..");
	}
}
