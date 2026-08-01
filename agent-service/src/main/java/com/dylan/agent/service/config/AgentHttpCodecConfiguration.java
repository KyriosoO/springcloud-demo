package com.dylan.agent.service.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.http.codec.ServerCodecConfigurer;
import org.springframework.web.reactive.config.WebFluxConfigurer;

@Configuration(proxyBeanMethods = false)
public class AgentHttpCodecConfiguration implements WebFluxConfigurer {
    private final AgentIngressProperties properties;

    public AgentHttpCodecConfiguration(AgentIngressProperties properties) {
        this.properties = properties;
    }

    @Override
    public void configureHttpMessageCodecs(ServerCodecConfigurer configurer) {
        configurer.defaultCodecs().maxInMemorySize(properties.maxBodyBytes());
    }
}
