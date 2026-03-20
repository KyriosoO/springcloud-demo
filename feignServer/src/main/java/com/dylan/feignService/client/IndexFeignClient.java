package com.dylan.feignService.client;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;


@FeignClient(name = "mserver", path = "/index", contextId = "feign2index")
public interface IndexFeignClient {
	@GetMapping //("/index")
	String index(@RequestParam("user") String name);
}
