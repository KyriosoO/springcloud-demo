package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.plan.DocumentGenerationOptions;
import com.dylan.agent.kernel.validator.ValidatedPlan;

import java.util.Objects;
import java.util.Optional;

public final class ValidatedDocumentPlan implements ValidatedPlan {

    private final String capabilityId;
    private final String domain;
    private final DocumentCorpusKey selectedCorpus;
    private final ValidatedDocumentExecutionParameters parameters;
    private final DocumentGenerationOptions generationOptions;
    private final DocumentExecutionProfileProjection profile;

    ValidatedDocumentPlan(
            String capabilityId,
            String domain,
            DocumentCorpusKey selectedCorpus,
            ValidatedDocumentExecutionParameters parameters,
            DocumentGenerationOptions generationOptions,
            DocumentExecutionProfileProjection profile) {
        this.capabilityId = Objects.requireNonNull(capabilityId);
        this.domain = Objects.requireNonNull(domain);
        this.selectedCorpus = Objects.requireNonNull(selectedCorpus);
        this.parameters = Objects.requireNonNull(parameters);
        this.generationOptions = generationOptions;
        this.profile = Objects.requireNonNull(profile);
    }

    @Override
    public String capabilityId() {
        return capabilityId;
    }

    @Override
    public AgentPlanKind planKind() {
        return AgentPlanKind.DOCUMENT;
    }

    @Override
    public Optional<String> domain() {
        return Optional.of(domain);
    }

    public DocumentCorpusKey selectedCorpus(){return selectedCorpus;}
    public ValidatedDocumentExecutionParameters parameters(){return parameters;}

    public Optional<DocumentGenerationOptions> generationOptions() {
        return Optional.ofNullable(generationOptions);
    }

    public DocumentExecutionProfileProjection profile() { return profile; }
}
