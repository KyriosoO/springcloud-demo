package com.dylan.agent.config;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Map;

/**
 * 启动时校验 AgentProperties 中仍由本地配置承载的运行参数。
 *
 * <p>Capability 覆盖、权限权威源和领域事实已分别由 Kernel/Metadata/Auth 门禁校验，
 * 这里不再读取旧 intent role 或旧处理器注册表，避免生产上下文保留双运行态。
 */
@Component
public class AgentPropertiesValidator implements InitializingBean {

    private final AgentProperties properties;
    private final DomainCatalogView domainCatalogView;

    public AgentPropertiesValidator(AgentProperties properties) {
        this(properties, null);
    }

    @Autowired
    public AgentPropertiesValidator(AgentProperties properties, DomainCatalogView domainCatalogView) {
        this.properties = properties;
        this.domainCatalogView = domainCatalogView;
    }

    @Override
    public void afterPropertiesSet() {
        validateRuntime();
        validateQuery();
        validateAggregateConfig();
        validateDocumentConfig();
        validateConversation();
    }

    private void validateRuntime() {
        var rt = properties.getRuntime();
        if (rt.getBaseUrl() == null || rt.getBaseUrl().isBlank()) {
            throw new IllegalStateException("agent.runtime.base-url 必须配置。");
        }
        if (rt.getSharedKey() == null || rt.getSharedKey().length() < 16) {
            throw new IllegalStateException("agent.runtime.shared-key 长度必须至少 16。");
        }
        if (rt.getConnectTimeout() == null || rt.getReadTimeout() == null) {
            throw new IllegalStateException("agent.runtime 超时配置必须提供。");
        }
        if (rt.getConnectTimeout().isZero() || rt.getConnectTimeout().isNegative()
                || rt.getReadTimeout().isZero() || rt.getReadTimeout().isNegative()) {
            throw new IllegalStateException("agent.runtime 超时配置必须为正数。");
        }
        if (rt.getMaxResponseBytes() <= 0) {
            throw new IllegalStateException("agent.runtime.max-response-bytes 必须为正数。");
        }
        if (rt.getRoutePath() == null || rt.getRoutePath().isBlank()
                || rt.getPlanPath() == null || rt.getPlanPath().isBlank()) {
            throw new IllegalStateException("agent.runtime route-path/plan-path 必须配置。");
        }
        if (rt.getMaxRepairAttempts() < 0 || rt.getMaxRepairAttempts() > 3) {
            throw new IllegalStateException("agent.runtime.max-repair-attempts 必须在 0..3。");
        }
    }

    private void validateQuery() {
        var q = properties.getQuery();
        if (q.getDefaultSize() <= 0) {
            throw new IllegalStateException("agent.query.default-size 必须为正数。");
        }
        if (q.getMaxSize() <= 0) {
            throw new IllegalStateException("agent.query.max-size 必须为正数。");
        }
        if (q.getDefaultSize() > q.getMaxSize()) {
            throw new IllegalStateException("agent.query.default-size 不能超过 max-size。");
        }
        if (q.getMaxSize() > q.getMaxResultWindow()) {
            throw new IllegalStateException("agent.query.max-size 不能超过 max-result-window。");
        }
        if (q.getMaxFilters() <= 0) {
            throw new IllegalStateException("agent.query.max-filters 必须为正数。");
        }
        if (q.getMaxInValues() <= 0) {
            throw new IllegalStateException("agent.query.max-in-values 必须为正数。");
        }
        if (q.getMaxFilterValueLength() <= 0) {
            throw new IllegalStateException("agent.query.max-filter-value-length 必须为正数。");
        }
        if (q.getMaxDownstreamResponseBytes() <= 0) {
            throw new IllegalStateException("agent.query.max-downstream-response-bytes 必须为正数。");
        }
    }

    private void validateAggregateConfig() {
        var a = properties.getAggregate();
        if (a == null) {
            throw new IllegalStateException("agent.aggregate 必须配置。");
        }
        if (a.getMaxMetrics() <= 0) {
            throw new IllegalStateException("agent.aggregate.max-metrics 必须为正数。");
        }
        if (a.getMaxGroupFields() <= 0) {
            throw new IllegalStateException("agent.aggregate.max-group-fields 必须为正数。");
        }
        if (a.getDefaultMaxRows() <= 0) {
            throw new IllegalStateException("agent.aggregate.default-max-rows 必须为正数。");
        }
        if (a.getMaxMaxRows() <= 0) {
            throw new IllegalStateException("agent.aggregate.max-max-rows 必须为正数。");
        }
        if (a.getDefaultMaxRows() > a.getMaxMaxRows()) {
            throw new IllegalStateException("agent.aggregate.default-max-rows 不能超过 max-max-rows。");
        }
    }

    private void validateDocumentConfig() {
        var d = properties.getDocument();
        if (d.getDefaultSize() <= 0) {
            throw new IllegalStateException("agent.document.default-size 必须为正数。");
        }
        if (d.getMaxSize() <= 0) {
            throw new IllegalStateException("agent.document.max-size 必须为正数。");
        }
        if (d.getDefaultSize() > d.getMaxSize()) {
            throw new IllegalStateException("agent.document.default-size 不能超过 max-size。");
        }
        if (d.getAnswerCandidateSize() <= 0 || d.getAnswerCandidateSize() > d.getMaxSize()) {
            throw new IllegalStateException("agent.document.answer-candidate-size 必须为正数且不能超过 max-size。");
        }
        if (d.getSummarizeCandidateSize() <= 0 || d.getSummarizeCandidateSize() > d.getMaxSize()) {
            throw new IllegalStateException("agent.document.summarize-candidate-size 必须为正数且不能超过 max-size。");
        }
        if (d.getMaxEvidenceCount() <= 0 || d.getMaxEvidenceCount() > d.getMaxSize()) {
            throw new IllegalStateException("agent.document.max-evidence-count 必须为正数且不能超过 max-size。");
        }
        if (d.getEvidenceSelection().getScoreGroups() <= 0
                || d.getEvidenceSelection().getMinTopGroupSize() <= 0) {
            throw new IllegalStateException("agent.document.evidence-selection 分组配置必须为正数。");
        }
        if (d.getContextWindow().getBeforeChunks() < 0 || d.getContextWindow().getAfterChunks() < 0) {
            throw new IllegalStateException("agent.document.context-window before/after chunks 不能为负数。");
        }
        if (d.getMaxQueryTextLength() <= 0 || d.getMaxSnippetChars() <= 0 || d.getMaxSummaryChars() <= 0) {
            throw new IllegalStateException("agent.document 文本长度配置必须为正数。");
        }
        validateDocumentEmbeddingConfig(d);
        validateDocumentGenerationConfig(d);
        validateDocumentHybridConfig(d);
        validateDocumentRetrievalProfiles(d);
    }

    private void validateDocumentEmbeddingConfig(AgentProperties.DocumentProperties d) {
        var e = d.getEmbedding();
        if (e.getTimeout() == null || e.getTimeout().isZero() || e.getTimeout().isNegative()) {
            throw new IllegalStateException("agent.document.embedding.timeout 必须为正数。");
        }
        if (e.isEnabled()) {
            if (e.getBaseUrl() == null || e.getBaseUrl().isBlank()) {
                throw new IllegalStateException("agent.document.embedding.base-url 必须配置。");
            }
            if (e.getModel() == null || e.getModel().isBlank()) {
                throw new IllegalStateException("agent.document.embedding.model 必须配置。");
            }
            if (e.getDimension() <= 0) {
                throw new IllegalStateException("agent.document.embedding.dimension 必须为正数。");
            }
        }
    }

    private void validateDocumentGenerationConfig(AgentProperties.DocumentProperties d) {
        var g = d.getGeneration();
        if (g.getTimeout() == null || g.getTimeout().isZero() || g.getTimeout().isNegative()) {
            throw new IllegalStateException("agent.document.generation.timeout 必须为正数。");
        }
        if (g.getMaxContextChars() <= 0 || g.getMaxEvidenceChars() <= 0 || g.getMaxOutputChars() <= 0) {
            throw new IllegalStateException("agent.document.generation 文本预算必须为正数。");
        }
        if (g.getMaxEvidenceChars() > g.getMaxContextChars()) {
            throw new IllegalStateException("agent.document.generation.max-evidence-chars 不能超过 max-context-chars。");
        }
        if (g.isEnabled()) {
            if (g.getBaseUrl() == null || g.getBaseUrl().isBlank()) {
                throw new IllegalStateException("agent.document.generation.base-url 必须配置。");
            }
            if (g.getModel() == null || g.getModel().isBlank()) {
                throw new IllegalStateException("agent.document.generation.model 必须配置。");
            }
        }
        if (!"FALLBACK_EXTRACTIVE".equals(g.getFailurePolicy()) && !"REFUSE".equals(g.getFailurePolicy())) {
            throw new IllegalStateException("agent.document.generation.failure-policy 必须为 FALLBACK_EXTRACTIVE 或 REFUSE。");
        }
    }

    private void validateDocumentHybridConfig(AgentProperties.DocumentProperties d) {
        var h = d.getHybrid();
        if (h.getKeywordK() <= 0 || h.getVectorK() <= 0 || h.getRrfK() <= 0 || h.getNumCandidates() <= 0) {
            throw new IllegalStateException("agent.document.hybrid 参数必须为正数。");
        }
    }

    private void validateDocumentRetrievalProfiles(AgentProperties.DocumentProperties d) {
        boolean hasEnabledProfile = d.getRetrievalProfiles().values().stream()
                .anyMatch(profile -> profile != null && profile.isEnabled());
        if (d.isEnabled() && !hasEnabledProfile) {
            throw new IllegalStateException("agent.document.retrieval-profiles 至少需要一个启用的 profile。");
        }
        Map<String, String> profileByDomainMaterialType = new LinkedHashMap<>();
        Map<String, String> profileByDomainName = new LinkedHashMap<>();
        for (var entry : d.getRetrievalProfiles().entrySet()) {
            var profile = entry.getValue();
            if (profile == null || !profile.isEnabled()) {
                continue;
            }
            String prefix = "agent.document.retrieval-profiles." + entry.getKey();
            if (profile.getDomain() == null || profile.getDomain().isBlank()) {
                throw new IllegalStateException(prefix + ".domain 必须配置。");
            }
            validateDocumentDomain(prefix, profile.getDomain());
            if (profile.getRetrievalProfile() == null || profile.getRetrievalProfile().isBlank()) {
                throw new IllegalStateException(prefix + ".retrieval-profile 必须配置。");
            }
            String domainProfileKey = normalizeKey(profile.getDomain()) + "/"
                    + normalizeKey(profile.getRetrievalProfile());
            String previousProfile = profileByDomainName.putIfAbsent(domainProfileKey, entry.getKey());
            if (previousProfile != null) {
                throw new IllegalStateException(prefix + ".retrieval-profile 在同一 domain 下重复。");
            }
            var materialTypes = normalizedMaterialTypes(profile);
            if (materialTypes.isEmpty()) {
                throw new IllegalStateException(prefix + ".material-types 至少配置一个资料类型。");
            }
            for (String materialType : materialTypes) {
                String routeKey = normalizeKey(profile.getDomain()) + "/" + normalizeKey(materialType);
                String previous = profileByDomainMaterialType.putIfAbsent(routeKey, entry.getKey());
                if (previous != null) {
                    throw new IllegalStateException(prefix + ".material-types 与其他 profile 重复。");
                }
            }
            if (profile.getIndexAlias() == null || profile.getIndexAlias().isBlank()) {
                throw new IllegalStateException(prefix + ".index-alias 必须配置。");
            }
            if (profile.getChannels() == null || profile.getChannels().isEmpty()) {
                throw new IllegalStateException(prefix + ".channels 至少配置一个通道。");
            }
            for (String channel : profile.getChannels()) {
                if (!isSupportedRetrievalChannel(channel)) {
                    throw new IllegalStateException(prefix + ".channels 包含不支持的通道。");
                }
            }
            if (profile.getKeywordK() <= 0 || profile.getExactK() <= 0 || profile.getPhraseK() <= 0
                    || profile.getVectorK() <= 0 || profile.getRrfK() <= 0
                    || profile.getNumCandidates() <= 0 || profile.getMaxChunksPerDocument() <= 0) {
                throw new IllegalStateException(prefix + " 检索参数必须为正数。");
            }
            if (profile.getKeywordK() > 10_000 || profile.getExactK() > 10_000
                    || profile.getPhraseK() > 10_000 || profile.getVectorK() > 10_000
                    || profile.getNumCandidates() > 10_000) {
                throw new IllegalStateException(prefix + " 召回候选参数超过系统上限。");
            }
            if (profile.getRrfK() > 1000) {
                throw new IllegalStateException(prefix + ".rrf-k 超过系统上限。");
            }
            if (profile.getMaxChunksPerDocument() > d.getMaxSize()) {
                throw new IllegalStateException(prefix + ".max-chunks-per-document 不能超过 max-size。");
            }
            if (profile.getChannelWeights().values().stream()
                    .anyMatch(weight -> weight == null || !Double.isFinite(weight) || weight <= 0.0d)) {
                throw new IllegalStateException(prefix + ".channel-weights 必须为正数。");
            }
            if (profile.getChannelWeights().keySet().stream().anyMatch(channel -> !isSupportedRetrievalChannel(channel))) {
                throw new IllegalStateException(prefix + ".channel-weights 包含不支持的通道。");
            }
            if (profile.getChannels().stream().anyMatch(channel -> "DENSE_VECTOR".equalsIgnoreCase(channel))
                    && (profile.getEmbeddingField() == null || profile.getEmbeddingField().isBlank())) {
                throw new IllegalStateException(prefix + ".embedding-field 必须配置。");
            }
            if (profile.getRerank().isEnabled() && profile.getRerank().getTopN() <= 0) {
                throw new IllegalStateException(prefix + ".rerank.top-n 必须为正数。");
            }
            if (profile.getRerank().isEnabled() && profile.getRerank().getTopN() > d.getMaxSize()) {
                throw new IllegalStateException(prefix + ".rerank.top-n 不能超过 max-size。");
            }
        }
    }

    private void validateDocumentDomain(String prefix, String domain) {
        if (domainCatalogView == null) {
            return;
        }
        try {
            domainCatalogView.requireDomain(domain.trim(), AdapterRole.DOCUMENT_RETRIEVABLE);
        } catch (RuntimeException ex) {
            throw new IllegalStateException(prefix + ".domain 必须存在且支持 DOCUMENT_RETRIEVABLE。", ex);
        }
    }

    private static LinkedHashSet<String> normalizedMaterialTypes(AgentProperties.RetrievalProfileProperties profile) {
        LinkedHashSet<String> values = new LinkedHashSet<>();
        if (profile.getMaterialTypes() != null) {
            profile.getMaterialTypes().stream()
                    .filter(value -> value != null && !value.isBlank())
                    .map(String::trim)
                    .forEach(values::add);
        }
        return values;
    }

    private static String normalizeKey(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private static boolean isSupportedRetrievalChannel(String channel) {
        if (channel == null || channel.isBlank()) {
            return false;
        }
        String normalized = channel.trim().toUpperCase(java.util.Locale.ROOT);
        return "KEYWORD".equals(normalized)
                || "BM25".equals(normalized)
                || "EXACT".equals(normalized)
                || "PHRASE".equals(normalized)
                || "VECTOR".equals(normalized)
                || "DENSE_VECTOR".equals(normalized);
    }

    private void validateConversation() {
        var c = properties.getConversation();
        if (c.getRecentTurnLimit() <= 0) {
            throw new IllegalStateException("agent.conversation.recent-turn-limit 必须为正数。");
        }
        if (c.getRetentionDays() <= 0) {
            throw new IllegalStateException("agent.conversation.retention-days 必须为正数。");
        }
        if (c.getCleanupDelay() == null || c.getCleanupDelay().isZero() || c.getCleanupDelay().isNegative()) {
            throw new IllegalStateException("agent.conversation.cleanup-delay 必须为正数。");
        }
    }
}
