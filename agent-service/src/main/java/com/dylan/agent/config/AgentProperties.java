package com.dylan.agent.config;

import java.time.Duration;
import java.util.Map;
import java.util.Set;

import org.springframework.boot.context.properties.ConfigurationProperties;

import com.dylan.agent.api.enums.AgentIntent;

/**
 * Agent 所有配置，以 agent 为前缀。
 * D04 后本类不再承载 domain metadata；domain 字段事实由
 * agent.domain-metadata 绑定到 DomainMetadataProperties。
 */
@ConfigurationProperties(prefix = "agent")
public class AgentProperties {

    private Map<AgentIntent, Set<String>> intentRoles;
    private RuntimeProperties runtime;
    private AuthServiceProperties authService = new AuthServiceProperties();
    private ConversationProperties conversation;
    private QueryProperties query;
    private AggregateProperties aggregate;

    public Map<AgentIntent, Set<String>> getIntentRoles() {
        return intentRoles;
    }

    public void setIntentRoles(Map<AgentIntent, Set<String>> intentRoles) {
        this.intentRoles = intentRoles;
    }

    public RuntimeProperties getRuntime() {
        return runtime;
    }

    public void setRuntime(RuntimeProperties runtime) {
        this.runtime = runtime;
    }

    public AuthServiceProperties getAuthService() {
        return authService;
    }

    public void setAuthService(AuthServiceProperties authService) {
        this.authService = authService == null ? new AuthServiceProperties() : authService;
    }

    public ConversationProperties getConversation() {
        return conversation;
    }

    public void setConversation(ConversationProperties conversation) {
        this.conversation = conversation;
    }

    public QueryProperties getQuery() {
        return query;
    }

    public void setQuery(QueryProperties query) {
        this.query = query;
    }

    public AggregateProperties getAggregate() {
        return aggregate;
    }

    public void setAggregate(AggregateProperties aggregate) {
        this.aggregate = aggregate;
    }

    /** Runtime 连接配置 */
    public static class RuntimeProperties {
        private String baseUrl;
        private Duration connectTimeout;
        private Duration readTimeout;
        private int maxResponseBytes;
        private String sharedKey;

        public String getBaseUrl() { return baseUrl; }
        public void setBaseUrl(String baseUrl) { this.baseUrl = baseUrl; }
        public Duration getConnectTimeout() { return connectTimeout; }
        public void setConnectTimeout(Duration connectTimeout) { this.connectTimeout = connectTimeout; }
        public Duration getReadTimeout() { return readTimeout; }
        public void setReadTimeout(Duration readTimeout) { this.readTimeout = readTimeout; }
        public int getMaxResponseBytes() { return maxResponseBytes; }
        public void setMaxResponseBytes(int maxResponseBytes) { this.maxResponseBytes = maxResponseBytes; }
        public String getSharedKey() { return sharedKey; }
        public void setSharedKey(String sharedKey) { this.sharedKey = sharedKey; }
    }

    /** auth-service 内部权限投影接口配置 */
    public static class AuthServiceProperties {
        private String baseUrl = "http://auth-service";
        private String resolvePath = "/internal/agent/permissions/resolve";
        private Duration connectTimeout = Duration.ofSeconds(2);
        private Duration readTimeout = Duration.ofSeconds(2);
        private String agentId = "agent-default";
        private String profileId = "profile-v1";
        private String scopeType = "CONVERSATION";
        private String scopeId = "agent-permission-authority";

        public String getBaseUrl() { return baseUrl; }
        public void setBaseUrl(String baseUrl) { this.baseUrl = baseUrl; }
        public String getResolvePath() { return resolvePath; }
        public void setResolvePath(String resolvePath) { this.resolvePath = resolvePath; }
        public Duration getConnectTimeout() { return connectTimeout; }
        public void setConnectTimeout(Duration connectTimeout) { this.connectTimeout = connectTimeout; }
        public Duration getReadTimeout() { return readTimeout; }
        public void setReadTimeout(Duration readTimeout) { this.readTimeout = readTimeout; }
        public String getAgentId() { return agentId; }
        public void setAgentId(String agentId) { this.agentId = agentId; }
        public String getProfileId() { return profileId; }
        public void setProfileId(String profileId) { this.profileId = profileId; }
        public String getScopeType() { return scopeType; }
        public void setScopeType(String scopeType) { this.scopeType = scopeType; }
        public String getScopeId() { return scopeId; }
        public void setScopeId(String scopeId) { this.scopeId = scopeId; }
    }

    /** Conversation 配置 */
    public static class ConversationProperties {
        private int recentTurnLimit;
        private int retentionDays;
        private Duration cleanupDelay;

        public int getRecentTurnLimit() { return recentTurnLimit; }
        public void setRecentTurnLimit(int recentTurnLimit) { this.recentTurnLimit = recentTurnLimit; }
        public int getRetentionDays() { return retentionDays; }
        public void setRetentionDays(int retentionDays) { this.retentionDays = retentionDays; }
        public Duration getCleanupDelay() { return cleanupDelay; }
        public void setCleanupDelay(Duration cleanupDelay) { this.cleanupDelay = cleanupDelay; }
    }

    /** Query 约束配置 */
    public static class QueryProperties {
        private int defaultSize;
        private int maxSize;
        private int maxResultWindow;
        private int maxFilters;
        private int maxInValues;
        private int maxFilterValueLength;
        private int maxDownstreamResponseBytes;

        public int getDefaultSize() { return defaultSize; }
        public void setDefaultSize(int defaultSize) { this.defaultSize = defaultSize; }
        public int getMaxSize() { return maxSize; }
        public void setMaxSize(int maxSize) { this.maxSize = maxSize; }
        public int getMaxResultWindow() { return maxResultWindow; }
        public void setMaxResultWindow(int maxResultWindow) { this.maxResultWindow = maxResultWindow; }
        public int getMaxFilters() { return maxFilters; }
        public void setMaxFilters(int maxFilters) { this.maxFilters = maxFilters; }
        public int getMaxInValues() { return maxInValues; }
        public void setMaxInValues(int maxInValues) { this.maxInValues = maxInValues; }
        public int getMaxFilterValueLength() { return maxFilterValueLength; }
        public void setMaxFilterValueLength(int maxFilterValueLength) { this.maxFilterValueLength = maxFilterValueLength; }
        public int getMaxDownstreamResponseBytes() { return maxDownstreamResponseBytes; }
        public void setMaxDownstreamResponseBytes(int maxDownstreamResponseBytes) { this.maxDownstreamResponseBytes = maxDownstreamResponseBytes; }
    }

    /** 聚合配置 */
    public static class AggregateProperties {
        private int maxMetrics = 5;
        private int maxGroupFields = 2;
        private int defaultMaxRows = 20;
        private int maxMaxRows = 100;

        public int getMaxMetrics() { return maxMetrics; }
        public void setMaxMetrics(int maxMetrics) { this.maxMetrics = maxMetrics; }
        public int getMaxGroupFields() { return maxGroupFields; }
        public void setMaxGroupFields(int maxGroupFields) { this.maxGroupFields = maxGroupFields; }
        public int getDefaultMaxRows() { return defaultMaxRows; }
        public void setDefaultMaxRows(int defaultMaxRows) { this.defaultMaxRows = defaultMaxRows; }
        public int getMaxMaxRows() { return maxMaxRows; }
        public void setMaxMaxRows(int maxMaxRows) { this.maxMaxRows = maxMaxRows; }
    }
}
