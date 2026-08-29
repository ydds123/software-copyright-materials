package com.example.alarm.domain;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 告警记录实体
 */
public class MwAlarmRecord {

    private Long id;
    private Long tenantId;
    private Long pointId;
    private String pointName;
    private String limitType;
    private String monitoredValue;
    private String limitInterval;
    private Integer alarmLevel;
    private Integer status;
    private Long pushUserId;
    private String content;
    private LocalDateTime createTime;
    // 其余字段省略，纯 POJO 无业务逻辑
}
