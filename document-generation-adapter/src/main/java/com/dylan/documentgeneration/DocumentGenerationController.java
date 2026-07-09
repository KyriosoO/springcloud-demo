package com.dylan.documentgeneration;

import com.dylan.agent.adapter.api.document.generation.DocumentGenerationRequest;
import com.dylan.agent.adapter.api.document.generation.DocumentGenerationResult;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class DocumentGenerationController {
    private final DeepSeekDocumentGenerationClient generationClient;

    public DocumentGenerationController(DeepSeekDocumentGenerationClient generationClient) {
        this.generationClient = generationClient;
    }

    @PostMapping("/document-generation")
    public DocumentGenerationResult generate(@Valid @RequestBody DocumentGenerationRequest request) {
        return generationClient.generate(request);
    }
}
