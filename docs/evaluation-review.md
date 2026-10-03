# 新评测集的审核与运行

Human review comes before scoring. The current 30-case dataset is still a candidate, not accepted evidence.

先审核再测量。`backend/evals/holdout_v3_candidate.json` 仍是 30 条候选用例，本轮没有修改它的标签、代签人工审核或产生新的模型准确率。

## 你或同学需要审核什么

可以直接填写 [三十条人工审核表](evaluation-review-sheet.md)，不必先阅读 JSON。表里是原候选标签，不是模型结果；审核表填写完以后仍需按下文更新源文件与哈希。

逐条看输入、人物和预期行为：它应该生成计划、直接命令、回答状态、先澄清，还是拒绝范围外任务？“只调灯”不能顺带改变空调；“更凉”要明确比较个人偏好还是当前温度；含糊的表达不能只因模型碰巧输出一个值就算正确。

先确认产品支持范围，再确认预期标签。存在歧义的题可以修改或移入开发集，但要在本轮模型测试前完成。不要根据模型答案反向改验收标准。

## 怎样冻结

以下命令只打印数量、状态和用例哈希，不评分、不调用模型：

```bash
cd backend
python scripts/evaluate_holdout.py --dataset evals/holdout_v3_candidate.json --review-info
```

人工审核完成后，记录真实审核人和时间，把状态改为 `accepted`、`human_reviewed` 改为 true，填写 `reviewer`、带时区的 `reviewed_at`、当前用例的 `reviewed_cases_sha256`。不要由 AI 自行声称完成了人工审核。哈希只检查用例有无改变，不是电子签名，也不能证明审核质量。

修改用例后哈希失配，脚本会拒绝继续按旧审核运行。v3 及以后未审核或候选集，不允许评分；旧 v1/v2 仍可跑历史回归，但不作为新的独立验收集。

## 审核后运行

确认本地环境已配置模型密钥后使用；密钥只在本机，不提交到仓库。

```bash
python scripts/evaluate_holdout.py --dataset evals/holdout_v3_candidate.json --model --output evals/results/v3-evaluation.json
python scripts/compare_models.py --dataset evals/holdout_v3_candidate.json --output evals/results/v3-model-comparison.json
```

结果包含数据集哈希、审核人/时间、模型、超时/输出预算和逐条结果。只重点看语义符合性、P50/P95、降级原因；不因 JSON 校验通过就认为模型理解正确。出现失败照实保留。如果拿这批题调提示词，它们就变成回归题，需要另留一批新验收题。

当前服务层计时不包含平板渲染，不得写成真机端到端响应时间；小样本比较不保证总体提速。此前连接复用 P95 没有改善，因此仍默认关闭。本轮没有新增付费模型调用。
