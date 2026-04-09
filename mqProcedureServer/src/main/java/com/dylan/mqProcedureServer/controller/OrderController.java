package com.dylan.mqProcedureServer.controller;

import org.apache.rocketmq.client.exception.MQBrokerException;
import org.apache.rocketmq.client.exception.MQClientException;
import org.apache.rocketmq.remoting.exception.RemotingException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.common.model.order.OrderMessage;
import com.dylan.mqProcedureServer.model.OrderResp;
import com.dylan.mqProcedureServer.service.OrderService;
import com.fasterxml.jackson.core.JsonProcessingException;

@RestController
@RequestMapping("/orders")
public class OrderController {
	@Autowired
	private OrderService orderService;

	@PostMapping("/mqTest")
	public String createOrder(@RequestParam String orderId, @RequestParam Integer quantity) {
		OrderMessage msg = new OrderMessage(orderId, quantity);
		orderService.sendOrderTx("order-topic:create", msg);
		return "订单创建成功，消息已发送";
	}

	@PostMapping("/create")
	public OrderResp createOrder(String userId, String productId, Integer quantity) throws JsonProcessingException,
			MQClientException, RemotingException, MQBrokerException, InterruptedException {
		return orderService.createOrder(userId, quantity, productId);
	}
}
