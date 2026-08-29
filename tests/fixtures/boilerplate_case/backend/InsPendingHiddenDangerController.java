package com.example.inspection.controller;

import java.util.List;
import org.springframework.web.bind.annotation.*;

/**
 * 待治理隐患管理
 * @author Lion Li
 * @date 2025-04-11
 */
@RestController
@RequestMapping("/inspection/pendingHiddenDanger")
public class InsPendingHiddenDangerController {

    @GetMapping("/list")
    public List<?> list(InsPendingHiddenDanger bo) { return null; }

    @GetMapping("/export")
    public void export(InsPendingHiddenDanger bo) { }

    @GetMapping("/{id}")
    public Object getInfo(@PathVariable Long id) { return null; }

    @PostMapping
    public int add(@RequestBody InsPendingHiddenDanger bo) { return 0; }

    @PutMapping
    public int edit(@RequestBody InsPendingHiddenDanger bo) { return 0; }

    @DeleteMapping("/{ids}")
    public int remove(@PathVariable Long[] ids) { return 0; }
}
