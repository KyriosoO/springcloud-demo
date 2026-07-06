package com.dylan.agent.metadata.result;

import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.response.AgentDocumentCitation;
import com.dylan.agent.api.response.AgentDocumentResult;

import java.util.List;
import java.util.stream.Collectors;

/** 基于已过滤引用片段生成抽取式安全文本，避免输出未授权证据外内容。 */
final class DocumentSafeTextComposer {

    private DocumentSafeTextComposer() {
    }

    static void compose(DocumentPlanOperation operation, AgentDocumentResult result, int maxSummaryChars) {
        List<AgentDocumentCitation> citations = result.getCitations() == null ? List.of() : result.getCitations();
        if (citations.isEmpty()) {
            result.setAnswerText(operation == DocumentPlanOperation.SEARCH ? null : "未找到可引用证据。");
            result.setSummaryText(operation == DocumentPlanOperation.SUMMARIZE ? "未找到可引用证据。" : null);
            result.setSummaryBullets(List.of());
            return;
        }
        if (operation == DocumentPlanOperation.ANSWER) {
            result.setAnswerText(citations.stream()
                    .map(DocumentSafeTextComposer::line)
                    .collect(Collectors.joining("\n")));
        }
        if (operation == DocumentPlanOperation.SUMMARIZE) {
            List<String> bullets = citations.stream()
                    .map(DocumentSafeTextComposer::line)
                    .limit(8)
                    .toList();
            String summary = truncate(String.join("\n", bullets), maxSummaryChars);
            result.setSummaryText(summary);
            result.setSummaryBullets(bullets);
        }
    }

    private static String line(AgentDocumentCitation citation) {
        String prefix = citation.getCitationId() == null ? "" : "[" + citation.getCitationId() + "] ";
        return prefix + truncate(citation.getSnippet(), 500);
    }

    private static String truncate(String value, int maxChars) {
        if (value == null) {
            return "";
        }
        int limit = maxChars <= 0 ? 500 : maxChars;
        return value.length() <= limit ? value : value.substring(0, limit);
    }
}
