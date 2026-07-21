package com.dylan.agent.capability.document.generation;

import java.util.List;

/** Provider 文本通过本地结构校验后的不可变内容。 */
public record DocumentGeneratedContent(
        String answerText,
        String summaryText,
        List<String> summaryBullets) {
    public DocumentGeneratedContent {
        summaryBullets = List.copyOf(summaryBullets == null ? List.of() : summaryBullets);
    }
}
