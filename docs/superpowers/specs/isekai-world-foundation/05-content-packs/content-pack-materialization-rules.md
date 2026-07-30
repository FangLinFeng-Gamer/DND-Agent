---
doc_id: isekai.content_pack_materialization_rules
status: active
layer: content_packs
owner: content
created_at: 2026-07-18
updated_at: 2026-07-18
depends_on:
  - isekai.field_domain_registry_rules
  - isekai.world_generation_manifest_rules
  - isekai.world_object_rules
  - isekai.static_world_runtime_rules
provides:
  - ContentPackEnvelope
  - CatalogEnvelope
  - ContentMaterializationContext
  - MaterializationProvenance
  - CatalogMaterializerProtocol
  - ContentPackVersionLock
---

# 内容包、Catalog 与物化版本规则

## 背景

内容包和 catalog 是世界生成的输入，不是运行时权威状态。若 materializer 只写“大致合并顺序”，不同实现会在对象深合并、数组去重、实例 ID、hash 和存档恢复上产生不同结果。

本规则定义：内容包如何版本化、catalog 如何被规范化、materializer 如何作为纯函数输出运行时实体，以及 WorldState / EventLog / Snapshot 如何固定版本摘要。

## 目标

- 让同一 content pack、catalog、registry、rule bundle 和 seed 在任意机器上物化出相同实体。
- 让每个运行时实体能追溯到具体 pack、catalog entry、materializer 和版本摘要。
- 让 Snapshot 能判断当前代码是否可以直接读档，还是必须走迁移。
- 禁止 catalog、DM 文本或 AI proposal 绕过 validator 直接写权威状态。

## 非目标

- 不定义具体物品、动物、植物或地点内容。
- 不允许内容包新增 enum、rule_id、affordance、action policy 或 schema 字段。
- 不定义存档压缩、云同步或资源热更新方案。

## 核心原则

### 1. Catalog 是输入，不是状态

Catalog 只能提供候选、默认值和静态文本。运行时真实存在的是 `WorldObject`、`FloraPatch`、`CreaturePopulation`、`ResourceNode` 等权威实体。

### 2. Materializer 是版本化纯函数

同一个 `ContentMaterializationContext` 输入必须得到完全相同的输出实体和 ID。Materializer 不能读取未声明输入，不能依赖字典遍历顺序、线程数、当前时间、进程随机数或 LLM 输出。

```text
CatalogEnvelope
+ CatalogEntry
+ instance_overrides
+ ContentMaterializationContext
-> CatalogMaterializerProtocol
-> materialized entity candidate
-> target validator
-> GenerationCommitter
-> WorldState + EventLog
```

### 3. 版本锁必须贯穿生成、事件和快照

`schema_version`、`registry_hash`、`rule_bundle_hash` 和 `content_pack_hash` 必须同时出现在：

```text
WorldGenerationManifest.seed_material
AuthoritativeWorldState.version_lock
EventLogEntry.version_context
WorldSnapshot.version_lock
```

缺任一项时，状态不能进入可长期保存版本。

### 4. 升级只能通过迁移

读档时如果当前运行时代码的版本锁与 Snapshot 不一致，不能静默套用新规则解释旧状态。必须创建 `before_migration` Snapshot，执行 `SchemaMigrated` 或内容迁移事件，再创建 `after_migration` Snapshot。

## 数据结构

### ContentPackEnvelope

`ContentPackEnvelope` 是一个内容包的顶层发布单位。P1 允许一个物理 JSON 文件只承载一个 catalog，此时 `ContentPackEnvelope` 和 `CatalogEnvelope` 可以是同一个对象；如果未来一个内容包包含多个 catalog，顶层 `ContentPackEnvelope` 必须声明统一的 `content_pack_id/content_pack_version`，每个子 catalog 再声明自己的 `kind/catalog_version/catalog_hash`。

P1 当前两个 catalog 文件采用单 catalog envelope。

### CatalogEnvelope

所有 catalog 文件必须有版本化 envelope。实际 catalog 内容放在 `payload` 对应的根字段里，例如 `generic_item_catalog` 或 `container_catalog`。

```json
{
  "schema_version": 1,
  "content_pack_id": "isekai_generic_items_p0",
  "content_pack_version": "2026-07-18.1",
  "kind": "generic_item_catalog",
  "catalog_version": "2026-07-18.1",
  "generic_item_catalog": {
    "category_defaults": {},
    "entries": []
  }
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `schema_version` | catalog envelope schema 版本。 |
| `content_pack_id` | 内容包 ID。同一内容包升级时 ID 不变。 |
| `content_pack_version` | 内容包版本。任何会改变物化结果的修改都必须递增。 |
| `kind` | catalog 类型，例如 `generic_item_catalog`、`container_catalog`、`animal_species_catalog`。 |
| `catalog_version` | 该 catalog 的内容版本。任何 entry、category default 或语义变更都必须递增。 |
| `<kind>` | catalog payload 根字段，字段名必须与 `kind` 对应。 |

### ContentMaterializationContext

Materializer 每次实例化实体前，必须构造上下文：

```json
{
  "materialization_id": "mat_generic_bent_nail_dark_corner_001",
  "materializer_id": "GenericItemMaterializer",
  "materializer_version": "2026-07-18.1",
  "target_entity_type": "WorldObject",
  "target_schema_version": "world_object@2026-07-18",
  "world_id": "world_graystone_001",
  "content_pack_id": "isekai_generic_items_p0",
  "content_pack_version": "2026-07-18.1",
  "catalog_kind": "generic_item_catalog",
  "catalog_version": "2026-07-18.1",
  "catalog_id": "generic_bent_nail",
  "instance_key": "chunk_12_08_02/hunter_cabin_inside/dark_corner/loot_001",
  "registry_hash": "sha256:registry_hash",
  "rule_bundle_hash": "sha256:rule_bundle_hash",
  "content_pack_hash": "sha256:content_pack_hash",
  "catalog_entry_hash": "sha256:catalog_entry_hash"
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `materialization_id` | 本次物化记录 ID，由 context canonical hash 派生。 |
| `materializer_id` | 物化器 ID，例如 GenericItemMaterializer。 |
| `materializer_version` | 物化器规则版本，参与 rule bundle hash。 |
| `target_entity_type` | 物化目标实体类型。 |
| `target_schema_version` | 目标实体 schema 版本。 |
| `world_id` | 所属世界。 |
| `content_pack_id` / `content_pack_version` | 来源内容包及版本。 |
| `catalog_kind` / `catalog_version` / `catalog_id` | 来源 catalog 类型、版本和条目。 |
| `instance_key` | 场景内稳定实例键。必须由生成阶段显式提供，不能来自遍历序号。 |
| `registry_hash` | 当前字段、enum、registry 和 schema 的 canonical hash。 |
| `rule_bundle_hash` | 当前生成器、resolver、validator、materializer 规则的 canonical hash。 |
| `content_pack_hash` | 当前启用内容包集合的 canonical hash。 |
| `catalog_entry_hash` | catalog entry 规范化后的 canonical hash。 |

### MaterializationProvenance

运行时实体必须保存来源证明。`WorldObject` 使用 `provenance` 字段；生态、资源和社会实体如果由 catalog 物化，也必须使用同名结构。

```json
{
  "source_kind": "content_pack",
  "content_pack_id": "isekai_generic_items_p0",
  "content_pack_version": "2026-07-18.1",
  "catalog_kind": "generic_item_catalog",
  "catalog_id": "generic_bent_nail",
  "catalog_version": "2026-07-18.1",
  "materializer_id": "GenericItemMaterializer",
  "materializer_version": "2026-07-18.1",
  "materialization_id": "mat_generic_bent_nail_dark_corner_001",
  "instance_key": "chunk_12_08_02/hunter_cabin_inside/dark_corner/loot_001",
  "schema_version": "world_object@2026-07-18",
  "registry_hash": "sha256:registry_hash",
  "rule_bundle_hash": "sha256:rule_bundle_hash",
  "content_pack_hash": "sha256:content_pack_hash",
  "catalog_entry_hash": "sha256:catalog_entry_hash"
}
```

`source_kind` 闭集：

```text
content_pack
world_generator
resolver_created
migration_tool
test_fixture
legacy_import
```

LLM proposal、DM 文本和 projection 不能成为权威 `source_kind`。它们只能作为产生 resolver 输入或 proposal 审计的原因。

## Canonical hash 协议

所有参与版本锁的 hash 使用同一规范：

```text
canonical_json_utf8 -> sha256 -> "sha256:<hex>"
```

规范化规则：

1. JSON object key 按 Unicode code point 升序排序。
2. string 保持原文，不做本地化替换。
3. number 在进入 hash 前必须按 FieldSpec 规范化；P1 金额、重量、容量等守恒数值推荐使用 decimal string。
4. array 默认保留顺序；被声明为 set 的字段必须先去重并稳定排序。
5. 不允许把注释、文件路径、mtime、格式化空白或加载顺序纳入 hash。
6. Hash 计算失败时，catalog 不能加载，Snapshot 不能创建。

`content_pack_hash` 是当前启用内容包集合的聚合 hash：

```text
sha256(canonical_json_utf8([
  {content_pack_id, content_pack_version, kind, catalog_version, catalog_hash}
  sorted by content_pack_id, kind, catalog_version
]))
```

`registry_hash` 必须覆盖 FieldSpec、enum、registry、CanonicalEntitySchemaRegistry、FieldOwnership、WriteACL 和 event_type 闭集。

`rule_bundle_hash` 必须覆盖生成器、resolver、validator、materializer、Deriver、AI action policy 和迁移规则版本。

## 合并规则

Materializer 的 merge 顺序固定：

```text
1. catalog.category_defaults[entry.category]
2. catalog entry override
3. instance_overrides
4. system fields
5. target validator / derived fields
```

规则表：

| 字段类型 | 合并规则 |
| --- | --- |
| scalar | 后一层替换前一层。 |
| object | 只在 schema 明确允许的对象路径递归深合并。 |
| nullable scalar | `null` 表示显式设置为空，不表示删除字段。 |
| array:set | 并集、去重、按 registry 顺序再按字典序排序。适用于 `tags`、`affordances`、`materials`、`traits`。 |
| array:ordered | 保留来源顺序，后层整体替换前层。适用于 `aliases`、叙事展示顺序。 |
| array:contents | catalog 默认必须为空；实例内容只能由场景实例、发现表或 resolver 提供。 |
| unknown path | 拒绝。 |

删除字段只允许迁移工具通过 `delete_for_migration` 执行，Materializer 不允许表达删除。

## 实例 ID 规则

运行时实体 ID 不能直接使用 `catalog_id`，也不能使用临时遍历序号。

```text
entity_id = namespace + "_" + stable_slug(catalog_id) + "_" + short_hash(
  world_id,
  target_entity_type,
  catalog_kind,
  catalog_id,
  instance_key,
  materializer_id,
  materializer_version
)
```

`instance_key` 必须由生成阶段显式提供，例如：

```text
chunk_12_08_02/hunter_cabin_inside/dark_corner/loot_001
old_furnace_inn/front_hall/counter/display_bowl_001
```

同一 context 物化两次得到同一 ID；两个不同 context 得到同一 ID 时，validator 必须拒绝并报告 ID collision。

## 物化提交规则

Materializer 只能输出候选实体，不能直接写 `WorldState`。

```text
Materializer output
-> FieldDomainValidator
-> target entity Validator
-> GenerationOutputValidator
-> GenerationCommitter
-> EventLogEntry(version_context)
-> AuthoritativeWorldState(version_lock)
```

提交成功后必须满足：

1. 实体包含 `provenance`。
2. `provenance` 中的 hash 与当前 `WorldState.version_lock` 一致。
3. EventLogEntry 包含同一份 `version_context`。
4. Snapshot 能覆盖该实体和对应 generation audit。

## 迁移规则

加载 Snapshot 时：

```text
if snapshot.version_lock == runtime.version_lock:
  restore + validate
else:
  require MigrationPlan
```

迁移必须：

1. 创建 `before_migration` Snapshot。
2. 运行 migration tool，并只写迁移计划允许的字段。
3. 形成 `SchemaMigrated` StateTransition：preconditions 记录旧 `World.version_lock`，changes 更新新 `World.version_lock`，`version_context` 等于新版本锁，并由 StateTransitionCommitter 生成 EventLogEntry。
4. 创建 `after_migration` Snapshot。
5. 重放并校验 canonical hash。

禁止：

```text
静默用新 catalog 重新解释旧实体。
按新默认值覆盖旧实体 provenance。
迁移时让 LLM 决定字段改动。
只改 Snapshot.version_lock 而不改对应实体和 EventLog。
```

## 硬规则

1. CatalogEnvelope 必须包含 `schema_version/content_pack_id/content_pack_version/kind/catalog_version`。
2. CatalogEnvelope 的 payload 根字段必须与 `kind` 对应。
3. 内容包不能新增未注册字段、enum、affordance、rule_id、event_type 或 action_type。
4. Materializer 必须使用 `ContentMaterializationContext`。
5. Materializer 不能依赖运行时遍历顺序、当前时间、线程数或进程随机数。
6. Materializer 输出必须包含 `provenance`。
7. `provenance.source_kind=content_pack` 时，pack、catalog、materializer、schema、registry、rule 和 content hash 必须完整。
8. `content_pack_hash`、`registry_hash`、`rule_bundle_hash` 不一致时，Snapshot 不能直接恢复。
9. 版本升级必须通过 StateTransitionCommitter 生成迁移 EventLogEntry，并创建迁移前后 Snapshot。
10. Catalog、projection、DM 文本和 AI proposal 不能直接成为权威状态。

## 验收测试

```text
test_catalog_envelope_requires_versions
test_catalog_payload_kind_must_match
test_materializer_is_stable_across_dict_order
test_materializer_is_stable_across_thread_count
test_materializer_id_uses_instance_key_not_iteration_order
test_array_set_merge_dedupes_and_sorts
test_array_ordered_merge_replaces
test_materialized_entity_requires_provenance
test_provenance_hashes_match_world_version_lock
test_snapshot_rejects_version_lock_mismatch_without_migration
test_schema_migration_creates_before_and_after_snapshots
test_migration_cannot_change_version_lock_without_eventlog
```
