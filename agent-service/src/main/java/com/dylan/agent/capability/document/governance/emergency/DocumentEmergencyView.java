package com.dylan.agent.capability.document.governance.emergency;
import java.time.Instant;
import java.util.List;
public record DocumentEmergencyView(String viewVersion,List<Decision> decisions,Instant checkedAt,Instant validUntil,String canonicalDigest) {
    public DocumentEmergencyView {
        if(viewVersion==null||viewVersion.isBlank()||checkedAt==null||validUntil==null
                ||validUntil.isBefore(checkedAt)||canonicalDigest==null||!canonicalDigest.matches("[0-9a-f]{64}"))
            throw new IllegalArgumentException("emergency view incomplete");
        decisions=List.copyOf(decisions==null?List.of():decisions);
    }
    public record Decision(String targetType,String targetDigest,Outcome outcome,String reasonCode){
        public Decision {
            if(targetType==null||targetType.isBlank()||targetDigest==null||!targetDigest.matches("[0-9a-f]{64}")||outcome==null
                    ||(outcome!=Outcome.NOT_BLOCKED&&(reasonCode==null||reasonCode.isBlank())))
                throw new IllegalArgumentException("emergency decision incomplete");
        }
    }
    public enum Outcome{NOT_BLOCKED,BLOCKED,FAILURE}
    public boolean allows(){return decisions.stream().allMatch(d->d.outcome()==Outcome.NOT_BLOCKED);}
}
