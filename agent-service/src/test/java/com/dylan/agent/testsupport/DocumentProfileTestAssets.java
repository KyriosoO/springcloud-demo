package com.dylan.agent.testsupport;

import com.dylan.agent.capability.document.profile.DocumentFeaturePolicy;
import com.dylan.agent.capability.document.profile.DocumentProfileAssets;
import com.dylan.agent.capability.document.profile.DocumentProfileProperties;

import java.util.List;
import java.util.Map;

/** 非 Document 专题测试构造 metadata bootstrap 所需 exact child asset。 */
public final class DocumentProfileTestAssets {
    private DocumentProfileTestAssets() {}

    public static DocumentProfileAssets.BuiltAssets assets() {
        DocumentProfileProperties properties = new DocumentProfileProperties();
        properties.setOwnerAgentId("agent-default");
        properties.setOwnerProfileVersion("profile-v1");
        properties.setPolicyVersion("policy-v1");
        DocumentProfileProperties.Entry entry = new DocumentProfileProperties.Entry();
        entry.setProfileName("employee-document-v1");
        entry.setDomain("employee");
        entry.setDefaultProfile(true);
        entry.setAllowedMaterialTypes(List.of("employee"));
        entry.setAllowedOperations(List.of("SEARCH", "ANSWER", "SUMMARIZE"));
        entry.setAllowedChannels(List.of("BM25"));
        entry.setRequiredChannels(List.of("BM25"));
        entry.setGenerationPolicy(Map.of(
                "SEARCH", DocumentFeaturePolicy.DISABLED,
                "ANSWER", DocumentFeaturePolicy.OPTIONAL,
                "SUMMARIZE", DocumentFeaturePolicy.OPTIONAL));
        properties.setDefinitions(List.of(entry));
        DocumentProfileProperties.PolicyEntry policy = new DocumentProfileProperties.PolicyEntry();
        policy.setDomain("employee");
        policy.setAllowedProfileNames(List.of("employee-document-v1"));
        policy.setAllowedChannels(List.of("BM25"));
        policy.setAllowedOperations(List.of("SEARCH", "ANSWER", "SUMMARIZE"));
        properties.setPolicy(List.of(policy));
        return DocumentProfileAssets.build(properties);
    }
}
