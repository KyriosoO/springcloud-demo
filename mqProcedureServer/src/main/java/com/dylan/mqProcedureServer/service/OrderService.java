package com.dylan.mqProcedureServer.service;

import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

import org.apache.rocketmq.client.exception.MQBrokerException;
import org.apache.rocketmq.client.exception.MQClientException;
import org.apache.rocketmq.common.message.Message;
import org.apache.rocketmq.remoting.exception.RemotingException;
import org.apache.rocketmq.spring.core.RocketMQTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.stereotype.Service;

import com.dylan.common.kafka.util.KryoUtils;
import com.dylan.common.model.order.OrderMessage;
import com.dylan.common.model.order.OrderResult;
import com.dylan.common.model.order.OrderStatus;
import com.dylan.common.redis.lock.DistributedLock;
import com.dylan.common.redis.service.RedisService;
import com.dylan.common.ws.support.WsSender;
import com.dylan.mqProcedureServer.model.OrderResp;
import com.esotericsoftware.kryo.Kryo;
import com.fasterxml.jackson.core.JsonProcessingException;

@Service
public class OrderService {
	public static final String ORDER_KEY_PREFIX = "order:";
	public static final String ORDER_TIMEOUT_PREFIX = "tiemout:";
	private static final AtomicLong ORDER_SEQ = new AtomicLong(System.currentTimeMillis());
	private static final ThreadLocal<OrderMessage> THREAD_LOCAL_ORDER = ThreadLocal.withInitial(OrderMessage::new);
	Kryo KYRO = new Kryo();
	@Autowired
	private RocketMQTemplate rocketMQTemplate;
	@Autowired
	private RedisService redisService;
	@Autowired
	WsSender wsSender;

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
	public OrderResp createOrder(String userId, Integer quantity, String productId) throws JsonProcessingException,
			MQClientException, RemotingException, MQBrokerException, InterruptedException {
		redisService.set("stock:1001", 20);
		String orderId = "O" + ORDER_SEQ.getAndIncrement();
		OrderMessage order = THREAD_LOCAL_ORDER.get();
		order.reset(orderId, userId, productId, quantity, null);
		byte[] payload = KryoUtils.serialize(order);
		// 1. 写入 Redis
		redisService.set(ORDER_KEY_PREFIX + orderId, order);
		// 2. 发送 MQ
		Message msg = new Message("order-topic", "create", payload);
		rocketMQTemplate.getProducer().send(msg);
		return new OrderResp(orderId, userId, "下单成功，处理中...");
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
			wsSender.sendOrder(order.getUserId(), "ORDER",
					Map.of("orderId", order.getOrderId(), "status", order.getOrderStatus(), "msg", "订单处理成功，等待付款"))
					.subscribe();
		} else {
			// TODO: 可异步落库 DB
			wsSender.sendOrder(order.getUserId(), "ORDER",
					Map.of("orderId", order.getOrderId(), "status", order.getOrderStatus(), "msg", "订单异常"));
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
		wsSender.sendOrder(order.getUserId(), "ORDER",
				Map.of("orderId", order.getOrderId(), "status", order.getOrderStatus(), "msg", "订单超时已关闭")).subscribe();
	}
}
