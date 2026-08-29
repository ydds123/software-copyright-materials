package com.example.inspection.strategy.handler;

import java.time.LocalDate;

/**
 * 立即推送并填写任务生成时段的实际处理者。
 *
 * 判定逻辑说明：
 * 本处理器承接责任链中「即时推送」分支，需同时满足以下任一条件组合：
 * 组合A：isImmediatelyPush=1 且 taskGenerateStartTime 晚于当前日期
 *        —— 适用于计划配置了未来生效日期但要求立即建立任务队列的场景
 * 组合B：isImmediatelyPush=1 且 任务生成时段起止至少填写其一
 *        且 taskType=1（固定周期）且 isCustomCycle≠1
 *        —— 适用于标准固定周期的即时下发场景
 * 两者均不满足时，将请求向下游 Handler 传递，由延时推送等处理器接管。
 */
public class ImmediatePushAndAssignHandler extends TaskGenerationHandler {

    private final ImmediatePushAndAssignFactory factory;

    public ImmediatePushAndAssignHandler(ImmediatePushAndAssignFactory factory) {
        this.factory = factory;
    }

    @Override
    public TaskGenerateResult handle(TaskGenerateRequest request) {
        boolean matchA = request.getIsImmediatelyPush() == 1
                && request.getTaskGenerateStartTime() != null
                && request.getTaskGenerateStartTime().isAfter(LocalDate.now());
        boolean matchB = request.getIsImmediatelyPush() == 1
                && (request.getStartTime() != null || request.getEndTime() != null)
                && request.getTaskType() == 1
                && request.getIsCustomCycle() != 1;
        if (matchA || matchB) {
            ImmediatePushAndAssignStrategy strategy = factory.select(request);
            return strategy.assign(request);
        }
        return next(request);
    }
}
