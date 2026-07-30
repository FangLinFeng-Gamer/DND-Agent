# 01 Governance

本层定义所有世界文档必须遵守的元规则。它回答：

- 字段值是否合法。
- tag、rule_id、event_type 如何注册。
- schema 是否允许额外字段。
- LLM proposal、Catalog、EventLog 如何接受字段值。
- seed、随机流、候选权重和抽样如何保持确定性。

## 当前文档

- [字段域与注册表规则](./field-domain-registry-rules.md)
- [确定性随机协议](./deterministic-random-protocol-rules.md)
- [可执行数值算法规则](./executable-numeric-algorithm-rules.md)

## 规则

```text
新增字段必须声明 FieldDomainKind。
新增 tag 必须进入对应 registry。
新增 rule_id 必须进入规则注册表。
新增 schema 默认 additionalProperties=false。
任何随机抽样必须使用确定性随机协议。
任何进入长期可重放基线的数值算法必须使用可执行数值算法规则。
治理层优先级高于世界模型、运行时和内容包。
```
