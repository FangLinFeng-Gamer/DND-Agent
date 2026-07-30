# 异世界世界底座设计问题（临时）

## 1. FormationRule.random 承载不了实际 DRP 抽样声明

draw_policy 是规则声明的随机策略；RandomDrawRef.draw_kind 是实际抽样类型。FormationRule 只有 uses_random/stream_domain/draw_policy/max_rejection_attempts，见 [formation-rule-contract-rules.md (line 156)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/00-architecture/formation-rule-contract-rules.md:156)，而 draw_policy 闭集是候选选择策略，见 [formation-rule-contract-rules.md (line 306)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/00-architecture/formation-rule-contract-rules.md:306)。但 DRP 的实际 draw_kind 包含 fixed_unit/int_range/id_suffix 等，见 [deterministic-random-protocol-rules.md (line 314)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/01-governance/deterministic-random-protocol-rules.md:314)，数值算法又要求 NumericAlgorithmSpec.random_draws 被 FormationRule 覆盖，见 [executable-numeric-algorithm-rules.md (line 876)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/01-governance/executable-numeric-algorithm-rules.md:876)。

实现后果：ready 数值算法无法写出完整 FormationRuleContract。解决条件：在 FormationRule.random 中加入可机读的 random_draws/logical_draw_id/draw_kind 列表，或明确映射规则。

## 2. terrain 规则的 stage ID 和算法状态不一致

stage_contract_id 是规则挂载的生成阶段 ID。FormationRule 示例和 registry 使用 stage_contract_terrain_candidate，见 [formation-rule-contract-rules.md (line 99)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/00-architecture/formation-rule-contract-rules.md:99) 和 [formation-rule-contract-rules.md (line 362)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/00-architecture/formation-rule-contract-rules.md:362)；但 manifest / recovery 使用 stage_contract_terrain_candidate_formation，见 [world-generation-manifest-rules.md (line 147)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/00-architecture/world-generation-manifest-rules.md:147)。

同一算法 terrain.classify_base_fields.fixed_point.v1 在 FormationRule 中是 contract_only，见 [formation-rule-contract-rules.md (line 104)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/00-architecture/formation-rule-contract-rules.md:104)，在 NumericAlgorithmRegistry 中是 ready，见 [executable-numeric-algorithm-rules.md (line 327)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/01-governance/executable-numeric-algorithm-rules.md:327)。而规则要求二者状态相等，见 [executable-numeric-algorithm-rules.md (line 873)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/01-governance/executable-numeric-algorithm-rules.md:873)。

解决条件：统一 stage ID；并决定该算法到底是 ready 还是 contract_only。

## 3. FormationRule 的 terrain 字段路径使用了不存在的字段

read_set/output_set 是规则声明的读写字段集合。FormationRule 示例读取 base_fields.roughness、base_fields.flow_potential，输出 terrain.type/terrain.roughness/terrain.tags，见 [formation-rule-contract-rules.md (line 121)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/00-architecture/formation-rule-contract-rules.md:121) 和 [formation-rule-contract-rules.md (line 138)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/00-architecture/formation-rule-contract-rules.md:138)。但实际基础场是 rockiness/water_flow 等八项，见 [climate-terrain-formation-rules.md (line 1056)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/climate-terrain-formation-rules.md:1056)；terrain 实际字段是 landform/terrain_tags 等，见 [climate-terrain-formation-rules.md (line 386)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/climate-terrain-formation-rules.md:386)。

实现后果：字段子集校验必然失败，或实现私下做别名映射。解决条件：把 FormationRule 示例和 registry 改成 canonical 字段名。

## 4. InitialKnowledgeFormation 示例仍违反 world 单 envelope 规则

GeneratorOutputEnvelope 是一包生成阶段输出。当前规则已经规定 execution_scope=world && parallelizable=false 时只能产生一个 scope.kind=world 的 envelope，见 [world-generation-manifest-rules.md (line 576)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/00-architecture/world-generation-manifest-rules.md:576)。但同文件示例仍写 scope.kind=site，见 [world-generation-manifest-rules.md (line 479)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/00-architecture/world-generation-manifest-rules.md:479)。

实现后果：照示例输出会被本文件自己的 validator 拒绝。解决条件：示例 envelope 改成 world:<world_id>，站点粒度放入 item payload 或 target scope。

## 5. 容器 catalog 仍是旧容量模型

components.container.capacity 是容器容量；新版要求 liquid_liters/mass_kg/slot_count，并要求 quantity_contents 与 contained_object_ids，见 [world-object-rules.md (line 724)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/world-object-rules.md:724) 和 [world-object-rules.md (line 2070)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/world-object-rules.md:2070)。但实际 container-catalog.json 仍使用 {amount, unit} 和 contents，见 [container-catalog.json (line 13)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/05-content-packs/catalogs/container-catalog.json:13) 和 [container-catalog.json (line 119)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/05-content-packs/catalogs/container-catalog.json:119)。

实现后果：当前容器 catalog 无法通过新版 WorldObject 物化。解决条件：实际 catalog 全部迁到多维 capacity 和两个内容数组，或定义版本化迁移。

## 6. catalog 条目字段名与 materializer 合并规则不一致

条目级 default_tags/default_affordances 是 catalog 条目默认标签/动作，见 [world-object-rules.md (line 495)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/world-object-rules.md:495)。但实例化合并步骤写的是 entry 的 tags/affordances，见 [world-object-rules.md (line 501)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/world-object-rules.md:501) 和 [world-object-rules.md (line 736)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/world-object-rules.md:736)。通用 materializer 也只把 tags/affordances 列为 set 合并字段，unknown path 拒绝，见 [content-pack-materialization-rules.md (line 243)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/05-content-packs/content-pack-materialization-rules.md:243)。

实现后果：实际 catalog 的 default_tags 可能被忽略或拒绝。解决条件：统一字段名，或明确 default_tags/default_affordances -> WorldObject.tags/affordances 的物化映射。

## 7. WorldObject 派生重量/容量字段的写者冲突

derived.total_weight_kg/contained_mass_kg/occupied_* 是派生字段。WorldObject 规则说 WeightDeriver 和 ContainerOccupancyDeriver 是唯一写者，见 [world-object-rules.md (line 966)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/world-object-rules.md:966)。但 WriteACL 又允许 ContainmentTransferResolver 和 QuantityTransferResolver 写 derived.*，见 [world-collection-influence-rules.md (line 541)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/00-architecture/world-collection-influence-rules.md:541)。

实现后果：同一转移事务里，derived 字段到底由 resolver 写还是 deriver 写不明确。解决条件：要么移除 resolver 的 derived.* 写权，让它只调用 deriver；要么定义 resolver 输出中的 derived 必须带 deriver 子证明和 provenance。

## 8. 玩家发现状态被写进世界事实

WorldObject.visibility 当前被定义为“玩家当前可见性”，含 discovered，见 [world-object-rules.md (line 800)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/world-object-rules.md:800)；observe 还会修改它，见 [world-object-rules.md (line 1971)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/world-object-rules.md:1971)。但知识层规定“谁知道/谁发现”必须写 DiscoveryState/KnowledgeState，不能写入 WorldObject 等世界事实，见 [world-collection-influence-rules.md (line 427)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/00-architecture/world-collection-influence-rules.md:427) 和 [world-knowledge-rules.md (line 528)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/03-runtime/world-knowledge-rules.md:528)。

实现后果：一个主体发现对象后会污染全局世界事实，破坏多主体知识裁剪。解决条件：把客观遮蔽/可观察属性留在世界事实，把主体发现状态迁到 DiscoveryState/KnowledgeState。

## 9. 运行时有效期时间坐标不一致

GameTimeInterval 是运行时有效期的统一结构，使用 start_world_minute/end_world_minute，见 [static-world-runtime-rules.md (line 117)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/03-runtime/static-world-runtime-rules.md:117)；clock.absolute_minute 是唯一过期坐标，见 [static-world-runtime-rules.md (line 897)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/03-runtime/static-world-runtime-rules.md:897)。但 ServiceEntitlementState.valid_from/valid_until 仍用 {day, minute_of_day}，见 [settlement-social-world-rules.md (line 667)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/settlement-social-world-rules.md:667)；AI proposal 也用 valid_until_game_time，见 [ai-social-mind-rules.md (line 455)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/04-ai-simulation/ai-social-mind-rules.md:455)。

实现后果：过期判断会出现多套转换规则。解决条件：运行时有效期统一改为 GameTimeInterval 或至少 canonical world minute 字段。

## 10. 世界模型引用了未注册的 EventLog event_type

event_type 是事件日志类型闭集，runtime 注册了 ObjectMoved/ObjectStateChanged/DiscoveryCreated 等，见 [static-world-runtime-rules.md (line 1725)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/03-runtime/static-world-runtime-rules.md:1725)。但 WorldObject 和空间规则引用 ObjectRevealedEvent/ObjectEquippedEvent/SearchResolvedEvent/SiteRevealedEvent 等未注册名称，见 [world-object-rules.md (line 1971)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/world-object-rules.md:1971) 和 [location-space-rules.md (line 2197)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/location-space-rules.md:2197)。

实现后果：按动作文档生成事件会被 StateTransitionValidator 拒绝。解决条件：统一事件名，要么补进 runtime 闭集，要么把 02 文档映射到已注册 event_type。

## 11. climate-terrain-formation-rules.md 的 base_fields 示例仍使用 JSON number

climate-terrain-formation-rules.md 里的 base_fields 示例仍用 JSON number，不符合 normalized_milli 三位小数字符串要求，见 [climate-terrain-formation-rules.md (line 348)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/climate-terrain-formation-rules.md:348)。

## 12. WorldChunk.terrain.water_presence 与 FieldOwnership 路径不一致

WorldChunk.terrain.water_presence 与 FieldOwnership 中顶层 water_presence/hydrology 路径不一致，见 [world-collection-influence-rules.md (line 341)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/00-architecture/world-collection-influence-rules.md:341) 和 [climate-terrain-formation-rules.md (line 487)](/Users/fanglinfeng/project/DND-Agent/docs/superpowers/specs/isekai-world-foundation/02-world-model/climate-terrain-formation-rules.md:487)。
