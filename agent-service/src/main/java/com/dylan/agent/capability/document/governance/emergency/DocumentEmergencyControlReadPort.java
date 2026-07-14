package com.dylan.agent.capability.document.governance.emergency;
import java.time.Instant;
import java.util.List;
public interface DocumentEmergencyControlReadPort { DocumentEmergencyView readCurrent(List<DocumentEmergencyTargetRef> targets, Instant deadline); }
