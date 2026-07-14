package com.dylan.agent.capability.document.security;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;

/** Document public/internal sidecar共用的source URI收紧器。 */
public final class DocumentSafeSourceUri {
    private DocumentSafeSourceUri() {}

    public static String sanitize(String value) {
        if (value == null || value.isBlank()) return null;
        try {
            URI source = new URI(value);
            String scheme = source.getScheme() == null
                    ? null : source.getScheme().toLowerCase(Locale.ROOT);
            if (!("https".equals(scheme) || "http".equals(scheme))
                    || source.getHost() == null || source.getHost().isBlank()) {
                throw new IllegalArgumentException("document source URI is unsafe");
            }
            URI sanitized = new URI(
                    scheme, null, source.getHost(), source.getPort(),
                    source.getPath(), null, null).normalize();
            return sanitized.toASCIIString();
        } catch (URISyntaxException ex) {
            throw new IllegalArgumentException("document source URI is unsafe", ex);
        }
    }
}
