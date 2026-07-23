package com.dylan.esquery.service;

import com.dylan.esquery.document.DocumentCorpusDefinition;
import org.springframework.stereotype.Component;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Schema v3 technical mapping gate；不按index名称猜版本。 */
@Component
public final class DocumentIndexDefinitionValidator {
    private static final Set<String> KEYWORDS = Set.of("tenantId", "documentId", "documentVersion", "chunkId",
            "aclRef", "aclVersion", "visibility", "status", "userIds", "departmentIds", "roleIds", "attributeKeys",
            "chunkContentHash", "safeSourceUri");
    private static final Set<String> INTEGERS = Set.of("chunkIndex", "charStart", "charEnd", "page");
    private static final Set<String> TEXT = Set.of("content", "title", "section");
    private static final Set<String> OPTIONAL = Set.of("title", "section", "page", "safeSourceUri", "sourceUpdatedAt", "embedding");
    private static final Set<String> REQUIRED = Set.of("tenantId", "documentId", "documentVersion", "chunkId", "chunkIndex",
            "charStart", "charEnd", "content", "chunkContentHash", "status", "aclRef", "aclVersion", "visibility",
            "userIds", "departmentIds", "roleIds", "attributeKeys");
    private static final Set<String> PROHIBITED = Set.of("retrievalProfile", "schemaVersion", "indexVersion", "embeddingModel",
            "embeddingDimension", "snippet", "contextBefore", "contextAfter", "aclExpression", "token");

    public void validate(String ignoredIndex, Map<String, Object> definition) {
        validate(definition, Set.of(), Set.of("standard", "policy_text_analyzer", "policy_phrase_analyzer"), null);
    }

    public void validate(DocumentCorpusDefinition corpus, Map<String, Object> definition, Integer vectorDimension) {
        if (corpus == null) throw new IllegalArgumentException("document corpus definition required");
        Set<String> analyzers = new HashSet<>();
        analyzers.add("standard");
        analyzers.add(corpus.analyzerRef());
        validate(definition, corpus.indexedBusinessFields(), Set.copyOf(analyzers), vectorDimension);
    }

    private void validate(Map<String,Object> definition,Set<String> businessFields,Set<String> analyzers,Integer vectorDimension){
        if(definition==null||definition.isEmpty())throw new IllegalArgumentException("document indexDefinition must not be empty");
        Map<?,?> mappings=map(definition.get("mappings"),"mappings");
        if(!"strict".equals(mappings.get("dynamic")))throw new IllegalArgumentException("document mapping dynamic must be strict");
        Map<?,?> properties=map(mappings.get("properties"),"mappings.properties");
        Set<String> allowed=new HashSet<>(REQUIRED);allowed.addAll(OPTIONAL);allowed.addAll(businessFields);
        for(Object raw:properties.keySet()){String field=String.valueOf(raw);if(PROHIBITED.contains(field))throw new IllegalArgumentException("document mapping contains prohibited field: "+field);if(!allowed.contains(field))throw new IllegalArgumentException("document mapping contains unknown field: "+field);}
        REQUIRED.forEach(field->{if(!properties.containsKey(field))throw new IllegalArgumentException("document mapping missing required field: "+field);});
        for(String field:KEYWORDS){if(properties.containsKey(field))requireType(properties,field,"keyword");}
        for(String field:INTEGERS){if(properties.containsKey(field))requireType(properties,field,"integer");}
        for(String field:TEXT){if(properties.containsKey(field)){Map<?,?> mapping=requireType(properties,field,"text");Object analyzer=mapping.get("analyzer");if(analyzer!=null&&!analyzers.contains(String.valueOf(analyzer)))throw new IllegalArgumentException("document mapping analyzer not registered: "+field);}}
        if(properties.containsKey("sourceUpdatedAt"))requireType(properties,"sourceUpdatedAt","date");
        if(properties.containsKey("safeSourceUri")){Map<?,?> uri=requireType(properties,"safeSourceUri","keyword");if(!Boolean.FALSE.equals(uri.get("index")))throw new IllegalArgumentException("safeSourceUri must be index:false");}
        if(vectorDimension==null&&properties.containsKey("embedding"))throw new IllegalArgumentException("document embedding mapping not enabled");
        if(vectorDimension!=null){Map<?,?> vector=requireType(properties,"embedding","dense_vector");if(!(vector.get("dims") instanceof Number n)||n.intValue()!=vectorDimension)throw new IllegalArgumentException("document embedding dims mismatch");Map<?,?> source=map(mappings.get("_source"),"mappings._source");Object excludes=source.get("excludes");if(!(excludes instanceof List<?> list)||!list.contains("embedding"))throw new IllegalArgumentException("document embedding must be excluded from _source");}
        for(String business:businessFields){if(!properties.containsKey(business))throw new IllegalArgumentException("document business mapping missing: "+business);Map<?,?> mapping=map(properties.get(business),business);if(!Set.of("keyword","text","date","integer","boolean").contains(mapping.get("type")))throw new IllegalArgumentException("document business mapping type invalid: "+business);}
    }
    private static Map<?,?> requireType(Map<?,?> properties,String field,String type){Map<?,?> mapping=map(properties.get(field),field);if(!type.equals(mapping.get("type")))throw new IllegalArgumentException("document mapping field type invalid: "+field);return mapping;}
    private static Map<?,?> map(Object value,String name){if(!(value instanceof Map<?,?> map))throw new IllegalArgumentException("document mapping object required: "+name);return map;}
}
