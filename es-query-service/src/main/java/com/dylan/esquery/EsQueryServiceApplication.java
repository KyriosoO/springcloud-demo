package com.dylan.esquery;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.scheduling.annotation.EnableAsync;

/**
 * ES 查询服务启动类，负责启动索引和检索服务。
 */
@EnableAsync
@EnableDiscoveryClient
@SpringBootApplication
public class EsQueryServiceApplication {

	/**
	 * 启动服务应用。
	 */
	public static void main(String[] args) {
		SpringApplication.run(EsQueryServiceApplication.class, args);
	}
}
