package com.dylan.esquery.config;

import static com.dylan.esquery.KnowledgeTestProfiles.enabledProperties;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.LinkedHashMap;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.io.ClassPathResource;
import org.springframework.mock.env.MockEnvironment;

import com.dylan.esquery.config.KnowledgeSearchProperties.KnowledgeSearchProfile;
import com.fasterxml.jackson.databind.ObjectMapper;

class KnowledgeSearchPropertiesTest {

	@Test
	void shippedLiveProfileEnablesOnlyMeasuredPolicyMatchingAndAllowsExplicitRollback() throws Exception {
		MockEnvironment environment = new MockEnvironment()
				.withProperty("AGENT_KNOWLEDGE_READ_ALIAS", "test-read")
				.withProperty("AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME", "test-index")
				.withProperty("AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID", "test-uuid")
				.withProperty("AGENT_KNOWLEDGE_MAPPING_VERSION", "test-mapping-v1")
				.withProperty("AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID", "0".repeat(64))
				.withProperty("AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID", "1".repeat(64));
		new YamlPropertySourceLoader().load("knowledge-live", new ClassPathResource("application-knowledge-live.yml"))
				.forEach(source -> environment.getPropertySources().addLast(source));
		KnowledgeSearchProperties properties = Binder.get(environment)
				.bind("es.query.knowledge", Bindable.of(KnowledgeSearchProperties.class)).get();
		properties.afterPropertiesSet();
		assertThat(properties.isEnabled()).isTrue();
		assertThat(properties.usesExpectedIndexTarget()).isFalse();
		assertThat(properties.getProfiles()).containsOnlyKeys("tax-policy-v1", "tax-law-v1");
		KnowledgeSearchProfile policy = properties.requireProfile("tax.policy", "tax-policy-v1");
		assertThat(policy.isDocumentNumberMatching()).isTrue();
		assertThat(policy.getMaxCandidates()).isEqualTo(20);
		assertThat(policy.getSourceFields().get("document-number")).isEqualTo("documentNo");
		assertThat(properties.requireProfile("tax.law", "tax-law-v1").isDocumentNumberMatching()).isFalse();
		assertThatThrownBy(() -> policy.setDocumentNumberMatching(false)).isInstanceOf(IllegalStateException.class);

		environment.withProperty("es.query.knowledge.profiles.tax-policy-v1.document-number-matching", "false");
		KnowledgeSearchProperties rollback = Binder.get(environment)
				.bind("es.query.knowledge", Bindable.of(KnowledgeSearchProperties.class)).get();
		rollback.afterPropertiesSet();
		assertThat(rollback.requireProfile("tax.policy", "tax-policy-v1").isDocumentNumberMatching()).isFalse();
	}

	@Test
	void shippedDefaultConfigurationKeepsKnowledgeDisabled() throws Exception {
		MockEnvironment environment = new MockEnvironment();
		new YamlPropertySourceLoader().load("application", new ClassPathResource("application.yml"))
				.forEach(source -> environment.getPropertySources().addLast(source));
		KnowledgeSearchProperties properties = Binder.get(environment)
				.bind("es.query.knowledge", Bindable.of(KnowledgeSearchProperties.class)).get();
		properties.afterPropertiesSet();
		assertThat(properties.isEnabled()).isFalse();
		assertThat(properties.usesExpectedIndexTarget()).isFalse();
		assertThat(properties.getProfiles()).isEmpty();
	}

	@Test
	void disabledConfigurationDoesNotRequireProfiles() {
		KnowledgeSearchProperties properties = new KnowledgeSearchProperties();
		properties.afterPropertiesSet();
		assertThat(properties.isEnabled()).isFalse();
	}

	@Test
	void enabledConfigurationRequiresExactDomainProfilePair() {
		KnowledgeSearchProperties properties = enabledProperties("0".repeat(64));
		KnowledgeSearchProfile profile = properties.requireProfile("tax.policy", "tax-policy-v1");
		assertThat(profile.getReadAlias())
				.isEqualTo("agent-doc-tax-policy-v2-read");
		assertThatThrownBy(() -> properties.requireProfile("tax.law", "tax-policy-v1"))
				.isInstanceOf(RuntimeException.class);
		assertThatThrownBy(() -> profile.setReadAlias("changed-after-startup"))
				.isInstanceOf(IllegalStateException.class);
	}

	@Test
	void enabledConfigurationRejectsMissingProfiles() {
		KnowledgeSearchProperties properties = new KnowledgeSearchProperties();
		properties.setEnabled(true);
		assertThatThrownBy(properties::afterPropertiesSet)
				.isInstanceOf(IllegalStateException.class);
	}

	@Test
	void documentNumberFlagDefaultsOffAndIsFrozenWithTheProfile() {
		KnowledgeSearchProfile original = enabledProperties("0".repeat(64)).requireProfile("tax.policy", "tax-policy-v1");
		assertThat(original.isDocumentNumberMatching()).isFalse();
		assertThatThrownBy(() -> original.setDocumentNumberMatching(true)).isInstanceOf(IllegalStateException.class);
		KnowledgeSearchProfile profile = copyOf(original);
		profile.setDocumentNumberMatching(true);
		KnowledgeSearchProperties properties = new KnowledgeSearchProperties();
		properties.setEnabled(true);
		properties.setProfiles(Map.of("tax-policy-v1", profile));
		properties.afterPropertiesSet();
		assertThat(properties.requireProfile("tax.policy", "tax-policy-v1").isDocumentNumberMatching()).isTrue();
		assertThatThrownBy(() -> profile.setDocumentNumberMatching(false)).isInstanceOf(IllegalStateException.class);
	}

	@Test
	void bindsDocumentNumberFlagAsABooleanAndRejectsMalformedValues() {
		String key = "es.query.knowledge.profiles.tax-policy-v1.document-number-matching";
		for (String value : new String[] {"true", "false"}) {
			KnowledgeSearchProperties properties = new Binder(new MapConfigurationPropertySource(Map.of(key, value)))
					.bind("es.query.knowledge", Bindable.of(KnowledgeSearchProperties.class)).get();
			assertThat(properties.getProfiles().get("tax-policy-v1").isDocumentNumberMatching())
					.isEqualTo(Boolean.parseBoolean(value));
		}
		assertThatThrownBy(() -> new Binder(new MapConfigurationPropertySource(Map.of(key, "enabled")))
				.bind("es.query.knowledge", Bindable.of(KnowledgeSearchProperties.class)))
				.isInstanceOf(org.springframework.boot.context.properties.bind.BindException.class);
	}

	@Test
	void enabledConfigurationRejectsAmbiguousSourceMappings() {
		KnowledgeSearchProperties baseline = enabledProperties("0".repeat(64));
		KnowledgeSearchProfile source = baseline.requireProfile("tax.policy", "tax-policy-v1");
		KnowledgeSearchProfile profile = copyOf(source);
		Map<String, String> fields = new LinkedHashMap<>(profile.getSourceFields());
		fields.put("policy-ref", fields.get("material-type"));
		profile.setSourceFields(fields);
		KnowledgeSearchProperties properties = new KnowledgeSearchProperties();
		properties.setEnabled(true);
		properties.setProfiles(Map.of("tax-policy-v1", profile));
		assertThatThrownBy(properties::afterPropertiesSet).isInstanceOf(IllegalStateException.class);
	}

	@Test
	void enabledConfigurationRejectsUnsupportedDomainProfilePairs() {
		KnowledgeSearchProperties baseline = enabledProperties("0".repeat(64));
		KnowledgeSearchProfile profile = copyOf(
				baseline.requireProfile("tax.policy", "tax-policy-v1"));
		profile.setLogicalDomainId("tax.unknown");
		KnowledgeSearchProperties properties = new KnowledgeSearchProperties();
		properties.setEnabled(true);
		properties.setProfiles(Map.of("tax-unknown-v1", profile));
		assertThatThrownBy(properties::afterPropertiesSet)
				.isInstanceOf(IllegalStateException.class);
	}

	@Test
	void bIsolationSwitchRejectsMalformedAndUnboundValues() {
		for (String value : new String[] {"TRUE", "yes", "enabled", "", " true "}) {
			KnowledgeSearchProperties properties = new KnowledgeSearchProperties();
			properties.setBIsolationFixedTarget(value);
			assertThatThrownBy(properties::afterPropertiesSet).isInstanceOf(IllegalStateException.class);
		}
		KnowledgeSearchProperties strayBinding = new KnowledgeSearchProperties();
		strayBinding.setBIsolationRunId("b-run-12345");
		assertThatThrownBy(strayBinding::afterPropertiesSet).isInstanceOf(IllegalStateException.class);

		KnowledgeSearchProperties missingRun = new KnowledgeSearchProperties();
		missingRun.setBIsolationFixedTarget("true");
		assertThatThrownBy(missingRun::afterPropertiesSet).isInstanceOf(IllegalStateException.class);
		KnowledgeSearchProperties disabledKnowledge = new KnowledgeSearchProperties();
		disabledKnowledge.setBIsolationFixedTarget("true");
		disabledKnowledge.setBIsolationRunId("b-run-12345");
		assertThatThrownBy(disabledKnowledge::afterPropertiesSet).isInstanceOf(IllegalStateException.class);
		for (String runId : new String[] {"tiny", "B-run-12345", "../escape", "b-run-12345 "}) {
			KnowledgeSearchProperties invalidRun = new KnowledgeSearchProperties();
			invalidRun.setEnabled(true);
			invalidRun.setBIsolationFixedTarget("true");
			invalidRun.setBIsolationRunId(runId);
			assertThatThrownBy(invalidRun::afterPropertiesSet).isInstanceOf(IllegalStateException.class);
		}
		assertThatThrownBy(() -> new Binder(new MapConfigurationPropertySource(Map.of(
				"es.query.knowledge.b-isolation-fixed-target", "unknown")))
				.bind("es.query.knowledge", Bindable.of(KnowledgeSearchProperties.class)).get()
				.afterPropertiesSet()).isInstanceOf(IllegalStateException.class);
	}

	@Test
	void bIsolationRequiresRunOwnedAliasAndTwoProfilesOnTheSamePhysicalIndex() {
		KnowledgeSearchProperties valid = bProperties("b-b-run-12345-0123456789abcdef-read", "test-index", "test-uuid",
				"test-mapping-v1", "b-b-run-12345-0123456789abcdef-read", "test-index", "test-uuid",
				"test-mapping-v1");
		valid.afterPropertiesSet();
		assertThat(valid.usesExpectedIndexTarget()).isTrue();
		assertThatThrownBy(() -> valid.setBIsolationFixedTarget("false"))
				.isInstanceOf(IllegalStateException.class);
		assertThatThrownBy(() -> valid.setProfiles(Map.of())).isInstanceOf(IllegalStateException.class);

		for (String[] mismatch : new String[][] {
				{"agent-doc-tax-policy-v2-read", "test-index", "test-uuid", "test-mapping-v1"},
				{"b-other-run-12345-0123456789abcdef-read", "test-index", "test-uuid", "test-mapping-v1"},
				{"b-b-run-12345-fedcba9876543210-read", "test-index", "test-uuid", "test-mapping-v1"},
				{"b-b-run-12345-0123456789abcdef-read", "other-index", "test-uuid", "test-mapping-v1"},
				{"b-b-run-12345-0123456789abcdef-read", "test-index", "other-uuid", "test-mapping-v1"},
				{"b-b-run-12345-0123456789abcdef-read", "test-index", "test-uuid", "other-mapping"}
		}) {
			KnowledgeSearchProperties invalid = bProperties("b-b-run-12345-0123456789abcdef-read",
					"test-index", "test-uuid", "test-mapping-v1",
					mismatch[0], mismatch[1], mismatch[2], mismatch[3]);
			assertThatThrownBy(invalid::afterPropertiesSet).isInstanceOf(IllegalStateException.class);
		}
		KnowledgeSearchProfile oneDomainProfile = copyOf(enabledProperties("0".repeat(64))
				.requireProfile("tax.policy", "tax-policy-v1"));
		oneDomainProfile.setReadAlias("b-b-run-12345-0123456789abcdef-read");
		KnowledgeSearchProperties oneDomain = new KnowledgeSearchProperties();
		oneDomain.setEnabled(true);
		oneDomain.setBIsolationFixedTarget("true");
		oneDomain.setBIsolationRunId("b-run-12345");
		oneDomain.setProfiles(Map.of("tax-policy-v1", oneDomainProfile));
		assertThatThrownBy(oneDomain::afterPropertiesSet).isInstanceOf(IllegalStateException.class);
	}

	@Test
	void bIsolationCannotBeEnabledByAProductionLaunch() {
		KnowledgeSearchProperties properties = bProperties("b-b-run-12345-0123456789abcdef-read",
				"test-index", "test-uuid", "test-mapping-v1",
				"b-b-run-12345-0123456789abcdef-read", "test-index", "test-uuid", "test-mapping-v1");
		properties.afterPropertiesSet();
		KnowledgeSearchConfiguration configuration = new KnowledgeSearchConfiguration();
		MockEnvironment production = new MockEnvironment().withProperty("server.address", "0.0.0.0")
				.withProperty("server.port", "9201");
		production.setActiveProfiles("knowledge-live");
		assertThatThrownBy(() -> configuration.knowledgeSearchService(null, new ObjectMapper(),
				properties, production)).isInstanceOf(IllegalStateException.class);

		MockEnvironment isolated = new MockEnvironment().withProperty("server.address", "127.0.0.1")
				.withProperty("server.port", "19201")
				.withProperty("eureka.client.enabled", "false")
				.withProperty("spring.cloud.discovery.enabled", "false")
				.withProperty("spring.cloud.config.enabled", "false");
		isolated.setActiveProfiles("knowledge-live", "knowledge-b-isolation");
		assertThat(configuration.knowledgeSearchService(null, new ObjectMapper(), properties, isolated))
				.isNotNull();
		for (String key : new String[] {"server.address", "server.port", "eureka.client.enabled",
				"spring.cloud.discovery.enabled", "spring.cloud.config.enabled"}) {
			MockEnvironment invalid = new MockEnvironment().withProperty("server.address", "127.0.0.1")
					.withProperty("server.port", "19201")
					.withProperty("eureka.client.enabled", "false")
					.withProperty("spring.cloud.discovery.enabled", "false")
					.withProperty("spring.cloud.config.enabled", "false")
					.withProperty(key, key.equals("server.address") ? "0.0.0.0"
							: key.equals("server.port") ? "9201" : "true");
			invalid.setActiveProfiles("knowledge-b-isolation");
			assertThatThrownBy(() -> configuration.knowledgeSearchService(null, new ObjectMapper(),
					properties, invalid)).isInstanceOf(IllegalStateException.class);
		}
	}

	private static KnowledgeSearchProperties bProperties(String policyAlias, String policyIndex,
			String policyUuid, String policyMapping, String lawAlias, String lawIndex, String lawUuid,
			String lawMapping) {
		KnowledgeSearchProfile source = enabledProperties("0".repeat(64))
				.requireProfile("tax.policy", "tax-policy-v1");
		KnowledgeSearchProfile policy = copyOf(source);
		policy.setReadAlias(policyAlias);
		policy.setExpectedIndexName(policyIndex);
		policy.setExpectedIndexUuid(policyUuid);
		policy.setMappingVersion(policyMapping);
		KnowledgeSearchProfile law = copyOf(source);
		law.setLogicalDomainId("tax.law");
		law.setReadAlias(lawAlias);
		law.setExpectedIndexName(lawIndex);
		law.setExpectedIndexUuid(lawUuid);
		law.setMappingVersion(lawMapping);
		KnowledgeSearchProperties properties = new KnowledgeSearchProperties();
		properties.setEnabled(true);
		properties.setBIsolationFixedTarget("true");
		properties.setBIsolationRunId("b-run-12345");
		properties.setProfiles(Map.of("tax-policy-v1", policy, "tax-law-v1", law));
		return properties;
	}

	private static KnowledgeSearchProfile copyOf(KnowledgeSearchProfile source) {
		KnowledgeSearchProfile copy = new KnowledgeSearchProfile();
		copy.setLogicalDomainId(source.getLogicalDomainId());
		copy.setProfileVersion(source.getProfileVersion());
		copy.setReadPolicyVersion(source.getReadPolicyVersion());
		copy.setReadAlias(source.getReadAlias());
		copy.setExpectedIndexName(source.getExpectedIndexName());
		copy.setExpectedIndexUuid(source.getExpectedIndexUuid());
		copy.setMappingVersion(source.getMappingVersion());
		copy.setIndexSnapshotId(source.getIndexSnapshotId());
		copy.setCategoryField(source.getCategoryField());
		copy.setCategoryValues(source.getCategoryValues());
		copy.setKeywordFields(source.getKeywordFields());
		copy.setVectorField(source.getVectorField());
		copy.setSourceFields(source.getSourceFields());
		copy.setMaxCandidates(source.getMaxCandidates());
		copy.setMaxContentChars(source.getMaxContentChars());
		copy.setDocumentNumberMatching(source.isDocumentNumberMatching());
		return copy;
	}
}
