package com.dylan.feignService.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.feignService.service.DecoratorService;

@RestController
public class DemoController {

	@Autowired
	DecoratorService decoratorService;

	// 调用 Service 中的 index 方法
	@GetMapping("/test")
	public String getIndex(@RequestParam("user") String user) {
		// 调用 Service 中的 index 方法
		return decoratorService.indexService(user);
	}

	@GetMapping("/api/my")
	public String getMy() {
		// 调用 Service 中的 index 方法
		return decoratorService.myService();
	}
	
	@GetMapping("/api/getUserId")
	public String getUserId() {
		// 调用 Service 中的 index 方法
		return decoratorService.myService();
	}

	@PostMapping("orders/create")
	public String createOrder(String userId, Integer quantity, String productId) {
		return decoratorService.mqCreateOrderService(userId, productId, quantity);
	}

	@PostMapping("orders/mqTest")
	public String createOrder(String orderId, Integer quantity) {
		return decoratorService.mqMyTestService(orderId, quantity);
	}
}