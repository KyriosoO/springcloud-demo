package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.document.AdapterDocumentRetrievalResult;
import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.adapter.api.document.DocumentRetrievalCommand;
import com.dylan.agent.adapter.api.operation.*;
import feign.FeignException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.util.Optional;

/** Document Adapter 只协调 mapper/client/validator，并形成一次 attempt typed outcome。 */
@Component
public final class DocumentAgentAdapter implements DocumentRetrievableAdapter {
    private static final Logger log= LoggerFactory.getLogger(DocumentAgentAdapter.class);
    private static final ProviderSafeIdentity PROVIDER=new ProviderSafeIdentity("es-query-service", Optional.empty());
    private final DocumentSearchClient client;private final DocumentRetrievalMapper mapper;private final DocumentEvidenceMapper evidenceMapper;
    private final DocumentRetrievalResponseBindingValidator validator;private final Clock clock;
    public DocumentAgentAdapter(DocumentSearchClient client,DocumentRetrievalMapper mapper,DocumentEvidenceMapper evidenceMapper,
                                DocumentRetrievalResponseBindingValidator validator,Clock clock){
        this.client=client;this.mapper=mapper;this.evidenceMapper=evidenceMapper;this.validator=validator;this.clock=clock;}
    @Override public CapabilityOperationOutcome<AdapterDocumentRetrievalResult> retrieve(DocumentRetrievalCommand command,CapabilityOperationContext context){
        long started=System.nanoTime();
        if(context.cancellation().isCancelled())return failure(context,0,CapabilityOperationFailureCode.CANCELLED,CapabilityOperationTermination.CANCELLED,started);
        if(!clock.instant().isBefore(context.absoluteDeadline()))return failure(context,0,CapabilityOperationFailureCode.DEADLINE_EXCEEDED,CapabilityOperationTermination.DEADLINE_EXCEEDED,started);
        try{
            context.resourceLimits().require(com.dylan.agent.api.contract.common.AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT,DocumentResourceLimit.class);
            var response=client.documentHybridSearch(mapper.toDocumentHybridRequest(command,context));
            if(context.cancellation().isCancelled())return failure(context,1,CapabilityOperationFailureCode.CANCELLED,CapabilityOperationTermination.CANCELLED,started);
            if(!clock.instant().isBefore(context.absoluteDeadline()))return failure(context,1,CapabilityOperationFailureCode.LATE_RESULT,CapabilityOperationTermination.DEADLINE_EXCEEDED,started);
            var bound=validator.validate(response,command,context);var candidate=evidenceMapper.toAdapterResult(response,bound,command,context);
            return new CapabilityOperationSuccess<>(candidate,metadata(context,1,CapabilityOperationTermination.SUCCEEDED,"document-retrieval-ok",started));
        }catch(IllegalArgumentException ex){log.warn("Document retrieval contract rejected: operationId={}",context.operationId());
            return failure(context,0,CapabilityOperationFailureCode.INVALID_REQUEST,CapabilityOperationTermination.REJECTED,started);
        }catch(FeignException ex){log.error("Document search Feign error: status={}",ex.status());
            return failure(context,1,CapabilityOperationFailureCode.PROVIDER_FAILED,CapabilityOperationTermination.FAILED,started);
        }catch(RuntimeException ex){log.error("Document search response rejected: operationId={}",context.operationId());
            return failure(context,1,CapabilityOperationFailureCode.INVALID_RESPONSE,CapabilityOperationTermination.REJECTED,started);}
    }
    private CapabilityOperationFailure<AdapterDocumentRetrievalResult> failure(CapabilityOperationContext context,int attempts,
            CapabilityOperationFailureCode code,CapabilityOperationTermination termination,long started){String diagnostic="document-retrieval-"+context.operationId()+"-"+code.name().toLowerCase(java.util.Locale.ROOT);
        return new CapabilityOperationFailure<>(code,diagnostic,metadata(context,attempts,termination,diagnostic,started));}
    private CapabilityOperationMetadata metadata(CapabilityOperationContext context,int attempts,CapabilityOperationTermination termination,String diagnostic,long started){
        return new CapabilityOperationMetadata(context.operationId(),context.operationType(),PROVIDER,attempts,
                Math.max(0,(System.nanoTime()-started)/1_000_000L),termination,diagnostic,context.resourceLimits().reference(),false,
                termination==CapabilityOperationTermination.DEADLINE_EXCEEDED,
                termination==CapabilityOperationTermination.CANCELLED);}
}
