package com.dylan.agent.capability.document.provider;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.beans.factory.InitializingBean;
import java.time.Duration;

@ConfigurationProperties(prefix = "agent.document-provider-adapter")
public class DocumentProviderAdapterProperties implements InitializingBean {
    private String baseUrl = "http://document-provider-adapter";
    private Duration connectTimeout = Duration.ofSeconds(1);
    private Duration readTimeout = Duration.ofSeconds(15);
    private long maxRequestBytes = 2_000_000L;
    private long maxResponseBytes = 2_000_000L;

    public String getBaseUrl() { return baseUrl; }
    public void setBaseUrl(String baseUrl) { this.baseUrl = baseUrl; }
    public Duration getConnectTimeout() { return connectTimeout; }
    public void setConnectTimeout(Duration connectTimeout) { this.connectTimeout = connectTimeout; }
    public Duration getReadTimeout() { return readTimeout; }
    public void setReadTimeout(Duration readTimeout) { this.readTimeout = readTimeout; }
    public long getMaxRequestBytes() { return maxRequestBytes; }
    public void setMaxRequestBytes(long maxRequestBytes) { this.maxRequestBytes = maxRequestBytes; }
    public long getMaxResponseBytes() { return maxResponseBytes; }
    public void setMaxResponseBytes(long maxResponseBytes) { this.maxResponseBytes = maxResponseBytes; }

    @Override
    public void afterPropertiesSet() {
        if (baseUrl == null || baseUrl.isBlank()
                || connectTimeout == null || connectTimeout.isZero() || connectTimeout.isNegative()
                || readTimeout == null || readTimeout.isZero() || readTimeout.isNegative()
                || maxRequestBytes <= 0 || maxRequestBytes >= Integer.MAX_VALUE
                || maxResponseBytes <= 0 || maxResponseBytes >= Integer.MAX_VALUE) {
            throw new IllegalStateException("document provider adapter properties invalid");
        }
    }
}
