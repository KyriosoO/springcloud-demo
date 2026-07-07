package com.dylan.documentgeneration.model;

import java.util.List;

public record CitationBinding(
        String text,
        List<String> citationIds) {
}
