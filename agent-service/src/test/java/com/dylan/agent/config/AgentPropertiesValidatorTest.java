package com.dylan.agent.config;

import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@DisplayName("AgentPropertiesValidator")
class AgentPropertiesValidatorTest {

    private AgentProperties properties;

    @BeforeEach
    void setUp() {
        properties = DomainMetadataTestSupport.agentProperties();
    }

    @Test
    @DisplayName("完整合法运行配置不抛异常")
    void shouldPassWithValidConfig() {
        var validator = new AgentPropertiesValidator(properties);

        assertThatCode(validator::afterPropertiesSet).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("document 新分层配置可绑定到兼容访问器")
    void shouldBindDocumentHierarchicalConfig() {
        MapConfigurationPropertySource source = new MapConfigurationPropertySource();
        source.put("agent.document.enabled", "true");
        source.put("agent.document.retrieval.default-size", "5");
        source.put("agent.document.retrieval.answer-candidate-size", "30");
        source.put("agent.document.retrieval.summarize-candidate-size", "30");
        source.put("agent.document.retrieval.max-size", "30");
        source.put("agent.document.retrieval.default-mode", "HYBRID");
        source.put("agent.document.retrieval.hybrid.keyword-k", "60");
        source.put("agent.document.retrieval.hybrid.vector-k", "60");
        source.put("agent.document.retrieval.hybrid.num-candidates", "300");
        source.put("agent.document.evidence-selection.max-evidence-count", "12");
        source.put("agent.document.text-limits.max-query-text-length", "500");

        AgentProperties bound = new Binder(source)
                .bind("agent", Bindable.of(AgentProperties.class))
                .orElseThrow(IllegalStateException::new);

        assertThat(bound.getDocument().getMaxSize()).isEqualTo(30);
        assertThat(bound.getDocument().getRetrieval().getAnswerCandidateSize()).isEqualTo(30);
        assertThat(bound.getDocument().getHybrid().getNumCandidates()).isEqualTo(300);
        assertThat(bound.getDocument().getMaxEvidenceCount()).isEqualTo(12);
        assertThat(bound.getDocument().getMaxQueryTextLength()).isEqualTo(500);
    }

    @Test
    @DisplayName("defaultSize > maxSize 时启动失败")
    void shouldFailWhenDefaultAboveMax() {
        properties.getQuery().setDefaultSize(200);
        properties.getQuery().setMaxSize(100);
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("default-size");
    }

    @Test
    @DisplayName("shared-key 不足 16 字符时启动失败")
    void shouldFailWhenSharedKeyTooShort() {
        properties.getRuntime().setSharedKey("short");
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("shared-key");
    }

    @Test
    @DisplayName("route/plan path 缺失时启动失败")
    void shouldFailWhenRuntimePlanPathMissing() {
        properties.getRuntime().setPlanPath("");
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("route-path/plan-path");
    }

    @Test
    @DisplayName("embedding 启用但缺少 model 时启动失败")
    void shouldFailWhenEmbeddingModelMissing() {
        properties.getDocument().getEmbedding().setEnabled(true);
        properties.getDocument().getEmbedding().setBaseUrl("http://embedding-provider");
        properties.getDocument().getEmbedding().setDimension(1536);
        properties.getDocument().getEmbedding().setModel("");
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("agent.document.embedding.model");
    }

    @Test
    @DisplayName("rewrite 启用但 path 缺失时启动失败")
    void shouldFailWhenRewritePathMissing() {
        properties.getDocument().getRewrite().setEnabled(true);
        properties.getDocument().getRewrite().setPath("");
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("agent.document.rewrite.path");
    }

    @Test
    @DisplayName("rewrite 启用但候选数非法时启动失败")
    void shouldFailWhenRewriteMaxCandidatesInvalid() {
        properties.getDocument().getRewrite().setEnabled(true);
        properties.getDocument().getRewrite().setMaxCandidates(0);
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("agent.document.rewrite.max-candidates");
    }

    @Test
    @DisplayName("generation 启用但缺少 model 时启动失败")
    void shouldFailWhenGenerationModelMissing() {
        properties.getDocument().getGeneration().setEnabled(true);
        properties.getDocument().getGeneration().setBaseUrl("http://generation-provider");
        properties.getDocument().getGeneration().setModel("");
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("agent.document.generation.model");
    }

    @Test
    @DisplayName("answer candidate size 超过 max-size 时启动失败")
    void shouldFailWhenAnswerCandidateSizeAboveMax() {
        properties.getDocument().setAnswerCandidateSize(21);
        properties.getDocument().setMaxSize(20);
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("answer-candidate-size");
    }

    @Test
    @DisplayName("evidence selection 分组配置非法时启动失败")
    void shouldFailWhenEvidenceSelectionGroupsInvalid() {
        properties.getDocument().getEvidenceSelection().setScoreGroups(0);
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("evidence-selection");
    }

    @Test
    @DisplayName("dense_vector profile 缺少 embedding-field 时启动失败")
    void shouldFailWhenDenseVectorProfileEmbeddingFieldMissing() {
        AgentProperties.RetrievalProfileProperties profile = new AgentProperties.RetrievalProfileProperties();
        profile.setDomain("policy_document");
        profile.setMaterialTypes(java.util.List.of("tax_policy"));
        profile.setRetrievalProfile("tax-v2");
        profile.setIndexAlias("agent-doc-tax-policy-read");
        profile.setEmbeddingField("");
        properties.getDocument().getRetrievalProfiles().put("tax-v2", profile);
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("embedding-field");
    }

    @Test
    @DisplayName("dense_vector profile 的 embedding dimension 为负数时启动失败")
    void shouldFailWhenProfileEmbeddingDimensionNegative() {
        AgentProperties.RetrievalProfileProperties profile = validProfile("tax-v2", "tax_policy");
        profile.setEmbeddingDimension(-1);
        properties.getDocument().getRetrievalProfiles().put("tax-v2", profile);
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("embedding-dimension");
    }

    @Test
    @DisplayName("启用 rerank 但 top-n 非法时启动失败")
    void shouldFailWhenRerankTopNInvalid() {
        AgentProperties.RetrievalProfileProperties profile = new AgentProperties.RetrievalProfileProperties();
        profile.setDomain("policy_document");
        profile.setMaterialTypes(java.util.List.of("tax_policy"));
        profile.setRetrievalProfile("tax-v2");
        profile.setIndexAlias("agent-doc-tax-policy-read");
        profile.getRerank().setEnabled(true);
        profile.getRerank().setTopN(0);
        properties.getDocument().getRetrievalProfiles().put("tax-v2", profile);
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("rerank.top-n");
    }

    @Test
    @DisplayName("profile 启用 rerank 但 provider 未启用时启动失败")
    void shouldFailWhenProfileRerankEnabledButProviderDisabled() {
        AgentProperties.RetrievalProfileProperties profile = validProfile("tax-rerank", "tax_policy");
        profile.getRerank().setEnabled(true);
        profile.getRerank().setTopN(10);
        properties.getDocument().getRetrievalProfiles().put("tax-rerank", profile);
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("agent.document.rerank");
    }

    @Test
    @DisplayName("启用 profile 但缺少 index-alias 时启动失败")
    void shouldFailWhenRetrievalProfileIndexAliasMissing() {
        AgentProperties.RetrievalProfileProperties profile = new AgentProperties.RetrievalProfileProperties();
        profile.setDomain("policy_document");
        profile.setMaterialTypes(java.util.List.of("tax_policy"));
        profile.setRetrievalProfile("tax-v2");
        profile.setIndexAlias("");
        properties.getDocument().getRetrievalProfiles().put("tax-v2", profile);
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("index-alias");
    }

    @Test
    @DisplayName("启用 profile 但缺少 material-types 时启动失败")
    void shouldFailWhenRetrievalProfileMaterialTypesMissing() {
        AgentProperties.RetrievalProfileProperties profile = validProfile("tax-v2", "tax_policy");
        profile.setMaterialTypes(java.util.List.of(" "));
        properties.getDocument().getRetrievalProfiles().put("tax-v2", profile);
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("material-types");
    }

    @Test
    @DisplayName("同一 domain/materialType 被多个 profile 绑定时启动失败")
    void shouldFailWhenMaterialTypeMappedByMultipleProfiles() {
        properties.getDocument().getRetrievalProfiles().put("tax-v2", validProfile("tax-v2", "tax_policy"));
        properties.getDocument().getRetrievalProfiles().put("tax-strict", validProfile("tax-strict", "tax_policy"));
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("material-types");
    }

    @Test
    @DisplayName("profile 召回候选数超过系统上限时启动失败")
    void shouldFailWhenProfileCandidateAboveSystemCap() {
        AgentProperties.RetrievalProfileProperties profile = validProfile("tax-v2", "tax_policy");
        profile.setKeywordK(10_001);
        properties.getDocument().getRetrievalProfiles().put("tax-v2", profile);
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("系统上限");
    }

    @Test
    @DisplayName("profile domain 不支持 DOCUMENT_RETRIEVABLE 时启动失败")
    void shouldFailWhenProfileDomainDoesNotSupportDocumentRole() {
        AgentProperties.RetrievalProfileProperties profile = validProfile("employee-profile", "policy");
        profile.setDomain("employee");
        properties.getDocument().getRetrievalProfiles().put("employee-profile", profile);
        var validator = new AgentPropertiesValidator(properties, DomainMetadataTestSupport.catalogView());

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("DOCUMENT_RETRIEVABLE");
    }

    private AgentProperties.RetrievalProfileProperties validProfile(String retrievalProfile, String materialType) {
        AgentProperties.RetrievalProfileProperties profile = new AgentProperties.RetrievalProfileProperties();
        profile.setDomain("policy_document");
        profile.setMaterialTypes(java.util.List.of(materialType));
        profile.setRetrievalProfile(retrievalProfile);
        profile.setIndexAlias("agent-doc-tax-policy-read");
        return profile;
    }
}
