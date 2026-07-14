package com.dylan.agent.capability.document.governance.emergency;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;

@JsonTypeInfo(use = JsonTypeInfo.Id.NAME, property = "targetType")
@JsonSubTypes({
        @JsonSubTypes.Type(value = DocumentEmergencyTargetRef.CapabilityTarget.class, name = "CAPABILITY"),
        @JsonSubTypes.Type(value = DocumentEmergencyTargetRef.CorpusTarget.class, name = "CORPUS"),
        @JsonSubTypes.Type(value = DocumentEmergencyTargetRef.ProfileTarget.class, name = "PROFILE"),
        @JsonSubTypes.Type(value = DocumentEmergencyTargetRef.IndexTarget.class, name = "INDEX_TARGET"),
        @JsonSubTypes.Type(value = DocumentEmergencyTargetRef.ProviderOperationTarget.class, name = "PROVIDER_OPERATION"),
        @JsonSubTypes.Type(value = DocumentEmergencyTargetRef.ProviderBindingTarget.class, name = "PROVIDER_BINDING")
})
public sealed interface DocumentEmergencyTargetRef permits DocumentEmergencyTargetRef.CapabilityTarget,DocumentEmergencyTargetRef.CorpusTarget,DocumentEmergencyTargetRef.ProfileTarget,DocumentEmergencyTargetRef.IndexTarget,DocumentEmergencyTargetRef.ProviderOperationTarget,DocumentEmergencyTargetRef.ProviderBindingTarget {
    @JsonIgnore String type();
    @JsonIgnore String key();
    record CapabilityTarget(String key) implements DocumentEmergencyTargetRef {
        public CapabilityTarget { if(!java.util.Set.of("document.search","document.answer","document.summarize").contains(key))throw new IllegalArgumentException("unknown document capability target"); }
        public String type(){return "CAPABILITY";}
    }
    record CorpusTarget(DocumentCorpusKey corpusKey) implements DocumentEmergencyTargetRef {
        public CorpusTarget { java.util.Objects.requireNonNull(corpusKey,"corpusKey must not be null"); }
        public String type(){return "CORPUS";} public String key(){return corpusKey.domain()+"\u001f"+corpusKey.materialType();}
    }
    record ProfileTarget(String key) implements DocumentEmergencyTargetRef {
        public ProfileTarget { safeText(key,"profile target"); }
        public String type(){return "PROFILE";}
    }
    record IndexTarget(String key) implements DocumentEmergencyTargetRef {
        public IndexTarget { digest(key,"index target"); }
        public String type(){return "INDEX_TARGET";}
    }
    record ProviderOperationTarget(CapabilityOperationType operationType) implements DocumentEmergencyTargetRef {
        public ProviderOperationTarget { java.util.Objects.requireNonNull(operationType,"operationType must not be null"); }
        public String type(){return "PROVIDER_OPERATION";} public String key(){return operationType.value();}
    }
    record ProviderBindingTarget(String key) implements DocumentEmergencyTargetRef {
        public ProviderBindingTarget { digest(key,"provider binding target"); }
        public String type(){return "PROVIDER_BINDING";}
    }
    private static void safeText(String value,String name){if(value==null||value.isBlank()||value.contains("*")||value.codePoints().anyMatch(Character::isISOControl))throw new IllegalArgumentException(name+" invalid");}
    private static void digest(String value,String name){if(value==null||!value.matches("[0-9a-f]{64}"))throw new IllegalArgumentException(name+" must be SHA-256 hex");}
}
