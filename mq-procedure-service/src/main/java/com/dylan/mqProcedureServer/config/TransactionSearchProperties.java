package com.dylan.mqprocedureserver.config;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@ConfigurationProperties(prefix = "transaction.search")
public class TransactionSearchProperties implements InitializingBean {

    private int maxExactTotal;

    public int getMaxExactTotal() {
        return maxExactTotal;
    }

    public void setMaxExactTotal(int maxExactTotal) {
        this.maxExactTotal = maxExactTotal;
    }

    @Override
    public void afterPropertiesSet() {
        if (maxExactTotal < 1 || maxExactTotal > Integer.MAX_VALUE - 1) {
            throw new IllegalStateException(
                    "transaction.search.max-exact-total 必须在 1～" + (Integer.MAX_VALUE - 1) + " 之间");
        }
    }
}
