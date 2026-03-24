package com.dylan.mqConsumerServer;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.context.annotation.ComponentScan;

@SpringBootApplication
@EnableDiscoveryClient
@ComponentScan(basePackages = { "com.dylan.mqConsumerServer", // 本项目
		"com.dylan.common.redis","com.dylan.common.db","com.dylan.common.kafka" // 公共模块
})
public class MqConsumerServiceApplicaton {
	public static void main(String[] args) {
		SpringApplication.run(MqConsumerServiceApplicaton.class, args);
	}
}
