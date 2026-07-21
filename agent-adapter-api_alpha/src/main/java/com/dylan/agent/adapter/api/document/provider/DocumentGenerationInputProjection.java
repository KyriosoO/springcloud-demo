package com.dylan.agent.adapter.api.document.provider;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import java.util.List;

public record DocumentGenerationInputProjection(
        String packageId,
        String packageDigest,
        DocumentPlanOperation operation,
        DocumentGenerationInstructionCode instructionCode,
        List<DocumentGenerationEvidenceItem> evidence,
        DocumentGenerationOutputShape outputShape) {
    public DocumentGenerationInputProjection {
        DocumentProviderContractValidation.text(packageId,"packageId");
        DocumentProviderContractValidation.digest(packageDigest,"packageDigest");
        if (operation == null || instructionCode == null || outputShape == null) {
            throw new IllegalArgumentException("invalid generation input");
        }
        evidence = DocumentProviderContractValidation.list(evidence,"evidence",false);
        DocumentProviderContractValidation.uniqueText(
                evidence.stream().map(DocumentGenerationEvidenceItem::citationId).toList(),"citationId");
        boolean answer = operation == DocumentPlanOperation.ANSWER
                && instructionCode == DocumentGenerationInstructionCode.ANSWER_WITH_CITATIONS
                && outputShape == DocumentGenerationOutputShape.ANSWER;
        boolean summary = operation == DocumentPlanOperation.SUMMARIZE
                && instructionCode == DocumentGenerationInstructionCode.SUMMARIZE_WITH_CITATIONS
                && outputShape == DocumentGenerationOutputShape.SUMMARY;
        if(!answer&&!summary)throw new IllegalArgumentException("generation operation union mismatch");
    }
}
