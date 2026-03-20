package com.dylan.feignService.client;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;


@FeignClient(name = "authCenter", path = "/my", contextId = "feign2my")
public interface MyFeignClient {
	@GetMapping // ("/index")
	String my();
}
