package com.dylan.agent.config;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.stereotype.Component;

/**
 * 启动时校验 AgentProperties 中仍由本地配置承载的运行参数。
 *
 * <p>Capability 覆盖、权限权威源和领域事实已分别由 Kernel/Metadata/Auth 门禁校验，
 * 这里不再读取旧 intent role 或旧处理器注册表，避免生产上下文保留双运行态。
 */
@Component
public class AgentPropertiesValidator implements InitializingBean {

    private final AgentProperties properties;

    public AgentPropertiesValidator(AgentProperties properties) {
        this.properties = properties;
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
        if (d.getMaxEvidenceCount() <= 0 || d.getMaxEvidenceCount() > d.getMaxSize()) {
            throw new IllegalStateException("agent.document.max-evidence-count 必须为正数且不能超过 max-size。");
        }
        if (d.getMaxQueryTextLength() <= 0 || d.getMaxSnippetChars() <= 0 || d.getMaxSummaryChars() <= 0) {
            throw new IllegalStateException("agent.document 文本长度配置必须为正数。");
        }
        validateDocumentEmbeddingConfig(d);
        validateDocumentGenerationConfig(d);
        validateDocumentHybridConfig(d);
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
        if (g.isEnabled() && (g.getBaseUrl() == null || g.getBaseUrl().isBlank())) {
            throw new IllegalStateException("agent.document.generation.base-url 必须配置。");
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
