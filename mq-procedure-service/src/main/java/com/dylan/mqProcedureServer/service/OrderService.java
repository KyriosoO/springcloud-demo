package com.dylan.mqprocedureserver.service;

import java.util.Map;
import java.util.concurrent.CompletableFuture;

import org.apache.rocketmq.client.exception.MQBrokerException;
import org.apache.rocketmq.client.exception.MQClientException;
import org.apache.rocketmq.remoting.exception.RemotingException;
import org.apache.rocketmq.spring.core.RocketMQTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.stereotype.Service;

import com.dylan.common.kafka.util.KryoUtils;
import com.dylan.order.api.model.OrderMessage;
import com.dylan.order.api.model.OrderResult;
import com.dylan.order.api.model.OrderStatus;
import com.dylan.common.redis.lock.DistributedLock;
import com.dylan.common.redis.service.RedisService;
import com.dylan.mqprocedureserver.ws.MqProcedureWsSender;
import com.dylan.mqprocedureserver.model.OrderResp;
import com.dylan.mqprocedureserver.support.CreateOrderSupport;
import com.fasterxml.jackson.core.JsonProcessingException;

@Service
public class OrderService {
	public static final String ORDER_KEY_PREFIX = "order:";
	public static final String ORDER_TIMEOUT_PREFIX = "timeout:";
	@Autowired
	private RocketMQTemplate rocketMQTemplate;
	@Autowired
	private RedisService redisService;
	@Autowired
	MqProcedureWsSender mqProcedureWsSender;
	@Autowired
	CreateOrderSupport orderSupport;
	@Autowired(required = false)
	private com.dylan.mqprocedureserver.disruptor.CreateOrderDisruptor createOrderDisruptor;

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
		System.out.println("发送事务消息 " + message.getOrderId());
	}

	// 创建订单
	@DistributedLock(key = "#userId + ':' + #productId")
	public OrderResp createOrder(String userId, Integer quantity, String productId, java.math.BigDecimal amount)
			throws JsonProcessingException, MQClientException, RemotingException, MQBrokerException,
			InterruptedException {
		// 若 Disruptor 可用，走 RingBuffer 零 GC 路径（秒杀优化）；否则降级为直接创建
		if (createOrderDisruptor != null) {
			return createOrderDisruptor.createOrder(userId, productId, quantity, amount);
		}
		// 降级路径：直接创建（无 Disruptor 时的 fallback）
		return createOrderFallback(userId, quantity, productId, amount);
	}

	private OrderResp createOrderFallback(String userId, Integer quantity, String productId,
			java.math.BigDecimal amount)
			throws MQClientException, RemotingException, MQBrokerException, InterruptedException {
		if (null == redisService.get("stock:1001")) {
			redisService.set("stock:1001", 20);// 模拟库存
		}
		String orderId = "O" + System.currentTimeMillis();
		OrderMessage order = new OrderMessage();
		order.reset(orderId, userId, productId, quantity, amount, null);
		// 1. 写入 Redis
		orderSupport.saveOrderToRedis(order);
		CompletableFuture.runAsync(() -> {
			try {
				orderSupport.sendOrderCreateMq(order);
			} catch (Exception e) {
				orderSupport.markMqSendFail(orderId);
			}
		});
		return orderSupport.buildAcceptedResp(order);
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
			org.springframework.messaging.Message<String> message = MessageBuilder
					.withPayload(ORDER_KEY_PREFIX + ORDER_TIMEOUT_PREFIX + result.getOrderId()).build();
			rocketMQTemplate.syncSend("order-topic:timeout", message, 3000, 16);
			mqProcedureWsSender.sendOrder(order.getUserId(), "ORDER",
					Map.of("orderId", order.getOrderId(), "status", order.getOrderStatus(), "msg", "订单处理成功，等待付款"))
					.subscribe();
		} else {
			// TODO: 可异步落 DB
			mqProcedureWsSender.sendOrder(order.getUserId(), "ORDER",
					Map.of("orderId", order.getOrderId(), "status", order.getOrderStatus(), "msg", result.getReason()))
					.subscribe();
		}
	}

	@DistributedLock(prefix = ORDER_KEY_PREFIX, key = "#orderId")
	public void handlerOrderTimeout(String orderId) {
		String key = ORDER_KEY_PREFIX + orderId;
		OrderMessage order = (OrderMessage) redisService.get(key);
		if (order == null || !OrderStatus.UNPAID.name().equals(order.getOrderStatus())) {
			return;
		}
		order.setOrderStatus("CLOSED");
		redisService.set(key, order);
		System.out.println("订单关闭");
		// 发送退库消息
		rocketMQTemplate.convertAndSend("order-topic:rollback", order);
		// TODO: 可异步落 DB
		mqProcedureWsSender.sendOrder(order.getUserId(), "ORDER",
				Map.of("orderId", order.getOrderId(), "status", order.getOrderStatus(), "msg", "订单超时已关闭")).subscribe();
	}
}
