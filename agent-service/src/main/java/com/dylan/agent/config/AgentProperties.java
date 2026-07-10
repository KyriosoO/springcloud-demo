package com.dylan.agent.config;

import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.dylan.agent.api.plan.DocumentRetrievalMode;
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
        private RetrievalProperties retrieval = new RetrievalProperties();
        private TextLimitsProperties textLimits = new TextLimitsProperties();
        private EvidenceSelectionProperties evidenceSelection = new EvidenceSelectionProperties();
        private ContextWindowProperties contextWindow = new ContextWindowProperties();
        private RewriteProperties rewrite = new RewriteProperties();
        private EmbeddingProperties embedding = new EmbeddingProperties();
        private GenerationProperties generation = new GenerationProperties();
        private RerankProviderProperties rerank = new RerankProviderProperties();
        private AclProperties acl = new AclProperties();
        private BlocklistProperties blocklist = new BlocklistProperties();

        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
        public RetrievalProperties getRetrieval() { return retrieval; }
        public void setRetrieval(RetrievalProperties retrieval) {
            this.retrieval = retrieval == null ? new RetrievalProperties() : retrieval;
        }
        public TextLimitsProperties getTextLimits() { return textLimits; }
        public void setTextLimits(TextLimitsProperties textLimits) {
            this.textLimits = textLimits == null ? new TextLimitsProperties() : textLimits;
        }
        public int getDefaultSize() { return retrieval.getDefaultSize(); }
        public void setDefaultSize(int defaultSize) { retrieval.setDefaultSize(defaultSize); }
        public int getAnswerCandidateSize() { return retrieval.getAnswerCandidateSize(); }
        public void setAnswerCandidateSize(int answerCandidateSize) {
            retrieval.setAnswerCandidateSize(answerCandidateSize);
        }
        public int getSummarizeCandidateSize() { return retrieval.getSummarizeCandidateSize(); }
        public void setSummarizeCandidateSize(int summarizeCandidateSize) {
            retrieval.setSummarizeCandidateSize(summarizeCandidateSize);
        }
        public int getMaxSize() { return retrieval.getMaxSize(); }
        public void setMaxSize(int maxSize) { retrieval.setMaxSize(maxSize); }
        public int getMaxEvidenceCount() { return evidenceSelection.getMaxEvidenceCount(); }
        public void setMaxEvidenceCount(int maxEvidenceCount) {
            evidenceSelection.setMaxEvidenceCount(maxEvidenceCount);
        }
        public int getMaxGenerationEvidenceCount() { return evidenceSelection.getMaxGenerationEvidenceCount(); }
        public int getMaxDisplayCitationCount() { return evidenceSelection.getMaxDisplayCitationCount(); }
        public int getMaxSummaryDocumentCount() { return evidenceSelection.getMaxSummaryDocumentCount(); }
        public int getMaxQueryTextLength() { return textLimits.getMaxQueryTextLength(); }
        public void setMaxQueryTextLength(int maxQueryTextLength) {
            textLimits.setMaxQueryTextLength(maxQueryTextLength);
        }
        public int getMaxSnippetChars() { return textLimits.getMaxSnippetChars(); }
        public void setMaxSnippetChars(int maxSnippetChars) { textLimits.setMaxSnippetChars(maxSnippetChars); }
        public int getMaxSummaryChars() { return textLimits.getMaxSummaryChars(); }
        public void setMaxSummaryChars(int maxSummaryChars) { textLimits.setMaxSummaryChars(maxSummaryChars); }
        public DocumentRetrievalMode getDefaultRetrievalMode() { return retrieval.getDefaultMode(); }
        public void setDefaultRetrievalMode(DocumentRetrievalMode defaultRetrievalMode) {
            retrieval.setDefaultMode(defaultRetrievalMode);
        }
        public Map<String, DocumentRetrievalMode> getRetrievalModeByDomain() { return retrieval.getModeByDomain(); }
        public void setRetrievalModeByDomain(Map<String, DocumentRetrievalMode> retrievalModeByDomain) {
            retrieval.setModeByDomain(retrievalModeByDomain);
        }
        public Map<String, RetrievalProfileProperties> getRetrievalProfiles() { return retrieval.getProfiles(); }
        public void setRetrievalProfiles(Map<String, RetrievalProfileProperties> retrievalProfiles) {
            retrieval.setProfiles(retrievalProfiles);
        }
        public EvidenceSelectionProperties getEvidenceSelection() { return evidenceSelection; }
        public void setEvidenceSelection(EvidenceSelectionProperties evidenceSelection) {
            this.evidenceSelection = evidenceSelection == null ? new EvidenceSelectionProperties() : evidenceSelection;
        }
        public ContextWindowProperties getContextWindow() { return contextWindow; }
        public void setContextWindow(ContextWindowProperties contextWindow) {
            this.contextWindow = contextWindow == null ? new ContextWindowProperties() : contextWindow;
        }
        public RewriteProperties getRewrite() { return rewrite; }
        public void setRewrite(RewriteProperties rewrite) {
            this.rewrite = rewrite == null ? new RewriteProperties() : rewrite;
        }
        public EmbeddingProperties getEmbedding() { return embedding; }
        public void setEmbedding(EmbeddingProperties embedding) { this.embedding = embedding == null ? new EmbeddingProperties() : embedding; }
        public GenerationProperties getGeneration() { return generation; }
        public void setGeneration(GenerationProperties generation) { this.generation = generation == null ? new GenerationProperties() : generation; }
        public RerankProviderProperties getRerank() { return rerank; }
        public void setRerank(RerankProviderProperties rerank) {
            this.rerank = rerank == null ? new RerankProviderProperties() : rerank;
        }
        public HybridProperties getHybrid() { return retrieval.getHybrid(); }
        public void setHybrid(HybridProperties hybrid) { retrieval.setHybrid(hybrid); }
        public AclProperties getAcl() { return acl; }
        public void setAcl(AclProperties acl) { this.acl = acl == null ? new AclProperties() : acl; }
        public BlocklistProperties getBlocklist() { return blocklist; }
        public void setBlocklist(BlocklistProperties blocklist) { this.blocklist = blocklist == null ? new BlocklistProperties() : blocklist; }
    }

    /** 文档检索阶段预算与 profile 路由配置。 */
    public static class RetrievalProperties {
        private int defaultSize = 5;
        private int answerCandidateSize = 20;
        private int summarizeCandidateSize = 20;
        private int maxSize = 20;
        private DocumentRetrievalMode defaultMode = DocumentRetrievalMode.HYBRID;
        private Map<String, DocumentRetrievalMode> modeByDomain = new LinkedHashMap<>();
        private HybridProperties hybrid = new HybridProperties();
        private Map<String, RetrievalProfileProperties> profiles = new LinkedHashMap<>();

        public int getDefaultSize() { return defaultSize; }
        public void setDefaultSize(int defaultSize) { this.defaultSize = defaultSize; }
        public int getAnswerCandidateSize() { return answerCandidateSize; }
        public void setAnswerCandidateSize(int answerCandidateSize) { this.answerCandidateSize = answerCandidateSize; }
        public int getSummarizeCandidateSize() { return summarizeCandidateSize; }
        public void setSummarizeCandidateSize(int summarizeCandidateSize) {
            this.summarizeCandidateSize = summarizeCandidateSize;
        }
        public int getMaxSize() { return maxSize; }
        public void setMaxSize(int maxSize) { this.maxSize = maxSize; }
        public DocumentRetrievalMode getDefaultMode() { return defaultMode; }
        public void setDefaultMode(DocumentRetrievalMode defaultMode) {
            this.defaultMode = defaultMode == null ? DocumentRetrievalMode.HYBRID : defaultMode;
        }
        public Map<String, DocumentRetrievalMode> getModeByDomain() { return modeByDomain; }
        public void setModeByDomain(Map<String, DocumentRetrievalMode> modeByDomain) {
            this.modeByDomain = modeByDomain == null ? new LinkedHashMap<>() : new LinkedHashMap<>(modeByDomain);
        }
        public HybridProperties getHybrid() { return hybrid; }
        public void setHybrid(HybridProperties hybrid) {
            this.hybrid = hybrid == null ? new HybridProperties() : hybrid;
        }
        public Map<String, RetrievalProfileProperties> getProfiles() { return profiles; }
        public void setProfiles(Map<String, RetrievalProfileProperties> profiles) {
            this.profiles = profiles == null ? new LinkedHashMap<>() : new LinkedHashMap<>(profiles);
        }
    }

    /** 文档查询、片段和摘要文本长度预算。 */
    public static class TextLimitsProperties {
        private int maxQueryTextLength = 500;
        private int maxSnippetChars = 500;
        private int maxSummaryChars = 2000;

        public int getMaxQueryTextLength() { return maxQueryTextLength; }
        public void setMaxQueryTextLength(int maxQueryTextLength) {
            this.maxQueryTextLength = maxQueryTextLength;
        }
        public int getMaxSnippetChars() { return maxSnippetChars; }
        public void setMaxSnippetChars(int maxSnippetChars) { this.maxSnippetChars = maxSnippetChars; }
        public int getMaxSummaryChars() { return maxSummaryChars; }
        public void setMaxSummaryChars(int maxSummaryChars) { this.maxSummaryChars = maxSummaryChars; }
    }

    /** 文档 evidence 在生成、展示和总结阶段的数量预算。 */
    public static class EvidenceSelectionProperties {
        private int maxGenerationEvidenceCount = 5;
        private int maxDisplayCitationCount = 8;
        private int maxSummaryDocumentCount = 8;
        private EvidenceSelectionStrategy strategy = EvidenceSelectionStrategy.TOP_K_FIXED;
        private int scoreGroups = 3;
        private int minTopGroupSize = 1;

        public int getMaxEvidenceCount() { return maxDisplayCitationCount; }
        public void setMaxEvidenceCount(int maxEvidenceCount) {
            this.maxGenerationEvidenceCount = maxEvidenceCount;
            this.maxDisplayCitationCount = maxEvidenceCount;
            this.maxSummaryDocumentCount = maxEvidenceCount;
        }
        public int getMaxGenerationEvidenceCount() { return maxGenerationEvidenceCount; }
        public void setMaxGenerationEvidenceCount(int maxGenerationEvidenceCount) {
            this.maxGenerationEvidenceCount = maxGenerationEvidenceCount;
        }
        public int getMaxDisplayCitationCount() { return maxDisplayCitationCount; }
        public void setMaxDisplayCitationCount(int maxDisplayCitationCount) {
            this.maxDisplayCitationCount = maxDisplayCitationCount;
        }
        public int getMaxSummaryDocumentCount() { return maxSummaryDocumentCount; }
        public void setMaxSummaryDocumentCount(int maxSummaryDocumentCount) {
            this.maxSummaryDocumentCount = maxSummaryDocumentCount;
        }
        public EvidenceSelectionStrategy getStrategy() { return strategy; }
        public void setStrategy(EvidenceSelectionStrategy strategy) {
            this.strategy = strategy == null ? EvidenceSelectionStrategy.TOP_K_FIXED : strategy;
        }
        public int getScoreGroups() { return scoreGroups; }
        public void setScoreGroups(int scoreGroups) { this.scoreGroups = scoreGroups; }
        public int getMinTopGroupSize() { return minTopGroupSize; }
        public void setMinTopGroupSize(int minTopGroupSize) { this.minTopGroupSize = minTopGroupSize; }
    }

    public enum EvidenceSelectionStrategy {
        TOP_K_FIXED,
        SCORE_GROUP_TOP
    }

    /** 文档命中片段进入生成前的相邻 chunk 上下文窗口。 */
    public static class ContextWindowProperties {
        private boolean enabled = true;
        private int beforeChunks = 1;
        private int afterChunks = 1;

        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
        public int getBeforeChunks() { return beforeChunks; }
        public void setBeforeChunks(int beforeChunks) { this.beforeChunks = beforeChunks; }
        public int getAfterChunks() { return afterChunks; }
        public void setAfterChunks(int afterChunks) { this.afterChunks = afterChunks; }
    }

    /** Runtime LLM 改写候选配置，默认关闭。 */
    public static class RewriteProperties {
        private boolean enabled = false;
        private String path = "/runtime/v1/document/rewrite";
        private String language = "zh-CN";
        private int maxCandidates = 3;
        private int maxCandidateLength = 128;
        private Duration timeout = Duration.ofSeconds(2);

        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
        public String getPath() { return path; }
        public void setPath(String path) { this.path = path; }
        public String getLanguage() { return language; }
        public void setLanguage(String language) { this.language = language; }
        public int getMaxCandidates() { return maxCandidates; }
        public void setMaxCandidates(int maxCandidates) { this.maxCandidates = maxCandidates; }
        public int getMaxCandidateLength() { return maxCandidateLength; }
        public void setMaxCandidateLength(int maxCandidateLength) { this.maxCandidateLength = maxCandidateLength; }
        public Duration getTimeout() { return timeout; }
        public void setTimeout(Duration timeout) { this.timeout = timeout; }
    }

    /** 文档 ACL 安全投影配置，文档能力启用时默认 fail closed。 */
    public static class AclProperties {
        private boolean enabled = true;
        private String scopeUrl;
        private Duration timeout = Duration.ofSeconds(2);

        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
        public String getScopeUrl() { return scopeUrl; }
        public void setScopeUrl(String scopeUrl) { this.scopeUrl = scopeUrl; }
        public Duration getTimeout() { return timeout; }
        public void setTimeout(Duration timeout) { this.timeout = timeout; }
    }

    /** 文档 queryVector 生成配置，默认关闭。 */
    public static class EmbeddingProperties {
        private boolean enabled = false;
        private String provider = "default";
        private String baseUrl;
        private String model;
        private int dimension = 0;
        private Duration timeout = Duration.ofSeconds(5);

        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
        public String getProvider() { return provider; }
        public void setProvider(String provider) { this.provider = provider; }
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

    /** 文档 rerank provider 配置，默认关闭。 */
    public static class RerankProviderProperties {
        private boolean enabled = false;
        private String baseUrl;
        private String path = "/rerank";
        private String model;
        private boolean normalize = true;
        private int maxDocumentChars = 1200;
        private Duration timeout = Duration.ofSeconds(5);

        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
        public String getBaseUrl() { return baseUrl; }
        public void setBaseUrl(String baseUrl) { this.baseUrl = baseUrl; }
        public String getPath() { return path; }
        public void setPath(String path) { this.path = path; }
        public String getModel() { return model; }
        public void setModel(String model) { this.model = model; }
        public boolean isNormalize() { return normalize; }
        public void setNormalize(boolean normalize) { this.normalize = normalize; }
        public int getMaxDocumentChars() { return maxDocumentChars; }
        public void setMaxDocumentChars(int maxDocumentChars) { this.maxDocumentChars = maxDocumentChars; }
        public Duration getTimeout() { return timeout; }
        public void setTimeout(Duration timeout) { this.timeout = timeout; }
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

    /** 文档资料域/资料类型检索 profile。 */
    public static class RetrievalProfileProperties {
        private boolean enabled = true;
        private String domain;
        private List<String> materialTypes = new ArrayList<>();
        private String retrievalProfile;
        private String indexAlias;
        private List<String> channels = new ArrayList<>(List.of("BM25", "EXACT", "PHRASE", "DENSE_VECTOR"));
        private Map<String, Double> channelWeights = new LinkedHashMap<>();
        private String embeddingField = "embedding";
        private String embeddingProvider;
        private String embeddingModel;
        private int embeddingDimension = 0;
        private int keywordK = 20;
        private int exactK = 20;
        private int phraseK = 20;
        private int vectorK = 20;
        private int rrfK = 60;
        private int numCandidates = 100;
        private int maxChunksPerDocument = 1;
        private RerankProperties rerank = new RerankProperties();

        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
        public String getDomain() { return domain; }
        public void setDomain(String domain) { this.domain = domain; }
        public List<String> getMaterialTypes() { return materialTypes; }
        public void setMaterialTypes(List<String> materialTypes) {
            this.materialTypes = materialTypes == null ? new ArrayList<>() : new ArrayList<>(materialTypes);
        }
        public String getRetrievalProfile() { return retrievalProfile; }
        public void setRetrievalProfile(String retrievalProfile) { this.retrievalProfile = retrievalProfile; }
        public String getIndexAlias() { return indexAlias; }
        public void setIndexAlias(String indexAlias) { this.indexAlias = indexAlias; }
        public List<String> getChannels() { return channels; }
        public void setChannels(List<String> channels) {
            this.channels = channels == null ? new ArrayList<>() : new ArrayList<>(channels);
        }
        public Map<String, Double> getChannelWeights() { return channelWeights; }
        public void setChannelWeights(Map<String, Double> channelWeights) {
            this.channelWeights = channelWeights == null ? new LinkedHashMap<>() : new LinkedHashMap<>(channelWeights);
        }
        public String getEmbeddingField() { return embeddingField; }
        public void setEmbeddingField(String embeddingField) { this.embeddingField = embeddingField; }
        public String getEmbeddingProvider() { return embeddingProvider; }
        public void setEmbeddingProvider(String embeddingProvider) { this.embeddingProvider = embeddingProvider; }
        public String getEmbeddingModel() { return embeddingModel; }
        public void setEmbeddingModel(String embeddingModel) { this.embeddingModel = embeddingModel; }
        public int getEmbeddingDimension() { return embeddingDimension; }
        public void setEmbeddingDimension(int embeddingDimension) { this.embeddingDimension = embeddingDimension; }
        public int getKeywordK() { return keywordK; }
        public void setKeywordK(int keywordK) { this.keywordK = keywordK; }
        public int getExactK() { return exactK; }
        public void setExactK(int exactK) { this.exactK = exactK; }
        public int getPhraseK() { return phraseK; }
        public void setPhraseK(int phraseK) { this.phraseK = phraseK; }
        public int getVectorK() { return vectorK; }
        public void setVectorK(int vectorK) { this.vectorK = vectorK; }
        public int getRrfK() { return rrfK; }
        public void setRrfK(int rrfK) { this.rrfK = rrfK; }
        public int getNumCandidates() { return numCandidates; }
        public void setNumCandidates(int numCandidates) { this.numCandidates = numCandidates; }
        public int getMaxChunksPerDocument() { return maxChunksPerDocument; }
        public void setMaxChunksPerDocument(int maxChunksPerDocument) { this.maxChunksPerDocument = maxChunksPerDocument; }
        public RerankProperties getRerank() { return rerank; }
        public void setRerank(RerankProperties rerank) {
            this.rerank = rerank == null ? new RerankProperties() : rerank;
        }
    }

    /** 文档 rerank 开关，默认关闭。 */
    public static class RerankProperties {
        private boolean enabled = false;
        private int topN = 20;

        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
        public int getTopN() { return topN; }
        public void setTopN(int topN) { this.topN = topN; }
    }

    /** 文档本地应急禁用清单，首版不扩展统一 policy target 枚举。 */
    public static class BlocklistProperties {
        private List<String> domains = new ArrayList<>();
        private List<String> indexVersions = new ArrayList<>();
        private List<String> retrievalProfiles = new ArrayList<>();
        private List<String> profileVersions = new ArrayList<>();
        private List<String> indexAliases = new ArrayList<>();

        public List<String> getDomains() { return domains; }
        public void setDomains(List<String> domains) { this.domains = domains == null ? new ArrayList<>() : domains; }
        public List<String> getIndexVersions() { return indexVersions; }
        public void setIndexVersions(List<String> indexVersions) { this.indexVersions = indexVersions == null ? new ArrayList<>() : indexVersions; }
        public List<String> getRetrievalProfiles() { return retrievalProfiles; }
        public void setRetrievalProfiles(List<String> retrievalProfiles) { this.retrievalProfiles = retrievalProfiles == null ? new ArrayList<>() : retrievalProfiles; }
        public List<String> getProfileVersions() { return profileVersions; }
        public void setProfileVersions(List<String> profileVersions) { this.profileVersions = profileVersions == null ? new ArrayList<>() : profileVersions; }
        public List<String> getIndexAliases() { return indexAliases; }
        public void setIndexAliases(List<String> indexAliases) { this.indexAliases = indexAliases == null ? new ArrayList<>() : indexAliases; }
    }
}
