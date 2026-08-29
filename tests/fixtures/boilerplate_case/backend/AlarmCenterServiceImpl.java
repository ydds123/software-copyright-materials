package com.example.alarm.service.impl;

import javax.annotation.PostConstruct;
import javax.annotation.PreDestroy;
import org.springframework.stereotype.Service;

/**
 * 报警中心服务实现。
 *
 * 核心机制：
 * 1. @PostConstruct 定时刷新任务初始化，加载告警分级矩阵缓存
 * 2. @PreDestroy 优雅关闭，取消刷新任务
 * 3. 多租户遍历推送（TenantHelper.run），按租户隔离上下文执行推送
 * 4. buildAlarmContent 模板占位符替换：
 *    {monitoringPoint} 监测点名称
 *    {limitType}       阈值类型
 *    {monitoredValue}  监测值
 *    {limitInterval}   限值区间
 */
@Service
public class AlarmCenterServiceImpl implements AlarmCenterService {

    @PostConstruct
    public void initRefreshTask() {
        // 启动定时刷新任务：周期重载告警分级矩阵与推送人员规则缓存
    }

    @PreDestroy
    public void shutdown() {
        // 取消定时任务，等待进行中的推送批次完成
    }

    @Override
    public void pushPersonAlarm(MwAlarmRecord record) {
        TenantHelper.run(record.getTenantId(), () -> {
            String content = buildAlarmContent(record);
            pushToAssignedUsers(record, content);
        });
    }

    private String buildAlarmContent(MwAlarmRecord record) {
        return alarmTemplate
                .replace("{monitoringPoint}", record.getPointName())
                .replace("{limitType}", record.getLimitType())
                .replace("{monitoredValue}", record.getMonitoredValue())
                .replace("{limitInterval}", record.getLimitInterval());
    }
}
