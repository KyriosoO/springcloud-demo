package com.dylan.esquery.document;

import java.util.ArrayList;
import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "document-corpus")
public class DocumentCorpusCatalogProperties {
    private List<Entry> definitions = new ArrayList<>();
    public List<Entry> getDefinitions() { return definitions; }
    public void setDefinitions(List<Entry> definitions) { this.definitions = definitions == null ? new ArrayList<>() : new ArrayList<>(definitions); }
    public static class Entry {
        private String domain; private String materialType; private String readAlias; private String schemaName;
        private String schemaVersion; private String schemaDigest; private String analyzerRef; private String vectorPolicyRef;
        private String chunkStrategyRef; private String sourceConnectorId; private List<String> indexedBusinessFields = new ArrayList<>();
        public String getDomain() { return domain; } public void setDomain(String value) { domain = value; }
        public String getMaterialType() { return materialType; } public void setMaterialType(String value) { materialType = value; }
        public String getReadAlias() { return readAlias; } public void setReadAlias(String value) { readAlias = value; }
        public String getSchemaName() { return schemaName; } public void setSchemaName(String value) { schemaName = value; }
        public String getSchemaVersion() { return schemaVersion; } public void setSchemaVersion(String value) { schemaVersion = value; }
        public String getSchemaDigest() { return schemaDigest; } public void setSchemaDigest(String value) { schemaDigest = value; }
        public String getAnalyzerRef() { return analyzerRef; } public void setAnalyzerRef(String value) { analyzerRef = value; }
        public String getVectorPolicyRef() { return vectorPolicyRef; } public void setVectorPolicyRef(String value) { vectorPolicyRef = value; }
        public String getChunkStrategyRef() { return chunkStrategyRef; } public void setChunkStrategyRef(String value) { chunkStrategyRef = value; }
        public String getSourceConnectorId() { return sourceConnectorId; } public void setSourceConnectorId(String value) { sourceConnectorId = value; }
        public List<String> getIndexedBusinessFields() { return indexedBusinessFields; } public void setIndexedBusinessFields(List<String> value) { indexedBusinessFields = value == null ? new ArrayList<>() : new ArrayList<>(value); }
    }
}
