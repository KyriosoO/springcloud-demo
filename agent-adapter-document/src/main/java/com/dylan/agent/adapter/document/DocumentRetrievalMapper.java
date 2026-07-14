package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.*;
import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;
import com.dylan.agent.adapter.api.operation.ResourceLimitReference;
import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentProtectedFilterDto;
import com.dylan.esquery.api.model.DocumentSearchChannel;
import com.dylan.esquery.api.model.document.*;

import java.util.List;

/** DocumentRetrievalCommand 到 strict wire contract 的一对一 mapper。 */
public final class DocumentRetrievalMapper {
    public HybridSearchRequest toDocumentHybridRequest(DocumentRetrievalCommand command,CapabilityOperationContext context){
        if(!command.executionBinding().resourceLimitReference().equals(context.resourceLimits().reference())
                ||!command.protectedFilter().resourceLimitReference().equals(context.resourceLimits().reference())){
            throw new IllegalArgumentException("document command/context resource binding mismatch");}
        ResourceLimitBindingDto limit=limit(context.resourceLimits().reference());
        var execution=command.executionBinding();
        var wireExecution=new DocumentSearchExecutionBinding(execution.profileName(),execution.documentProfileVersion(),execution.profileProjectionDigest(),
                limit,execution.authorizationBindingDigest(),execution.aclEvidenceDigest());
        var wireQuery=new DocumentQueryPlan(command.preparedQuery().normalizedOriginal(),command.preparedQuery().ruleKeywords(),command.preparedQuery().rewriteCandidates(),
                command.preparedQuery().embedding().map(value->new DocumentQueryEmbeddingDto(value.vector(),value.dimension(),value.bindingReference().canonicalDigest())));
        List<DocumentHybridChannelRequest> channels=command.channels().enabled().stream().map(channel->new DocumentHybridChannelRequest(
                DocumentSearchChannel.valueOf(channel.name()),command.channels().required().contains(channel),command.channels().weights().get(channel),
                command.channels().candidatesPerChannel())).toList();
        return new HybridSearchRequest(new DocumentCorpusKeyDto(command.corpusKey().domain(),command.corpusKey().materialType()),wireExecution,
                command.callerFilters().stream().map(filter->new DocumentCallerFilterNode(filter.field(),
                        DocumentCallerFilterNode.Operator.valueOf(filter.operator().name()),filter.value(),filter.values())).toList(),
                protectedNode(command.protectedFilter().root()),command.protectedFilter().filterDigest(),wireQuery,channels,
                new HybridFusionRequest(command.fusion().rrfK(),command.fusion().maxFusedCandidates()),
                new HybridDedupRequest(command.dedup().maxReturnedDocuments(),command.dedup().maxChunksPerDocument()),
                new HybridContextRequest(command.context().beforeChunks(),command.context().afterChunks(),command.context().maxContextChars()),
                new DocumentSearchOperationMetadata(context.requestCorrelationId(),context.operationId(),context.operationType().value(),
                        context.absoluteDeadline().toEpochMilli(),limit.registrationIdentity(),limit));
    }
    private ResourceLimitBindingDto limit(ResourceLimitReference ref){return new ResourceLimitBindingDto(ref.contractRef().namespace(),ref.contractRef().name(),
            ref.contractRef().version(),ref.canonicalDigest(),ref.invocationId(),ref.registrationIdentity());}
    private DocumentProtectedFilterDto protectedNode(DocumentProtectedFilterNode node){return switch(node){
        case DocumentAllOf all->composite(DocumentProtectedFilterDto.Kind.ALL_OF,all.children());case DocumentAnyOf any->composite(DocumentProtectedFilterDto.Kind.ANY_OF,any.children());
        case DocumentExactTerm exact->new DocumentProtectedFilterDto(DocumentProtectedFilterDto.Kind.EXACT,DocumentProtectedFilterDto.Field.valueOf(exact.field().name()),exact.value(),List.of(),List.of());
        case DocumentAnyTerms any->new DocumentProtectedFilterDto(DocumentProtectedFilterDto.Kind.ANY_TERMS,DocumentProtectedFilterDto.Field.valueOf(any.field().name()),null,any.values().stream().sorted().toList(),List.of());
        case DocumentNoneTerms none->new DocumentProtectedFilterDto(DocumentProtectedFilterDto.Kind.NONE_TERMS,DocumentProtectedFilterDto.Field.valueOf(none.field().name()),null,none.values().stream().sorted().toList(),List.of());};}
    private DocumentProtectedFilterDto composite(DocumentProtectedFilterDto.Kind kind,List<DocumentProtectedFilterNode> children){return new DocumentProtectedFilterDto(kind,null,null,List.of(),children.stream().map(this::protectedNode).toList());}
}
