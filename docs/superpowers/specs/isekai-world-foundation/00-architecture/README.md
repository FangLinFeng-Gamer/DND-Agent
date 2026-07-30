# 00 Architecture

本层定义异世界模式世界底座的总架构。它回答：

- 世界底座有哪些大集合。
- 大集合之间如何产生影响。
- 每个权威 EntityType 由哪个文档定义唯一 canonical schema。
- 生成阶段和运行时阶段如何区分。
- 文档系统如何分层阅读。

## 当前文档

- [世界集合与影响规则](./world-collection-influence-rules.md)
- [世界生成输出清单规则](./world-generation-manifest-rules.md)
- [生成失败恢复与断点续生成规则](./generation-recovery-rules.md)
- [FormationRule 合约与注册表规则](./formation-rule-contract-rules.md)

## 规则

```text
新增世界底座级概念时，先进入本层。
如果一个设计会影响多个集合，必须先更新世界集合与影响规则。
新增权威 EntityType 时，必须先登记唯一 canonical schema owner。
本层不写具体内容包和具体剧情。
```
