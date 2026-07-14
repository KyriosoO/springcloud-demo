package com.dylan.agent.config;

import java.time.Duration;
import java.util.Set;
import org.springframework.boot.context.properties.ConfigurationProperties;

/** Agent 进程级基础配置；领域元数据、Profile、资源预算和 Provider 绑定由各自权威来源持有。 */
@ConfigurationProperties(prefix = "agent")
public class AgentProperties {
    private RuntimeProperties runtime;
    private AuthServiceProperties authService = new AuthServiceProperties();
    private ProfileProperties profile = new ProfileProperties();
    private ConversationProperties conversation;
    private QueryProperties query;
    private AggregateProperties aggregate;
    private DocumentProperties document = new DocumentProperties();

    public RuntimeProperties getRuntime() { return runtime; }
    public void setRuntime(RuntimeProperties runtime) { this.runtime = runtime; }
    public AuthServiceProperties getAuthService() { return authService; }
    public void setAuthService(AuthServiceProperties value) { authService = value == null ? new AuthServiceProperties() : value; }
    public ProfileProperties getProfile() { return profile; }
    public void setProfile(ProfileProperties value) { profile = value == null ? new ProfileProperties() : value; }
    public ConversationProperties getConversation() { return conversation; }
    public void setConversation(ConversationProperties conversation) { this.conversation = conversation; }
    public QueryProperties getQuery() { return query; }
    public void setQuery(QueryProperties query) { this.query = query; }
    public AggregateProperties getAggregate() { return aggregate; }
    public void setAggregate(AggregateProperties aggregate) { this.aggregate = aggregate; }
    public DocumentProperties getDocument() { return document; }
    public void setDocument(DocumentProperties value) { document = value == null ? new DocumentProperties() : value; }

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
        public void setBaseUrl(String value) { baseUrl = value; }
        public Duration getConnectTimeout() { return connectTimeout; }
        public void setConnectTimeout(Duration value) { connectTimeout = value; }
        public Duration getReadTimeout() { return readTimeout; }
        public void setReadTimeout(Duration value) { readTimeout = value; }
        public int getMaxResponseBytes() { return maxResponseBytes; }
        public void setMaxResponseBytes(int value) { maxResponseBytes = value; }
        public String getSharedKey() { return sharedKey; }
        public void setSharedKey(String value) { sharedKey = value; }
        public String getRoutePath() { return routePath; }
        public void setRoutePath(String value) { routePath = value; }
        public String getPlanPath() { return planPath; }
        public void setPlanPath(String value) { planPath = value; }
        public int getMaxRepairAttempts() { return maxRepairAttempts; }
        public void setMaxRepairAttempts(int value) { maxRepairAttempts = value; }
    }

    public static class AuthServiceProperties {
        private String baseUrl = "http://auth-service";
        private String resolvePath = "/internal/agent/permissions/resolve";
        private Duration connectTimeout = Duration.ofSeconds(2);
        private Duration readTimeout = Duration.ofSeconds(2);
        public String getBaseUrl() { return baseUrl; }
        public void setBaseUrl(String value) { baseUrl = value; }
        public String getResolvePath() { return resolvePath; }
        public void setResolvePath(String value) { resolvePath = value; }
        public Duration getConnectTimeout() { return connectTimeout; }
        public void setConnectTimeout(Duration value) { connectTimeout = value; }
        public Duration getReadTimeout() { return readTimeout; }
        public void setReadTimeout(Duration value) { readTimeout = value; }
    }

    /** 新建 CHAT Invocation 使用的精确 Profile 引用；不进入权限权威请求。 */
    public static class ProfileProperties {
        private String agentId = "agent-default";
        private String profileVersion = "profile-v1";
        private Set<String> allowedDomains = Set.of();
        public String getAgentId() { return agentId; }
        public void setAgentId(String value) { agentId = value; }
        public String getProfileVersion() { return profileVersion; }
        public void setProfileVersion(String value) { profileVersion = value; }
        public Set<String> getAllowedDomains() { return allowedDomains; }
        public void setAllowedDomains(Set<String> value) { allowedDomains = value == null ? Set.of() : Set.copyOf(value); }
    }

    public static class ConversationProperties {
        private int recentTurnLimit;
        private int retentionDays;
        private Duration cleanupDelay;
        public int getRecentTurnLimit() { return recentTurnLimit; }
        public void setRecentTurnLimit(int value) { recentTurnLimit = value; }
        public int getRetentionDays() { return retentionDays; }
        public void setRetentionDays(int value) { retentionDays = value; }
        public Duration getCleanupDelay() { return cleanupDelay; }
        public void setCleanupDelay(Duration value) { cleanupDelay = value; }
    }

    public static class QueryProperties {
        private int defaultSize;
        private int maxSize;
        private int maxResultWindow;
        private int maxFilters;
        private int maxInValues;
        private int maxFilterValueLength;
        private int maxDownstreamResponseBytes;
        public int getDefaultSize() { return defaultSize; }
        public void setDefaultSize(int value) { defaultSize = value; }
        public int getMaxSize() { return maxSize; }
        public void setMaxSize(int value) { maxSize = value; }
        public int getMaxResultWindow() { return maxResultWindow; }
        public void setMaxResultWindow(int value) { maxResultWindow = value; }
        public int getMaxFilters() { return maxFilters; }
        public void setMaxFilters(int value) { maxFilters = value; }
        public int getMaxInValues() { return maxInValues; }
        public void setMaxInValues(int value) { maxInValues = value; }
        public int getMaxFilterValueLength() { return maxFilterValueLength; }
        public void setMaxFilterValueLength(int value) { maxFilterValueLength = value; }
        public int getMaxDownstreamResponseBytes() { return maxDownstreamResponseBytes; }
        public void setMaxDownstreamResponseBytes(int value) { maxDownstreamResponseBytes = value; }
    }

    public static class AggregateProperties {
        private int maxMetrics = 5;
        private int maxGroupFields = 2;
        private int defaultMaxRows = 20;
        private int maxMaxRows = 100;
        public int getMaxMetrics() { return maxMetrics; }
        public void setMaxMetrics(int value) { maxMetrics = value; }
        public int getMaxGroupFields() { return maxGroupFields; }
        public void setMaxGroupFields(int value) { maxGroupFields = value; }
        public int getDefaultMaxRows() { return defaultMaxRows; }
        public void setDefaultMaxRows(int value) { defaultMaxRows = value; }
        public int getMaxMaxRows() { return maxMaxRows; }
        public void setMaxMaxRows(int value) { maxMaxRows = value; }
    }

    /** 仅保留文档 ACL authority 的技术连接配置。 */
    public static class DocumentProperties {
        private AclProperties acl = new AclProperties();
        public AclProperties getAcl() { return acl; }
        public void setAcl(AclProperties value) { acl = value == null ? new AclProperties() : value; }
    }

    public static class AclProperties {
        private String scopeUrl;
        private Duration timeout = Duration.ofSeconds(2);
        private Duration maxAuthorityEvidenceTtl = Duration.ofMinutes(30);
        private Duration finalDecisionMaxAge = Duration.ofSeconds(2);
        private int maxDepartments = 128;
        private int maxRoles = 128;
        private int maxAttributes = 128;
        private int maxAllowedDocumentIds = 512;
        private int maxDeniedDocumentIds = 512;
        private int maxAstNodes = 64;
        private int maxAstDepth = 8;
        private int maxTerms = 1024;
        private int maxCanonicalBytes = 131072;
        private int maxWireBytes = 262144;
        private int maxCurrentnessCandidates = 200;
        public String getScopeUrl() { return scopeUrl; }
        public void setScopeUrl(String value) { scopeUrl = value; }
        public Duration getTimeout() { return timeout; }
        public void setTimeout(Duration value) { timeout = value; }
        public Duration getMaxAuthorityEvidenceTtl() { return maxAuthorityEvidenceTtl; }
        public void setMaxAuthorityEvidenceTtl(Duration value) { maxAuthorityEvidenceTtl = value; }
        public Duration getFinalDecisionMaxAge() { return finalDecisionMaxAge; }
        public void setFinalDecisionMaxAge(Duration value) { finalDecisionMaxAge = value; }
        public int getMaxDepartments() { return maxDepartments; }
        public void setMaxDepartments(int value) { maxDepartments = value; }
        public int getMaxRoles() { return maxRoles; }
        public void setMaxRoles(int value) { maxRoles = value; }
        public int getMaxAttributes() { return maxAttributes; }
        public void setMaxAttributes(int value) { maxAttributes = value; }
        public int getMaxAllowedDocumentIds() { return maxAllowedDocumentIds; }
        public void setMaxAllowedDocumentIds(int value) { maxAllowedDocumentIds = value; }
        public int getMaxDeniedDocumentIds() { return maxDeniedDocumentIds; }
        public void setMaxDeniedDocumentIds(int value) { maxDeniedDocumentIds = value; }
        public int getMaxAstNodes() { return maxAstNodes; }
        public void setMaxAstNodes(int value) { maxAstNodes = value; }
        public int getMaxAstDepth() { return maxAstDepth; }
        public void setMaxAstDepth(int value) { maxAstDepth = value; }
        public int getMaxTerms() { return maxTerms; }
        public void setMaxTerms(int value) { maxTerms = value; }
        public int getMaxCanonicalBytes() { return maxCanonicalBytes; }
        public void setMaxCanonicalBytes(int value) { maxCanonicalBytes = value; }
        public int getMaxWireBytes() { return maxWireBytes; }
        public void setMaxWireBytes(int value) { maxWireBytes = value; }
        public int getMaxCurrentnessCandidates() { return maxCurrentnessCandidates; }
        public void setMaxCurrentnessCandidates(int value) { maxCurrentnessCandidates = value; }
    }
}
