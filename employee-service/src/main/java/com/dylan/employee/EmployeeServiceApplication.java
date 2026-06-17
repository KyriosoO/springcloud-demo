package com.dylan.employee;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.context.annotation.Import;
import org.springframework.kafka.annotation.EnableKafka;
import org.springframework.scheduling.annotation.EnableScheduling;

import com.dylan.common.kafka.config.BytesKafkaConsumerConfig;
import com.dylan.common.kafka.config.BytesKafkaProducerConfig;

/**
 * 员工服务启动类，负责启动员工业务服务。
 */
@EnableKafka
@EnableScheduling
@EnableFeignClients
@EnableDiscoveryClient
@MapperScan({"com.dylan.employee.mapper", "com.dylan.employee.dao"})
@Import({ BytesKafkaProducerConfig.class, BytesKafkaConsumerConfig.class })
@SpringBootApplication
public class EmployeeServiceApplication {

	/**
	 * 启动服务应用。
	 */
	public static void main(String[] args) {
		SpringApplication.run(EmployeeServiceApplication.class, args);
	}
}
