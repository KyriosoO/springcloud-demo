package com.dylan.feignService.client;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;

@FeignClient(name = "authCenter", path = "/as/", contextId = "feign2my")
public interface AsFeignClient {
	@GetMapping("/my")
	String my();

	@GetMapping("/getUserId")
	String getUserId();
}
