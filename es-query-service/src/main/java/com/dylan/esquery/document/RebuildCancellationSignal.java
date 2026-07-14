package com.dylan.esquery.document;

/** Rebuild 页/批次边界使用的本地只读取消信号。 */
@FunctionalInterface
public interface RebuildCancellationSignal {
    boolean isCancellationRequested();
}
