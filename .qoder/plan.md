# 自动化代码审查与修复迭代工作流

## Context

当前分支 `fix/prd-alignment-remediation` 包含 6 个 commit（领先 `main`），涉及 49 个文件、+2617/-322 行改动，覆盖 API（evals、approvals、agent、metrics、health 等）和 Web（导航、账户页、E2E 测试）两大模块。分支尚未推送到远程，也没有对应的 PR。

目标：推送分支、创建 PR、使用 `review-swarm` 技能进行多轮自动审查与修复，直到审查通过。

## 当前状态

- **分支**: `fix/prd-alignment-remediation`（仅本地）
- **远程**: `origin` (https://github.com/leihuang23/ops-agent.git)
- **改动**: 49 files, +2617/-322
- **未提交**: 无（仅 untracked `.trae/`）
- **工具**: `gh` v2.95.0 可用且已认证

---

## Task 1: 准备阶段

1. 在 `.gitignore` 中追加 `.trae/`，避免工具私有状态被提交
2. 提交该改动：`chore: add .trae/ to gitignore`
3. 推送分支：`git push -u origin fix/prd-alignment-remediation`
4. 创建 PR：
   ```bash
   gh pr create \
     --base main \
     --head fix/prd-alignment-remediation \
     --title "fix: PRD alignment remediation – evals, approvals, perf, a11y" \
     --body "<变更摘要>"
   ```
5. 记录 PR 编号供后续迭代使用

## Task 2: 第一轮 review-swarm 审查

- 调用 `review-swarm` 技能对 PR diff 进行全面审查
- 解析并分类 findings：
  - **P0** (Bug/Security) — 必须修复
  - **P1** (Performance) — 本轮修复
  - **P2** (Style/Docs) — 本轮修复
  - **P3** (Nit/Suggestion) — 记录但可延后

## Task 3: 修复循环（每轮）

每轮执行以下步骤：

1. **分析 findings** — 提取每个问题的文件路径、行号、描述、修复方案
2. **执行修复** — 按 P0 → P1 → P2 优先级修改代码
3. **验证修复** — 运行相关测试：
   - API: `cd apps/api && .venv/bin/pytest tests/ -x -q`
   - Web: `cd apps/web && npx tsc --noEmit`
4. **提交并推送**：
   ```bash
   git add -A
   git commit -m "fix(review-round-{N}): address review findings – <摘要>"
   git push origin fix/prd-alignment-remediation
   ```
5. **发布 PR 评论** — 使用 `gh pr comment` 说明本轮修复内容

## Task 4: 重新审查与终止判断

每轮修复推送后，重新调用 `review-swarm`，检查终止条件：

| 条件 | 行为 |
|------|------|
| review-swarm 返回 0 个新 issue | 正常终止，标记 PR ready |
| 迭代轮次 > 5（安全上限） | 强制终止，请求人工评审 |
| 连续两轮 findings 完全重复（无收敛） | 提前终止，说明存在结构性问题 |
| 修复引入无法解决的测试失败 | 回滚该轮，终止并标记需人工介入 |

## Task 5: 最终确认

- 确认 review-swarm 无新问题后，在 PR 添加评论总结整个审查过程
- 为 PR 添加 `ready-for-review` 标签

---

## 关键文件

- `.gitignore` — 添加 `.trae/`
- `apps/api/app/` — API 侧主要改动（evals, approvals, agent, metrics, health, cache, core）
- `apps/api/tests/` — API 测试文件
- `apps/web/app/` — Web 侧改动（Nav, accounts, agent runs, incidents）
- `apps/web/e2e/` — E2E 测试
- `apps/web/lib/api.ts` — Web API 客户端

## 验证方法

1. 每轮修复后运行 `pytest tests/ -x -q`（API）和 `tsc --noEmit`（Web）
2. 每轮推送后通过 `review-swarm` 确认问题是否已解决
3. 最终确认 PR 在 GitHub 上的 CI 检查通过
