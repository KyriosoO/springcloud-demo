package com.dylan.mqprocedureserver.controller;

import org.apache.rocketmq.client.exception.MQBrokerException;
import org.apache.rocketmq.client.exception.MQClientException;
import org.apache.rocketmq.remoting.exception.RemotingException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.order.api.model.OrderMessage;
import com.dylan.mqprocedureserver.model.OrderResp;
import com.dylan.mqprocedureserver.service.OrderService;
import com.fasterxml.jackson.core.JsonProcessingException;

@RestController
@RequestMapping("/orders")
public class OrderController {
	@Autowired
	private OrderService orderService;

	@PostMapping("/mqTest")
	public String createOrder(@RequestParam String orderId, @RequestParam Integer quantity) {
		OrderMessage msg = new OrderMessage(orderId, quantity);
		orderService.sendOrderTx("order-topic:txTest", msg);
		return "消息已发送";
	}

	@PostMapping("/create")
	public OrderResp createOrder(@RequestParam String userId, @RequestParam String productId,
			@RequestParam Integer quantity,
			@RequestParam(required = false, defaultValue = "0") java.math.BigDecimal amount)
			throws JsonProcessingException, MQClientException, RemotingException, MQBrokerException,
			InterruptedException {
		return orderService.createOrder(userId, quantity, productId, amount);
	}
}
