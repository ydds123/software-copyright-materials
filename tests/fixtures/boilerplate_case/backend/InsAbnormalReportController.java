package com.example.inspection.controller;

import java.util.List;
import org.springframework.web.bind.annotation.*;

/**
 * 异常上报管理
 * @author Lion Li
 * @date 2025-04-11
 */
@RestController
@RequestMapping("/inspection/abnormalReport")
public class InsAbnormalReportController {

    @GetMapping("/list")
    public List<?> list(InsAbnormalReport bo) { return null; }

    @GetMapping("/export")
    public void export(InsAbnormalReport bo) { }

    @GetMapping("/{id}")
    public Object getInfo(@PathVariable Long id) { return null; }

    @PostMapping
    public int add(@RequestBody InsAbnormalReport bo) { return 0; }

    @PutMapping
    public int edit(@RequestBody InsAbnormalReport bo) { return 0; }

    @DeleteMapping("/{ids}")
    public int remove(@PathVariable Long[] ids) { return 0; }
}
