package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.capability.document.provider.security.DocumentProviderOutboundFieldProjector;
import com.dylan.agent.capability.document.provider.security.DocumentProviderOutboundPolicyDecision;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.util.ArrayList;
import java.util.List;

/** 将完整有序 selection 投影为 Provider 可见文本；不重排、不静默丢项。 */
public final class DocumentGenerationEvidenceProjector {
    private final DocumentProviderOutboundFieldProjector fieldProjector;

    public DocumentGenerationEvidenceProjector(DocumentProviderOutboundFieldProjector fieldProjector) {
        this.fieldProjector = java.util.Objects.requireNonNull(fieldProjector, "fieldProjector must not be null");
    }

    public DocumentGenerationEvidenceProjection project(
            List<AclBoundDocumentHit> evidence,
            DocumentEvidencePackingLimit budget,
            DocumentProviderOutboundPolicyDecision decision,
            ExecutionScope scope) {
        List<AclBoundDocumentHit> ordered = List.copyOf(evidence == null ? List.of() : evidence);
        if (ordered.size() > budget.maxEvidenceCount()) {
            throw new IllegalArgumentException("selected evidence exceeds generation item limit");
        }
        List<GenerationEvidencePackageItem> items = new ArrayList<>();
        int evidenceChars = 0;
        int contextChars = 0;
        boolean truncated = false;
        for (AclBoundDocumentHit item : ordered) {
            String rawText = text(item);
            if (rawText == null || rawText.isBlank()) {
                throw new IllegalArgumentException("selected document evidence has no provider text");
            }
            String domain = decision.corpusKey().domain();
            String outboundTitle = fieldProjector.stringValue(decision, scope, domain, "title", item.title());
            String outboundSection = fieldProjector.stringValue(decision, scope, domain, "section", item.section());
            Integer outboundPage = fieldProjector.integerValue(decision, scope, domain, "page", item.page());
            String maskedText = fieldProjector.stringValue(decision, scope, domain, "snippet", rawText);
            int metadataChars = codePoints(outboundTitle) + codePoints(outboundSection)
                    + codePoints(outboundPage == null ? null : outboundPage.toString());
            int allowed = Math.min(
                    budget.maxSnippetChars(),
                    Math.min(
                            budget.maxEvidenceChars() - evidenceChars,
                            budget.maxContextChars() - contextChars - metadataChars));
            if (allowed <= 0) {
                throw new IllegalArgumentException("selected evidence exceeds generation character limit");
            }
            String outboundText = truncateAtSentenceBoundary(maskedText, allowed);
            int outboundChars = codePoints(outboundText);
            if (outboundChars == 0) {
                throw new IllegalArgumentException("selected document evidence cannot be projected safely");
            }
            if (outboundChars < codePoints(maskedText)) truncated = true;
            String citationId = "C" + Math.addExact(items.size(), 1);
            items.add(new GenerationEvidencePackageItem(
                    citationId, item.candidateId(), item.identity(), outboundTitle, outboundSection, outboundPage,
                    outboundText, item.securityBinding()));
            evidenceChars = Math.addExact(evidenceChars, outboundChars);
            contextChars = Math.addExact(contextChars, Math.addExact(metadataChars, outboundChars));
        }
        return new DocumentGenerationEvidenceProjection(
                items, new DocumentEvidenceUsage(items.size(), evidenceChars, contextChars, truncated));
    }

    private static String text(AclBoundDocumentHit evidence) {
        if (evidence.generationText() != null && !evidence.generationText().isBlank()) {
            return evidence.generationText();
        }
        String anchor = evidence.content();
        if (anchor == null || anchor.isBlank()) {
            anchor = evidence.citationText() != null && !evidence.citationText().isBlank()
                    ? evidence.citationText() : evidence.snippet();
        }
        List<String> values = new ArrayList<>(evidence.contextBefore());
        if (anchor != null && !anchor.isBlank()) values.add(anchor);
        values.addAll(evidence.contextAfter());
        return values.stream().filter(value -> value != null && !value.isBlank())
                .collect(java.util.stream.Collectors.joining("\n"));
    }

    private static String truncateAtSentenceBoundary(String value, int codePointLimit) {
        if (codePoints(value) <= codePointLimit) return value;
        int end = value.offsetByCodePoints(0, codePointLimit);
        String clipped = value.substring(0, end);
        int boundary = lastSentenceBoundary(clipped);
        return boundary >= Math.max(1, clipped.length() / 2)
                ? clipped.substring(0, boundary).strip() : clipped.strip();
    }

    private static int lastSentenceBoundary(String value) {
        int boundary = -1;
        for (String marker : List.of("。", "！", "？", ";", "；", "\n")) {
            boundary = Math.max(boundary, value.lastIndexOf(marker));
        }
        return boundary < 0 ? -1 : boundary + 1;
    }

    private static int codePoints(String value) {
        return value == null ? 0 : value.codePointCount(0, value.length());
    }
}
