package com.dylan.agent.capability.document.profile;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** exact AgentProfile/Policy 文档子资产的配置输入；启动时一次 canonicalize 后不再读取。 */
@ConfigurationProperties(prefix = "agent.document-profiles")
public class DocumentProfileProperties {
    private String ownerAgentId;
    private String ownerProfileVersion;
    private String policyVersion;
    private List<Entry> definitions = new ArrayList<>();
    private List<PolicyEntry> policy = new ArrayList<>();

    public String getOwnerAgentId() { return ownerAgentId; }
    public void setOwnerAgentId(String value) { ownerAgentId = value; }
    public String getOwnerProfileVersion() { return ownerProfileVersion; }
    public void setOwnerProfileVersion(String value) { ownerProfileVersion = value; }
    public String getPolicyVersion() { return policyVersion; }
    public void setPolicyVersion(String value) { policyVersion = value; }
    public List<Entry> getDefinitions() { return definitions; }
    public void setDefinitions(List<Entry> value) { definitions = value == null ? new ArrayList<>() : new ArrayList<>(value); }
    public List<PolicyEntry> getPolicy() { return policy; }
    public void setPolicy(List<PolicyEntry> value) { policy = value == null ? new ArrayList<>() : new ArrayList<>(value); }

    public static class Entry {
        private String profileName;
        private String domain;
        private boolean defaultProfile;
        private List<String> allowedMaterialTypes = new ArrayList<>();
        private List<String> allowedOperations = new ArrayList<>();
        private List<String> allowedChannels = new ArrayList<>();
        private List<String> requiredChannels = new ArrayList<>();
        private Map<String, Integer> channelWeights = new LinkedHashMap<>();
        private int keywordK = 20;
        private int vectorK = 20;
        private int rrfK = 60;
        private int numCandidates = 100;
        private int rerankTopN = 20;
        private int maxChunksPerDocument = 1;
        private int contextBeforeChunks = 0;
        private int contextAfterChunks = 0;
        private DocumentFeaturePolicy rewritePolicy = DocumentFeaturePolicy.DISABLED;
        private DocumentFeaturePolicy embeddingPolicy = DocumentFeaturePolicy.DISABLED;
        private DocumentFeaturePolicy rerankPolicy = DocumentFeaturePolicy.DISABLED;
        private Map<String, DocumentFeaturePolicy> generationPolicy = new LinkedHashMap<>();
        private List<String> searchableFields = new ArrayList<>();
        private List<String> returnableFields = new ArrayList<>();

        public String getProfileName() { return profileName; }
        public void setProfileName(String value) { profileName = value; }
        public String getDomain() { return domain; }
        public void setDomain(String value) { domain = value; }
        public boolean isDefaultProfile() { return defaultProfile; }
        public void setDefaultProfile(boolean value) { defaultProfile = value; }
        public List<String> getAllowedMaterialTypes() { return allowedMaterialTypes; }
        public void setAllowedMaterialTypes(List<String> value) { allowedMaterialTypes = list(value); }
        public List<String> getAllowedOperations() { return allowedOperations; }
        public void setAllowedOperations(List<String> value) { allowedOperations = list(value); }
        public List<String> getAllowedChannels() { return allowedChannels; }
        public void setAllowedChannels(List<String> value) { allowedChannels = list(value); }
        public List<String> getRequiredChannels() { return requiredChannels; }
        public void setRequiredChannels(List<String> value) { requiredChannels = list(value); }
        public Map<String, Integer> getChannelWeights() { return channelWeights; }
        public void setChannelWeights(Map<String, Integer> value) { channelWeights = value == null ? new LinkedHashMap<>() : new LinkedHashMap<>(value); }
        public int getKeywordK() { return keywordK; }
        public void setKeywordK(int value) { keywordK = value; }
        public int getVectorK() { return vectorK; }
        public void setVectorK(int value) { vectorK = value; }
        public int getRrfK() { return rrfK; }
        public void setRrfK(int value) { rrfK = value; }
        public int getNumCandidates() { return numCandidates; }
        public void setNumCandidates(int value) { numCandidates = value; }
        public int getRerankTopN() { return rerankTopN; }
        public void setRerankTopN(int value) { rerankTopN = value; }
        public int getMaxChunksPerDocument() { return maxChunksPerDocument; }
        public void setMaxChunksPerDocument(int value) { maxChunksPerDocument = value; }
        public int getContextBeforeChunks() { return contextBeforeChunks; }
        public void setContextBeforeChunks(int value) { contextBeforeChunks = value; }
        public int getContextAfterChunks() { return contextAfterChunks; }
        public void setContextAfterChunks(int value) { contextAfterChunks = value; }
        public DocumentFeaturePolicy getRewritePolicy() { return rewritePolicy; }
        public void setRewritePolicy(DocumentFeaturePolicy value) { rewritePolicy = value; }
        public DocumentFeaturePolicy getEmbeddingPolicy() { return embeddingPolicy; }
        public void setEmbeddingPolicy(DocumentFeaturePolicy value) { embeddingPolicy = value; }
        public DocumentFeaturePolicy getRerankPolicy() { return rerankPolicy; }
        public void setRerankPolicy(DocumentFeaturePolicy value) { rerankPolicy = value; }
        public Map<String, DocumentFeaturePolicy> getGenerationPolicy() { return generationPolicy; }
        public void setGenerationPolicy(Map<String, DocumentFeaturePolicy> value) { generationPolicy = value == null ? new LinkedHashMap<>() : new LinkedHashMap<>(value); }
        public List<String> getSearchableFields() { return searchableFields; }
        public void setSearchableFields(List<String> value) { searchableFields = list(value); }
        public List<String> getReturnableFields() { return returnableFields; }
        public void setReturnableFields(List<String> value) { returnableFields = list(value); }

        private static List<String> list(List<String> value) { return value == null ? new ArrayList<>() : new ArrayList<>(value); }
    }

    public static class PolicyEntry {
        private String domain;
        private List<String> allowedProfileNames = new ArrayList<>();
        private List<String> allowedChannels = new ArrayList<>();
        private List<String> allowedOperations = new ArrayList<>();
        public String getDomain() { return domain; }
        public void setDomain(String value) { domain = value; }
        public List<String> getAllowedProfileNames() { return allowedProfileNames; }
        public void setAllowedProfileNames(List<String> value) { allowedProfileNames = value == null ? new ArrayList<>() : new ArrayList<>(value); }
        public List<String> getAllowedChannels() { return allowedChannels; }
        public void setAllowedChannels(List<String> value) { allowedChannels = value == null ? new ArrayList<>() : new ArrayList<>(value); }
        public List<String> getAllowedOperations() { return allowedOperations; }
        public void setAllowedOperations(List<String> value) { allowedOperations = value == null ? new ArrayList<>() : new ArrayList<>(value); }
    }
}
