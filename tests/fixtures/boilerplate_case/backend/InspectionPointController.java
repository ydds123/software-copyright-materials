package com.example.inspection.controller;

import java.util.List;
import org.springframework.web.bind.annotation.*;

/**
 * 巡检点管理
 * @author Lion Li
 * @date 2025-04-11
 */
@RestController
@RequestMapping("/inspection/inspectionPoint")
public class InspectionPointController {

    @GetMapping("/list")
    public List<?> list(InspectionPoint bo) { return null; }

    @GetMapping("/export")
    public void export(InspectionPoint bo) { }

    @GetMapping("/{id}")
    public Object getInfo(@PathVariable Long id) { return null; }

    @PostMapping
    public int add(@RequestBody InspectionPoint bo) { return 0; }

    @PutMapping
    public int edit(@RequestBody InspectionPoint bo) { return 0; }

    @DeleteMapping("/{ids}")
    public int remove(@PathVariable Long[] ids) { return 0; }
}
