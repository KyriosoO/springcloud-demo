package com.dylan.agent.conversation;

import java.time.Clock;
import java.time.LocalDateTime;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import com.dylan.agent.config.AgentProperties;

/**
 * 定时清理过期 Conversation 和 Turn。
 */
@Component
public class ConversationCleanupJob {

    private static final Logger log = LoggerFactory.getLogger(ConversationCleanupJob.class);

    private final ConversationService conversationService;
    private final AgentProperties properties;
    private final Clock clock;

    public ConversationCleanupJob(ConversationService conversationService,
                                  AgentProperties properties, Clock clock) {
        this.conversationService = conversationService;
        this.properties = properties;
        this.clock = clock;
    }

    @Scheduled(fixedDelayString = "${agent.conversation.cleanup-delay:1h}")
    public void cleanup() {
        LocalDateTime cutoff = LocalDateTime.now(clock)
                .minusDays(properties.getConversation().getRetentionDays());
        int deleted = conversationService.cleanupExpired(cutoff);
        log.info("Scheduled cleanup completed: {} total records deleted.", deleted);
    }
}
