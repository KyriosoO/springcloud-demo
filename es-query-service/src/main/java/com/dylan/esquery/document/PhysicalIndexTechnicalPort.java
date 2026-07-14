package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;

import java.util.List;

public interface PhysicalIndexTechnicalPort {
    List<String> listPhysicalIndexCandidates(DocumentCorpusKeyDto corpusKey);
    PhysicalIndexReferenceInspection inspectReferences(String physicalIndex);
    void deletePhysicalIndex(AuthorizedIndexDeletionCommand command);
}
