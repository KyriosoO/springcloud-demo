package com.dylan.mqProcedureServer;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.context.annotation.ComponentScan;

@SpringBootApplication
@EnableDiscoveryClient
@ComponentScan(basePackages = { "com.dylan.mqProcedureServer", // 本项目
		"com.dylan.common.redis", "com.dylan.common.db", "com.dylan.common.kafka", "com.dylan.common.ws", "com.dylan.common.security"// 公共模块
})
public class MqProcdeureServiceApplicaton {
	public static void main(String[] args) {
		SpringApplication.run(MqProcdeureServiceApplicaton.class, args);
	}
}
