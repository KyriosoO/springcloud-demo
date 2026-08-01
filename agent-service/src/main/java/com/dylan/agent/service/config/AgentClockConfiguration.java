package com.dylan.agent.service.config;

import com.dylan.agent.service.application.AgentClocks;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class AgentClockConfiguration {

    @Bean
    AgentClocks agentClocks() {
        return new AgentClocks() {
            @Override
            public long monotonicNanos() {
                return System.nanoTime();
            }

            @Override
            public long epochMillis() {
                return System.currentTimeMillis();
            }
        };
    }
}
