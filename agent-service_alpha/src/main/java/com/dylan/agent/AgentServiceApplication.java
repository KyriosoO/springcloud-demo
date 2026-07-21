package com.dylan.agent;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.scheduling.annotation.EnableScheduling;

import com.dylan.agent.config.AgentProperties;

@SpringBootApplication
@EnableDiscoveryClient
@EnableFeignClients(basePackages = "com.dylan.agent.adapter")
@EnableScheduling
@EnableConfigurationProperties(AgentProperties.class)
@org.mybatis.spring.annotation.MapperScan(
        basePackages = {
                "com.dylan.agent.persistence.mapper",
                "com.dylan.agent.metadata.context.internal"
        },
        annotationClass = org.apache.ibatis.annotations.Mapper.class)
public class AgentServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(AgentServiceApplication.class, args);
    }
}
