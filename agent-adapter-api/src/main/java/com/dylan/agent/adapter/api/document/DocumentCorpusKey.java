package com.dylan.agent.adapter.api.document;

import java.nio.charset.StandardCharsets;
import java.util.Objects;
import java.util.regex.Pattern;

/** 文档语料逻辑主键；canonical contract 为 DCK-1。 */
public record DocumentCorpusKey(String domain, String materialType) {
    private static final Pattern IDENTIFIER = Pattern.compile("[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*");

    public DocumentCorpusKey {
        domain = requireIdentifier(domain, "domain");
        materialType = requireIdentifier(materialType, "materialType");
    }

    public byte[] canonicalBytes() {
        return (domain + '\u001f' + materialType).getBytes(StandardCharsets.UTF_8);
    }

    private static String requireIdentifier(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        if (!IDENTIFIER.matcher(value).matches()) {
            throw new IllegalArgumentException(name + " must be a canonical identifier");
        }
        return value;
    }
}
