package com.dylan.agent.config;

import java.net.http.HttpClient;
import java.time.Clock;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

/** Spring Bean 配置，定义 agentRuntimeRestClient 和 agentClock 等基础设施 Bean。 */
@Configuration
public class AgentConfiguration {

    @Bean
    RestClient agentRuntimeRestClient(RestClient.Builder builder, AgentProperties properties) {
        var rt = properties.getRuntime();
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(rt.getConnectTimeout())
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(rt.getReadTimeout());
        return builder
                .baseUrl(rt.getBaseUrl())
                .requestFactory(requestFactory)
                .defaultHeader("Content-Type", "application/json")
                .build();
    }

    @Bean
    Clock agentClock() {
        return Clock.systemUTC();
    }
}
