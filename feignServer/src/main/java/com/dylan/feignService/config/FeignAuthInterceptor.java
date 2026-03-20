package com.dylan.feignService.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.context.request.RequestAttributes;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import feign.RequestInterceptor;
import feign.RequestTemplate;

@Configuration
public class FeignAuthInterceptor implements RequestInterceptor {

	@Override
	public void apply(RequestTemplate template) {
		// 获取当前 HTTP 请求
		RequestAttributes requestAttributes = RequestContextHolder.getRequestAttributes();
		if (requestAttributes instanceof ServletRequestAttributes attrs) {
			String authHeader = attrs.getRequest().getHeader("Authorization");
			if (authHeader != null && !authHeader.isEmpty()) {
				// 将 Authorization Header 传递给 Feign 调用的下游服务
				template.header("Authorization", authHeader);
			}
		}
	}
}
