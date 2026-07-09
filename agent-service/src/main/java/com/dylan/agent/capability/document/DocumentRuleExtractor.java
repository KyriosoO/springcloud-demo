package com.dylan.agent.capability.document;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.regex.Pattern;

/** 从原始问题中抽取 Java 侧可信的文档规则关键词。 */
public final class DocumentRuleExtractor {

    private static final Pattern DOCUMENT_NUMBER = Pattern.compile(
            "[\\p{IsHan}A-Za-z]{1,12}[〔\\[]\\d{4}[〕\\]]\\d{1,8}号?");
    private static final Pattern DATE = Pattern.compile(
            "\\d{4}年\\d{1,2}月\\d{1,2}日|\\d{4}-\\d{1,2}-\\d{1,2}");
    private static final List<String> TAX_TYPES = List.of(
            "增值税",
            "企业所得税",
            "个人所得税",
            "印花税",
            "消费税",
            "房产税",
            "土地增值税");
    private static final List<String> ISSUERS = List.of(
            "国家税务总局",
            "财政部",
            "国务院",
            "税务局",
            "人力资源和社会保障部");

    public List<String> extract(String queryText, String domain, String materialType) {
        if (queryText == null || queryText.isBlank()) {
            return List.of();
        }
        LinkedHashSet<String> values = new LinkedHashSet<>();
        collectPattern(values, DOCUMENT_NUMBER, queryText);
        collectPattern(values, DATE, queryText);
        collectContains(values, queryText, TAX_TYPES);
        collectContains(values, queryText, ISSUERS);
        return List.copyOf(values);
    }

    private static void collectPattern(LinkedHashSet<String> values, Pattern pattern, String queryText) {
        var matcher = pattern.matcher(queryText);
        while (matcher.find()) {
            add(values, matcher.group());
        }
    }

    private static void collectContains(LinkedHashSet<String> values, String queryText, List<String> candidates) {
        candidates.stream()
                .filter(Objects::nonNull)
                .filter(queryText::contains)
                .forEach(value -> add(values, value));
    }

    private static void add(LinkedHashSet<String> values, String value) {
        if (value == null) {
            return;
        }
        String normalized = value.trim();
        if (!normalized.isBlank()) {
            values.add(normalized);
        }
    }
}
