package com.dylan.agent.employee;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;

@EnableDiscoveryClient
@SpringBootApplication
public class AgentEmployeeAdapterApplication {

	public static void main(String[] args) {
		SpringApplication.run(AgentEmployeeAdapterApplication.class, args);
	}
}
