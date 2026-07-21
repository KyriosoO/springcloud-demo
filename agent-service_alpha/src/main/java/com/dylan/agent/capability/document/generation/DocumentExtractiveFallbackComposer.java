package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.api.plan.DocumentPlanOperation;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** 只按selected evidence顺序拼完整citation-bound单位的确定性fallback。 */
public final class DocumentExtractiveFallbackComposer {
    public FallbackDraft compose(DocumentPlanOperation operation, List<AclBoundDocumentHit> evidence,
                                 int maxGeneratedChars, int maxSummaryChars, int maxSummaryBullets) {
        if (operation == DocumentPlanOperation.ANSWER) {
            List<String> paragraphs = new ArrayList<>();
            for (int index = 0; index < evidence.size(); index++) {
                String unit = unit(evidence.get(index), index);
                String candidate = String.join("\n\n", append(paragraphs, unit));
                if (codePoints(candidate) > maxGeneratedChars) break;
                paragraphs.add(unit);
            }
            return paragraphs.isEmpty() ? FallbackDraft.refusal()
                    : new FallbackDraft(String.join("\n\n", paragraphs), null, List.of(), citationIdsFromUnits(paragraphs), false);
        }
        if (operation == DocumentPlanOperation.SUMMARIZE) {
            List<String> bullets = new ArrayList<>();
            for (int index = 0; index < evidence.size() && bullets.size() < maxSummaryBullets; index++) {
                AclBoundDocumentHit hit = evidence.get(index);
                String unit = unit(hit, index);
                if (unit.isBlank()) continue;
                int total = bullets.stream().mapToInt(DocumentExtractiveFallbackComposer::codePoints).sum() + codePoints(unit);
                if (total > maxSummaryChars) break;
                bullets.add(unit);
            }
            return bullets.isEmpty() ? FallbackDraft.refusal()
                    : new FallbackDraft(null, null, List.copyOf(bullets), citationIdsFromUnits(bullets), false);
        }
        return FallbackDraft.refusal();
    }

    private static String unit(AclBoundDocumentHit hit, int index) {
        String text = hit.citationText();
        if (text == null || text.isBlank()) text = hit.snippet();
        if (text == null || text.isBlank()) return "";
        return text.strip() + " [C" + (index + 1) + "]";
    }
    private static List<String> append(List<String> values, String value) { List<String> result = new ArrayList<>(values); if (!value.isBlank()) result.add(value); return result; }
    private static int codePoints(String value) { return value.codePointCount(0, value.length()); }
    private static List<String> citationIdsFromUnits(List<String> units) {
        List<String> ids = new ArrayList<>(); PatternHolder.PATTERN.matcher(String.join("\n", units)).results().forEach(match -> ids.add(match.group(1))); return List.copyOf(new java.util.LinkedHashSet<>(ids));
    }
    private static final class PatternHolder { private static final java.util.regex.Pattern PATTERN = java.util.regex.Pattern.compile("\\[(C[1-9][0-9]*)]"); }
    public record FallbackDraft(String answerText, String summaryText, List<String> summaryBullets,
                                List<String> citedIds, boolean refused) {
        public FallbackDraft { summaryBullets = List.copyOf(summaryBullets); citedIds = List.copyOf(citedIds); }
        static FallbackDraft refusal() { return new FallbackDraft(null, null, List.of(), List.of(), true); }
    }
}
