package com.dylan.agent.config;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.stereotype.Component;

/** 仅校验仍由 Agent 本地配置拥有的技术参数。 */
@Component
public class AgentPropertiesValidator implements InitializingBean {
    private final AgentProperties properties;

    public AgentPropertiesValidator(AgentProperties properties) { this.properties = properties; }

    @Override
    public void afterPropertiesSet() {
        validateRuntime();
        validateProfile();
        validateQuery();
        validateAggregate();
        validateDocument();
        validateConversation();
    }

    private void validateProfile() {
        var value = required(properties.getProfile(), "agent.profile 必须配置。");
        text(value.getAgentId(), "agent.profile.agent-id 必须配置。");
        text(value.getProfileVersion(), "agent.profile.profile-version 必须配置。");
        if (value.getAllowedDomains().isEmpty()
                || value.getAllowedDomains().stream().anyMatch(domain -> domain == null || domain.isBlank())) {
            throw new IllegalStateException("agent.profile.allowed-domains 必须是非空合法集合。");
        }
    }

    private void validateRuntime() {
        var value = required(properties.getRuntime(), "agent.runtime 必须配置。");
        text(value.getBaseUrl(), "agent.runtime.base-url 必须配置。");
        if (value.getSharedKey() == null || value.getSharedKey().length() < 16) {
            throw new IllegalStateException("agent.runtime.shared-key 长度必须至少 16。");
        }
        positive(value.getConnectTimeout(), "agent.runtime.connect-timeout 必须为正数。");
        positive(value.getReadTimeout(), "agent.runtime.read-timeout 必须为正数。");
        if (value.getMaxResponseBytes() <= 0) {
            throw new IllegalStateException("agent.runtime.max-response-bytes 必须为正数。");
        }
        text(value.getRoutePath(), "agent.runtime.route-path 必须配置。");
        text(value.getPlanPath(), "agent.runtime.plan-path 必须配置。");
        if (value.getMaxRepairAttempts() < 0 || value.getMaxRepairAttempts() > 3) {
            throw new IllegalStateException("agent.runtime.max-repair-attempts 必须在 0..3。");
        }
    }

    private void validateQuery() {
        var value = required(properties.getQuery(), "agent.query 必须配置。");
        if (value.getDefaultSize() <= 0 || value.getMaxSize() <= 0
                || value.getDefaultSize() > value.getMaxSize()
                || value.getMaxSize() > value.getMaxResultWindow()) {
            throw new IllegalStateException("agent.query size/window 配置非法。");
        }
        if (value.getMaxFilters() <= 0 || value.getMaxInValues() <= 0
                || value.getMaxFilterValueLength() <= 0 || value.getMaxDownstreamResponseBytes() <= 0) {
            throw new IllegalStateException("agent.query 限额必须为正数。");
        }
    }

    private void validateAggregate() {
        var value = required(properties.getAggregate(), "agent.aggregate 必须配置。");
        if (value.getMaxMetrics() <= 0 || value.getMaxGroupFields() <= 0
                || value.getDefaultMaxRows() <= 0 || value.getMaxMaxRows() <= 0
                || value.getDefaultMaxRows() > value.getMaxMaxRows()) {
            throw new IllegalStateException("agent.aggregate 限额配置非法。");
        }
    }

    private void validateDocument() {
        var value = required(properties.getDocument(), "agent.document 必须配置。");
        var acl = required(value.getAcl(), "agent.document.acl 必须配置。");
        text(acl.getScopeUrl(), "agent.document.acl.scope-url 必须配置。");
        positive(acl.getTimeout(), "agent.document.acl.timeout 必须为正数。");
        positive(acl.getMaxAuthorityEvidenceTtl(), "agent.document.acl.max-authority-evidence-ttl 必须为正数。");
        positive(acl.getFinalDecisionMaxAge(), "agent.document.acl.final-decision-max-age 必须为正数。");
        if (acl.getMaxDepartments() <= 0 || acl.getMaxRoles() <= 0 || acl.getMaxAttributes() <= 0
                || acl.getMaxAllowedDocumentIds() <= 0 || acl.getMaxDeniedDocumentIds() <= 0
                || acl.getMaxAstNodes() <= 0 || acl.getMaxAstDepth() <= 0 || acl.getMaxTerms() <= 0
                || acl.getMaxCanonicalBytes() <= 0 || acl.getMaxWireBytes() <= 0
                || acl.getMaxCurrentnessCandidates() <= 0) {
            throw new IllegalStateException("agent.document.acl compiler limits 必须为正数。");
        }
    }

    private void validateConversation() {
        var value = required(properties.getConversation(), "agent.conversation 必须配置。");
        if (value.getRecentTurnLimit() <= 0 || value.getRetentionDays() <= 0) {
            throw new IllegalStateException("agent.conversation turn/retention 必须为正数。");
        }
        positive(value.getCleanupDelay(), "agent.conversation.cleanup-delay 必须为正数。");
    }

    private static void positive(java.time.Duration value, String message) {
        if (value == null || value.isZero() || value.isNegative()) throw new IllegalStateException(message);
    }

    private static void text(String value, String message) {
        if (value == null || value.isBlank()) throw new IllegalStateException(message);
    }

    private static <T> T required(T value, String message) {
        if (value == null) throw new IllegalStateException(message);
        return value;
    }
}
