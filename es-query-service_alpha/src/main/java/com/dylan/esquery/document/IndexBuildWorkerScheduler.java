package com.dylan.esquery.document;

import org.springframework.scheduling.annotation.Scheduled;

import java.lang.management.ManagementFactory;
import java.util.UUID;

/** 单次只领取一个 task；数据库 lease 支持多实例并发与崩溃恢复。 */
public final class IndexBuildWorkerScheduler {
    private final IndexBuildWorker worker;
    private final String leaseOwner;
    public IndexBuildWorkerScheduler(IndexBuildWorker worker) {
        this.worker = worker;
        this.leaseOwner = "esq-" + Integer.toHexString(ManagementFactory.getRuntimeMXBean().getName().hashCode())
                + "-" + UUID.randomUUID().toString().substring(0, 8);
    }
    @Scheduled(fixedDelayString = "${document-rebuild.poll-delay:2s}")
    public void poll() { worker.runNext(leaseOwner); }
}
