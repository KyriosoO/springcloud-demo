package com.dylan.agent.capability.document.generation;

import java.util.List;

/** 生成句子或摘要 bullet 到 citation 的绑定。 */
public record CitationBinding(
        String text,
        List<String> citationIds) {
}
