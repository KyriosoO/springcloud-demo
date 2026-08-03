package com.dylan.esquery.config;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.boot.context.properties.ConfigurationProperties;

import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeAuthorityUnavailableException;

@ConfigurationProperties(prefix = "es.query.knowledge", ignoreUnknownFields = false)
public class KnowledgeSearchProperties implements InitializingBean {
	private static final Set<String> REQUIRED_SOURCE_FIELDS = Set.of(
			"document-id", "chunk-id", "title", "content", "source-url",
			"document-number", "written-date", "material-type", "policy-ref");

	private boolean enabled;
	private Map<String, KnowledgeSearchProfile> profiles = new LinkedHashMap<>();

	public boolean isEnabled() {
		return enabled;
	}

	public void setEnabled(boolean enabled) {
		this.enabled = enabled;
	}

	public Map<String, KnowledgeSearchProfile> getProfiles() {
		return profiles;
	}

	public void setProfiles(Map<String, KnowledgeSearchProfile> profiles) {
		this.profiles = profiles == null ? new LinkedHashMap<>() : new LinkedHashMap<>(profiles);
	}

	@Override
	public void afterPropertiesSet() {
		if (!enabled) {
			return;
		}
		if (profiles.isEmpty()) {
			throw new IllegalStateException("es.query.knowledge.profiles must not be empty when enabled");
		}
		Set<String> domains = new LinkedHashSet<>();
		profiles.forEach((profileId, profile) -> validateProfile(profileId, profile, domains));
		profiles = Collections.unmodifiableMap(new LinkedHashMap<>(profiles));
	}

	public KnowledgeSearchProfile requireProfile(String logicalDomainId, String retrievalProfileId) {
		KnowledgeSearchProfile profile = profiles.get(retrievalProfileId);
		if (profile == null || !profile.getLogicalDomainId().equals(logicalDomainId)) {
			throw new KnowledgeAuthorityUnavailableException();
		}
		return profile;
	}

	private static void validateProfile(String profileId, KnowledgeSearchProfile profile, Set<String> domains) {
		if (profile == null || !physicalToken(profileId) || blank(profile.logicalDomainId)
				|| !supportedDomainProfile(profile.logicalDomainId, profileId)
				|| blank(profile.profileVersion) || blank(profile.readPolicyVersion)
				|| !physicalToken(profile.readAlias) || !physicalToken(profile.expectedIndexName)
				|| !physicalToken(profile.expectedIndexUuid) || blank(profile.mappingVersion)
				|| !lowerHex64(profile.indexSnapshotId) || !fieldName(profile.categoryField)
				|| profile.categoryValues.isEmpty() || profile.keywordFields.isEmpty()
				|| profile.categoryValues.stream().anyMatch(KnowledgeSearchProperties::blank)
				|| new LinkedHashSet<>(profile.categoryValues).size() != profile.categoryValues.size()
				|| profile.keywordFields.stream().anyMatch(field -> !fieldName(field))
				|| new LinkedHashSet<>(profile.keywordFields).size() != profile.keywordFields.size()
				|| !fieldName(profile.vectorField) || !profile.sourceFields.keySet().equals(REQUIRED_SOURCE_FIELDS)
				|| profile.sourceFields.values().stream().anyMatch(KnowledgeSearchProperties::blank)
				|| profile.sourceFields.values().stream().anyMatch(field -> !fieldName(field))
				|| new LinkedHashSet<>(profile.sourceFields.values()).size() != profile.sourceFields.size()
				|| profile.maxCandidates != 20 || profile.maxContentChars != 4096) {
			throw new IllegalStateException("invalid Knowledge search profile: " + profileId);
		}
		if (!domains.add(profile.logicalDomainId)) {
			throw new IllegalStateException("duplicate Knowledge logical domain: " + profile.logicalDomainId);
		}
		profile.freeze();
	}

	private static boolean supportedDomainProfile(String logicalDomainId, String profileId) {
		return "tax.policy".equals(logicalDomainId) && "tax-policy-v1".equals(profileId)
				|| "tax.law".equals(logicalDomainId) && "tax-law-v1".equals(profileId);
	}

	private static boolean blank(String value) {
		return value == null || value.isBlank() || !value.equals(value.trim());
	}

	private static boolean lowerHex64(String value) {
		return value != null && value.matches("[0-9a-f]{64}");
	}

	private static boolean physicalToken(String value) {
		return value != null && value.matches("[A-Za-z0-9._-]+");
	}

	private static boolean fieldName(String value) {
		return value != null && value.matches("[A-Za-z0-9_-]+(?:\\.[A-Za-z0-9_-]+)*");
	}

	public static class KnowledgeSearchProfile {
		private String logicalDomainId;
		private String profileVersion;
		private String readPolicyVersion;
		private String readAlias;
		private String expectedIndexName;
		private String expectedIndexUuid;
		private String mappingVersion;
		private String indexSnapshotId;
		private String categoryField;
		private List<String> categoryValues = new ArrayList<>();
		private List<String> keywordFields = new ArrayList<>();
		private String vectorField;
		private Map<String, String> sourceFields = new LinkedHashMap<>();
		private int maxCandidates = 20;
		private int maxContentChars = 4096;
		private boolean frozen;

		private void freeze() {
			categoryValues = List.copyOf(categoryValues);
			keywordFields = List.copyOf(keywordFields);
			sourceFields = Map.copyOf(sourceFields);
			frozen = true;
		}

		private void ensureMutable() {
			if (frozen) {
				throw new IllegalStateException("Knowledge search profile is frozen");
			}
		}

		public String getLogicalDomainId() { return logicalDomainId; }
		public void setLogicalDomainId(String value) { ensureMutable(); this.logicalDomainId = value; }
		public String getProfileVersion() { return profileVersion; }
		public void setProfileVersion(String value) { ensureMutable(); this.profileVersion = value; }
		public String getReadPolicyVersion() { return readPolicyVersion; }
		public void setReadPolicyVersion(String value) { ensureMutable(); this.readPolicyVersion = value; }
		public String getReadAlias() { return readAlias; }
		public void setReadAlias(String value) { ensureMutable(); this.readAlias = value; }
		public String getExpectedIndexName() { return expectedIndexName; }
		public void setExpectedIndexName(String value) { ensureMutable(); this.expectedIndexName = value; }
		public String getExpectedIndexUuid() { return expectedIndexUuid; }
		public void setExpectedIndexUuid(String value) { ensureMutable(); this.expectedIndexUuid = value; }
		public String getMappingVersion() { return mappingVersion; }
		public void setMappingVersion(String value) { ensureMutable(); this.mappingVersion = value; }
		public String getIndexSnapshotId() { return indexSnapshotId; }
		public void setIndexSnapshotId(String value) { ensureMutable(); this.indexSnapshotId = value; }
		public String getCategoryField() { return categoryField; }
		public void setCategoryField(String value) { ensureMutable(); this.categoryField = value; }
		public List<String> getCategoryValues() { return categoryValues; }
		public void setCategoryValues(List<String> value) { ensureMutable(); this.categoryValues = value == null ? new ArrayList<>() : new ArrayList<>(value); }
		public List<String> getKeywordFields() { return keywordFields; }
		public void setKeywordFields(List<String> value) { ensureMutable(); this.keywordFields = value == null ? new ArrayList<>() : new ArrayList<>(value); }
		public String getVectorField() { return vectorField; }
		public void setVectorField(String value) { ensureMutable(); this.vectorField = value; }
		public Map<String, String> getSourceFields() { return sourceFields; }
		public void setSourceFields(Map<String, String> value) { ensureMutable(); this.sourceFields = value == null ? new LinkedHashMap<>() : new LinkedHashMap<>(value); }
		public int getMaxCandidates() { return maxCandidates; }
		public void setMaxCandidates(int value) { ensureMutable(); this.maxCandidates = value; }
		public int getMaxContentChars() { return maxContentChars; }
		public void setMaxContentChars(int value) { ensureMutable(); this.maxContentChars = value; }
	}
}
