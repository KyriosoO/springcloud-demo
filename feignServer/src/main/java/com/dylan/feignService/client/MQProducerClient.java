package com.dylan.feignService.client;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

@FeignClient(name = "mqprocedureserver", path = "/orders/", contextId = "feign2mqProducer")
public interface MQProducerClient {
	@PostMapping(path = "create")
	String createOrders(@RequestParam String userId, @RequestParam String productId, @RequestParam Integer quantity);

	@PostMapping(path = "mqTest")
	String mqTest(@RequestParam String orderId, @RequestParam Integer quantity);
}
