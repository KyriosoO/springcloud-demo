package com.dylan.agent.adapter.api.document.provider;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import java.util.List;

public record DocumentUntrustedGenerationPayload(
        DocumentPlanOperation operation,
        String answerText,
        String summaryText,
        List<String> summaryBullets,
        List<String> citedIds,
        DocumentProviderFinishReason finishReason) {
    public DocumentUntrustedGenerationPayload {
        if (operation == null || finishReason == null) {
            throw new IllegalArgumentException("generation operation and finishReason are required");
        }
        summaryBullets = List.copyOf(summaryBullets == null ? List.of() : summaryBullets);
        citedIds = List.copyOf(citedIds == null ? List.of() : citedIds);
        if(answerText!=null)DocumentProviderContractValidation.text(answerText,"answerText");
        if(summaryText!=null)DocumentProviderContractValidation.text(summaryText,"summaryText");
        summaryBullets.forEach(value->DocumentProviderContractValidation.text(value,"summary bullet"));
        DocumentProviderContractValidation.uniqueText(citedIds,"citedId");
        if(citedIds.stream().anyMatch(value->!value.matches("C[1-9][0-9]{0,9}")))
            throw new IllegalArgumentException("citedId is not canonical");
        if(operation==DocumentPlanOperation.SEARCH)throw new IllegalArgumentException("SEARCH generation payload is forbidden");
        if(operation==DocumentPlanOperation.ANSWER&&(summaryText!=null||!summaryBullets.isEmpty()))
            throw new IllegalArgumentException("answer payload contains summary fields");
        if(operation==DocumentPlanOperation.SUMMARIZE&&answerText!=null)
            throw new IllegalArgumentException("summary payload contains answer field");
    }
}
