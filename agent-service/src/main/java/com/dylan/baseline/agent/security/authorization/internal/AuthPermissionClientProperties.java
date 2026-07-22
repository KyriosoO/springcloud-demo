package com.dylan.baseline.agent.security.authorization.internal;

import java.net.URI;
import java.time.Duration;
import org.springframework.beans.factory.InitializingBean;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "agent.security.auth")
public final class AuthPermissionClientProperties implements InitializingBean {

    private String baseUrl;
    private String resolvePath = "/internal/agent/permissions/resolve";
    private Duration connectTimeout = Duration.ofSeconds(2);
    private Duration readTimeout = Duration.ofSeconds(2);
    private int maxResponseBytes = 65_536;
    private boolean positiveCacheEnabled;

    public String getBaseUrl() {
        return baseUrl;
    }

    public void setBaseUrl(String baseUrl) {
        this.baseUrl = baseUrl;
    }

    public String getResolvePath() {
        return resolvePath;
    }

    public void setResolvePath(String resolvePath) {
        this.resolvePath = resolvePath;
    }

    public Duration getConnectTimeout() {
        return connectTimeout;
    }

    public void setConnectTimeout(Duration connectTimeout) {
        this.connectTimeout = connectTimeout;
    }

    public Duration getReadTimeout() {
        return readTimeout;
    }

    public void setReadTimeout(Duration readTimeout) {
        this.readTimeout = readTimeout;
    }

    public int getMaxResponseBytes() {
        return maxResponseBytes;
    }

    public void setMaxResponseBytes(int maxResponseBytes) {
        this.maxResponseBytes = maxResponseBytes;
    }

    public boolean isPositiveCacheEnabled() {
        return positiveCacheEnabled;
    }

    public void setPositiveCacheEnabled(boolean positiveCacheEnabled) {
        this.positiveCacheEnabled = positiveCacheEnabled;
    }

    @Override
    public void afterPropertiesSet() {
        URI base = parseBaseUrl();
        if (!("http".equalsIgnoreCase(base.getScheme()) || "https".equalsIgnoreCase(base.getScheme()))
                || base.getHost() == null
                || base.getUserInfo() != null
                || base.getQuery() != null
                || base.getFragment() != null) {
            throw new IllegalStateException("agent.security.auth.base-url must be an HTTP(S) service URL");
        }
        URI path;
        try {
            path = URI.create(resolvePath == null ? "" : resolvePath);
        } catch (IllegalArgumentException ex) {
            throw new IllegalStateException("agent.security.auth.resolve-path is invalid", ex);
        }
        boolean invalidPath = path.isAbsolute()
                || resolvePath == null
                || !resolvePath.startsWith("/")
                || path.getQuery() != null
                || path.getFragment() != null;
        if (invalidPath) {
            throw new IllegalStateException("agent.security.auth.resolve-path must be an absolute HTTP path");
        }
        requirePositive(connectTimeout, "connect-timeout");
        requirePositive(readTimeout, "read-timeout");
        if (maxResponseBytes < 1_024 || maxResponseBytes > 1_048_576) {
            throw new IllegalStateException("agent.security.auth.max-response-bytes must be between 1024 and 1048576");
        }
        if (positiveCacheEnabled) {
            throw new IllegalStateException("agent.security.auth.positive-cache-enabled must remain false");
        }
    }

    private URI parseBaseUrl() {
        try {
            return URI.create(baseUrl == null ? "" : baseUrl);
        } catch (IllegalArgumentException ex) {
            throw new IllegalStateException("agent.security.auth.base-url is invalid", ex);
        }
    }

    private static void requirePositive(Duration value, String name) {
        if (value == null || value.isZero() || value.isNegative()) {
            throw new IllegalStateException("agent.security.auth." + name + " must be positive");
        }
    }
}
