package com.dylan.mqProcedureServer.service;

import java.nio.charset.StandardCharsets;
import java.util.UUID;

import org.apache.rocketmq.client.exception.MQBrokerException;
import org.apache.rocketmq.client.exception.MQClientException;
import org.apache.rocketmq.remoting.exception.RemotingException;
import org.apache.rocketmq.spring.core.RocketMQTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.messaging.Message;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.stereotype.Service;

import com.dylan.common.model.order.OrderMessage;
import com.dylan.common.model.order.OrderResult;
import com.dylan.common.model.order.OrderStatus;
import com.dylan.common.redis.lock.DistributedLock;
import com.dylan.common.redis.service.RedisService;

@Service
public class OrderService {
	public static final String ORDER_KEY_PREFIX = "order:";
	public static final String ORDER_TIMEOUT_PREFIX = "tiemout:";
	@Autowired
	private RocketMQTemplate rocketMQTemplate;
	@Autowired
	private RedisService redisService;

	// 发送普通消息
	public void send(String topic, String msg) {
		rocketMQTemplate.convertAndSend(topic, msg);
	}

	// 发送对象消息
	public void sendObject(String topic, OrderMessage message) {
		rocketMQTemplate.convertAndSend(topic, message);
	}

	// tx增强的
	public void sendOrderTx(String topic, OrderMessage message) {
		rocketMQTemplate.sendMessageInTransaction(topic, MessageBuilder.withPayload(message).build(),
				message.getOrderId());
		System.out.println("发送事务消息: " + message.getOrderId());
	}

	// 创建订单
	@DistributedLock(key = "#userId + ':' + #productId")
	public String createOrder(String userId, Integer quantity, String productId) {
		redisService.set("stock:1001", 20);
		String orderId = UUID.randomUUID().toString();
		OrderMessage order = new OrderMessage(orderId, userId, productId, quantity, "PEDDING");
		// 1. 写入 Redis
		redisService.set(ORDER_KEY_PREFIX + orderId, order);
		// 2. 发送 MQ
		rocketMQTemplate.convertAndSend("order-topic:create", order);
		return "下单成功，处理中..." + "订单Id:" + orderId;
	}

	@DistributedLock(key = "#result.orderId")
	public void handlerOrderFeedback(OrderResult result) {
		String key = ORDER_KEY_PREFIX + result.getOrderId();
		OrderMessage order = (OrderMessage) redisService.get(key);
		if (order == null) {
			return;
		}
		order.setOrderStatus(result.getStatus());
		redisService.set(key, order);
		if (result.getStatus().equals(OrderStatus.UNPAID.name())) {
			// 设置 TTL 自动取消（例如 30 分钟）
			String timeoutKey = ORDER_KEY_PREFIX + ORDER_TIMEOUT_PREFIX + result.getOrderId();
			redisService.set(timeoutKey, result.getOrderId(), 60);
			// 设置超时mq消息
			Message<String> message = MessageBuilder
					.withPayload(ORDER_KEY_PREFIX + ORDER_TIMEOUT_PREFIX + result.getOrderId()).build();
			rocketMQTemplate.syncSend("order-topic:timeout", message, 3000, 16);
		} else {
			// TODO: 可异步落库 DB

		}
	}

	@DistributedLock(prefix = ORDER_KEY_PREFIX, key = "#orderId")
	public void handlerOrderTimeout(String orderId) {
		String key = ORDER_KEY_PREFIX + orderId;
		OrderMessage order = (OrderMessage) redisService.get(key);
		if (order == null || order.getOrderStatus() != OrderStatus.UNPAID.name()) {
			return;
		}
		order.setOrderStatus("CLOSED");
		redisService.set(key, order);
		System.out.println("订单关闭");
		// 发送退库消息
		rocketMQTemplate.convertAndSend("order-topic:rollback", order);
		// TODO: 可异步落库 DB
	}
}
