package com.dylan.esquery.document.governance.emergency;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;

import java.util.List;

public final class DocumentEmergencyGateExpectedBindings {
    private DocumentEmergencyGateExpectedBindings() {}

    public static List<DocumentEmergencyGateTargetBinding> forIndex(
            DocumentCorpusKeyDto corpusKey,String targetBindingDigest){
        return java.util.stream.Stream.of(
                DocumentEmergencyGateCanonicalizer.targetBinding(DocumentEmergencyTargetType.CORPUS,
                        corpusKey.domain()+"\u001f"+corpusKey.materialType()),
                DocumentEmergencyGateCanonicalizer.targetBinding(DocumentEmergencyTargetType.INDEX_TARGET,
                        targetBindingDigest))
                .sorted().toList();
    }
}
