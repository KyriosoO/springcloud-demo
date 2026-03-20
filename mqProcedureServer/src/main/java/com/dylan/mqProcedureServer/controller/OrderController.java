package com.dylan.mqProcedureServer.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.common.model.order.OrderMessage;
import com.dylan.mqProcedureServer.service.OrderService;

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
	public String createOrder(String userId, String productId, Integer quantity) {
		return orderService.createOrder(userId, quantity, productId);
	}
}
