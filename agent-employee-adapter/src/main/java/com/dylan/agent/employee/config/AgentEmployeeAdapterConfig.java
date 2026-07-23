package com.dylan.agent.employee.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;
import org.springframework.security.oauth2.jwt.JwtEncoder;

import com.dylan.common.security.JwtKeyProvider;
import com.dylan.common.security.ServiceTokenProperties;
import com.dylan.common.security.ServiceTokenProvider;

@Configuration
@EnableConfigurationProperties({AgentEmployeeAdapterProperties.class, ServiceTokenProperties.class})
public class AgentEmployeeAdapterConfig {

	@Bean
	ServiceTokenProvider employeeServiceTokenProvider(JwtEncoder jwtEncoder,
			ServiceTokenProperties properties, Environment environment, JwtKeyProvider jwtKeyProvider) {
		return new ServiceTokenProvider(jwtEncoder, properties, environment, jwtKeyProvider);
	}
}
