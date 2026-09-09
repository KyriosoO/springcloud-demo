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

import com.dylan.esquery.config.KnowledgeSearchProperties.KnowledgeSearchProfile;

class KnowledgeSearchPropertiesTest {

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
