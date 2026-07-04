package com.dylan.mqprocedureserver;

import org.mybatis.spring.annotation.MapperScan;
import org.mybatis.spring.annotation.MapperScans;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.context.annotation.ComponentScan;

@SpringBootApplication
@EnableDiscoveryClient
@MapperScans({
		@MapperScan("com.dylan.mqprocedureserver.mapper")
})
@ComponentScan(basePackages = { "com.dylan.mqprocedureserver", // 本项目
		"com.dylan.common.redis", "com.dylan.common.db", "com.dylan.common.kafka", "com.dylan.common.ws", "com.dylan.common.security"// 公共模块
})
public class MqProcdeureServiceApplicaton {
	public static void main(String[] args) {
		SpringApplication.run(MqProcdeureServiceApplicaton.class, args);
	}
}
