package com.dylan.feignservice.client;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;

@FeignClient(name = "auth-service", path = "/as/", contextId = "feign2my")
public interface AsFeignClient {
	@GetMapping("/my")
	String my();

	@GetMapping("/getUserId")
	String getUserId();
}
