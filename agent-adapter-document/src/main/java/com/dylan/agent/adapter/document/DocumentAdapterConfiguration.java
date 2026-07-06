package com.dylan.agent.adapter.document;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
@EnableConfigurationProperties(DocumentAdapterProperties.class)
public class DocumentAdapterConfiguration {
}
