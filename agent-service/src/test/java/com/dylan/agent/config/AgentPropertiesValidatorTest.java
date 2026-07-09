package com.dylan.agent.config;

import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

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
    @DisplayName("启用 rerank 但 top-n 非法时启动失败")
    void shouldFailWhenRerankTopNInvalid() {
        AgentProperties.RetrievalProfileProperties profile = new AgentProperties.RetrievalProfileProperties();
        profile.setDomain("policy_document");
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
    @DisplayName("启用 profile 但缺少 index-alias 时启动失败")
    void shouldFailWhenRetrievalProfileIndexAliasMissing() {
        AgentProperties.RetrievalProfileProperties profile = new AgentProperties.RetrievalProfileProperties();
        profile.setDomain("policy_document");
        profile.setRetrievalProfile("tax-v2");
        profile.setIndexAlias("");
        properties.getDocument().getRetrievalProfiles().put("tax-v2", profile);
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("index-alias");
    }
}
