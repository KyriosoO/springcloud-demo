package com.dylan.esquery;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.dylan.esquery.config.KnowledgeSearchProperties;
import com.dylan.esquery.config.KnowledgeSearchProperties.KnowledgeSearchProfile;

public final class KnowledgeTestProfiles {
	private KnowledgeTestProfiles() {
	}

	public static KnowledgeSearchProperties enabledProperties(String snapshot) {
		return enabledProperties(snapshot, defaultSourceFields());
	}

	public static KnowledgeSearchProperties enabledProperties(String snapshot,
			Map<String, String> sourceFields) {
		KnowledgeSearchProfile profile = new KnowledgeSearchProfile();
		profile.setLogicalDomainId("tax.policy");
		profile.setProfileVersion("tax-knowledge-search-v1");
		profile.setReadPolicyVersion("tax-public-authenticated-v1");
		profile.setReadAlias("agent-doc-tax-policy-v2-read");
		profile.setExpectedIndexName("agent-doc-tax-policy-v2-000001");
		profile.setExpectedIndexUuid("index-uuid-1");
		profile.setMappingVersion("mapping-v1");
		profile.setIndexSnapshotId(snapshot);
		profile.setCategoryField("category");
		profile.setCategoryValues(List.of("policy"));
		profile.setKeywordFields(List.of("title", "content"));
		profile.setVectorField("embedding");
		profile.setSourceFields(sourceFields);

		KnowledgeSearchProperties properties = new KnowledgeSearchProperties();
		properties.setEnabled(true);
		properties.setProfiles(Map.of("tax-policy-v1", profile));
		properties.afterPropertiesSet();
		return properties;
	}

	public static Map<String, String> defaultSourceFields() {
		Map<String, String> sourceFields = new LinkedHashMap<>();
		sourceFields.put("document-id", "document_id");
		sourceFields.put("chunk-id", "chunk_id");
		sourceFields.put("title", "title");
		sourceFields.put("content", "content");
		sourceFields.put("source-url", "source_url");
		sourceFields.put("document-number", "document_number");
		sourceFields.put("written-date", "written_date");
		sourceFields.put("material-type", "material_type");
		sourceFields.put("policy-ref", "policy_ref");
		return sourceFields;
	}
}
