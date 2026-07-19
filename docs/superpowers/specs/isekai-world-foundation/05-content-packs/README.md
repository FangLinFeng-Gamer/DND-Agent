# 05 Content Packs

本层定义内容包和 catalog。它回答：

- 可复用内容如何写入 catalog。
- catalog 如何通过 validator。
- catalog 如何被 materializer 实例化为运行时实体。
- catalog、registry、rule bundle 和 snapshot 如何固定版本摘要。

## 权威规则

- [内容包、Catalog 与物化版本规则](./content-pack-materialization-rules.md)

## 当前 catalog

- [通用小物件 catalog](./catalogs/generic-item-catalog.json)
- [容器 catalog](./catalogs/container-catalog.json)

## 规则

```text
Catalog 不是运行时权威状态。
Catalog 字段必须满足字段域与注册表规则。
Catalog 中出现的新字符串不会自动成为合法 tag、category、rule_id 或 schema 字段。
Catalog 必须包含 schema_version、content_pack_id、content_pack_version、kind 和 catalog_version。
Materializer 必须是版本化纯函数，并输出带 provenance 的运行时实体。
Catalog 实例化后必须再次运行目标实体 validator。
```
