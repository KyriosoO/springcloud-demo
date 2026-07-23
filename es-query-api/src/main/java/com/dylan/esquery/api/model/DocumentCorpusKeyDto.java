package com.dylan.esquery.api.model;

import java.nio.charset.StandardCharsets;
import java.util.regex.Pattern;

/** ES wire 侧 DCK-1 文档语料主键。 */
public record DocumentCorpusKeyDto(String domain, String materialType) {
    private static final Pattern IDENTIFIER = Pattern.compile("[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*");
    public DocumentCorpusKeyDto {
        if (domain == null || !IDENTIFIER.matcher(domain).matches()) throw new IllegalArgumentException("domain must be canonical");
        if (materialType == null || !IDENTIFIER.matcher(materialType).matches()) throw new IllegalArgumentException("materialType must be canonical");
    }
    public byte[] canonicalBytes() { return (domain + '\u001f' + materialType).getBytes(StandardCharsets.UTF_8); }
}
