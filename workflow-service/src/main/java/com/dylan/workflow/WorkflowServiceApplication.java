package com.dylan.workflow;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Import;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;

import com.dylan.common.kafka.config.BytesKafkaProducerConfig;
import com.dylan.workflow.config.WorkflowActionProperties;

@EnableAsync
@EnableScheduling
@EnableDiscoveryClient
@EnableConfigurationProperties(WorkflowActionProperties.class)
@Import(BytesKafkaProducerConfig.class)
@SpringBootApplication
public class WorkflowServiceApplication {

	public static void main(String[] args) {
		SpringApplication.run(WorkflowServiceApplication.class, args);
	}
}
