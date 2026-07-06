package com.dylan.agent.config;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Agent 所有配置，统一使用 agent 前缀。
 * D04 后本类不再承载领域元数据；领域字段事实由
 * 通过 agent.domain-metadata 绑定到 DomainMetadataProperties。
 */
@ConfigurationProperties(prefix = "agent")
public class AgentProperties {

    private RuntimeProperties runtime;
    private AuthServiceProperties authService = new AuthServiceProperties();
    private ConversationProperties conversation;
    private QueryProperties query;
    private AggregateProperties aggregate;
    private DocumentProperties document = new DocumentProperties();

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

    public DocumentProperties getDocument() {
        return document;
    }

    public void setDocument(DocumentProperties document) {
        this.document = document == null ? new DocumentProperties() : document;
    }

    /** Runtime 连接配置。 */
    public static class RuntimeProperties {
        private String baseUrl;
        private Duration connectTimeout;
        private Duration readTimeout;
        private int maxResponseBytes;
        private String sharedKey;
        private String routePath = "/runtime/v1/route";
        private String planPath = "/runtime/v1/plan";
        private int maxRepairAttempts = 1;

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
        public String getRoutePath() { return routePath; }
        public void setRoutePath(String routePath) { this.routePath = routePath; }
        public String getPlanPath() { return planPath; }
        public void setPlanPath(String planPath) { this.planPath = planPath; }
        public int getMaxRepairAttempts() { return maxRepairAttempts; }
        public void setMaxRepairAttempts(int maxRepairAttempts) { this.maxRepairAttempts = maxRepairAttempts; }
    }

    /** auth-service 内部权限投影接口配置。 */
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

    /** 会话配置。 */
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

    /** 查询约束配置。 */
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

    /** 文档型检索与总结能力配置，默认不启用生产路由。 */
    public static class DocumentProperties {
        private boolean enabled = false;
        private int defaultSize = 5;
        private int maxSize = 20;
        private int maxEvidenceCount = 8;
        private int maxQueryTextLength = 500;
        private int maxSnippetChars = 500;
        private int maxSummaryChars = 2000;
        private EmbeddingProperties embedding = new EmbeddingProperties();
        private GenerationProperties generation = new GenerationProperties();
        private HybridProperties hybrid = new HybridProperties();

        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
        public int getDefaultSize() { return defaultSize; }
        public void setDefaultSize(int defaultSize) { this.defaultSize = defaultSize; }
        public int getMaxSize() { return maxSize; }
        public void setMaxSize(int maxSize) { this.maxSize = maxSize; }
        public int getMaxEvidenceCount() { return maxEvidenceCount; }
        public void setMaxEvidenceCount(int maxEvidenceCount) { this.maxEvidenceCount = maxEvidenceCount; }
        public int getMaxQueryTextLength() { return maxQueryTextLength; }
        public void setMaxQueryTextLength(int maxQueryTextLength) { this.maxQueryTextLength = maxQueryTextLength; }
        public int getMaxSnippetChars() { return maxSnippetChars; }
        public void setMaxSnippetChars(int maxSnippetChars) { this.maxSnippetChars = maxSnippetChars; }
        public int getMaxSummaryChars() { return maxSummaryChars; }
        public void setMaxSummaryChars(int maxSummaryChars) { this.maxSummaryChars = maxSummaryChars; }
        public EmbeddingProperties getEmbedding() { return embedding; }
        public void setEmbedding(EmbeddingProperties embedding) { this.embedding = embedding == null ? new EmbeddingProperties() : embedding; }
        public GenerationProperties getGeneration() { return generation; }
        public void setGeneration(GenerationProperties generation) { this.generation = generation == null ? new GenerationProperties() : generation; }
        public HybridProperties getHybrid() { return hybrid; }
        public void setHybrid(HybridProperties hybrid) { this.hybrid = hybrid == null ? new HybridProperties() : hybrid; }
    }

    /** 文档 queryVector 生成配置，默认关闭。 */
    public static class EmbeddingProperties {
        private boolean enabled = false;
        private String baseUrl;
        private String model;
        private int dimension = 0;
        private Duration timeout = Duration.ofSeconds(5);

        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
        public String getBaseUrl() { return baseUrl; }
        public void setBaseUrl(String baseUrl) { this.baseUrl = baseUrl; }
        public String getModel() { return model; }
        public void setModel(String model) { this.model = model; }
        public int getDimension() { return dimension; }
        public void setDimension(int dimension) { this.dimension = dimension; }
        public Duration getTimeout() { return timeout; }
        public void setTimeout(Duration timeout) { this.timeout = timeout; }
    }

    /** 文档执行后 LLM 生成配置，默认关闭。 */
    public static class GenerationProperties {
        private boolean enabled = false;
        private String baseUrl;
        private String model;
        private int maxContextChars = 8000;
        private int maxEvidenceChars = 1200;
        private int maxOutputChars = 2000;
        private Duration timeout = Duration.ofSeconds(15);
        private String failurePolicy = "FALLBACK_EXTRACTIVE";

        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
        public String getBaseUrl() { return baseUrl; }
        public void setBaseUrl(String baseUrl) { this.baseUrl = baseUrl; }
        public String getModel() { return model; }
        public void setModel(String model) { this.model = model; }
        public int getMaxContextChars() { return maxContextChars; }
        public void setMaxContextChars(int maxContextChars) { this.maxContextChars = maxContextChars; }
        public int getMaxEvidenceChars() { return maxEvidenceChars; }
        public void setMaxEvidenceChars(int maxEvidenceChars) { this.maxEvidenceChars = maxEvidenceChars; }
        public int getMaxOutputChars() { return maxOutputChars; }
        public void setMaxOutputChars(int maxOutputChars) { this.maxOutputChars = maxOutputChars; }
        public Duration getTimeout() { return timeout; }
        public void setTimeout(Duration timeout) { this.timeout = timeout; }
        public String getFailurePolicy() { return failurePolicy; }
        public void setFailurePolicy(String failurePolicy) { this.failurePolicy = failurePolicy; }
    }

    /** 文档混合检索默认参数。 */
    public static class HybridProperties {
        private int keywordK = 20;
        private int vectorK = 20;
        private int rrfK = 60;
        private int numCandidates = 100;

        public int getKeywordK() { return keywordK; }
        public void setKeywordK(int keywordK) { this.keywordK = keywordK; }
        public int getVectorK() { return vectorK; }
        public void setVectorK(int vectorK) { this.vectorK = vectorK; }
        public int getRrfK() { return rrfK; }
        public void setRrfK(int rrfK) { this.rrfK = rrfK; }
        public int getNumCandidates() { return numCandidates; }
        public void setNumCandidates(int numCandidates) { this.numCandidates = numCandidates; }
    }
}
