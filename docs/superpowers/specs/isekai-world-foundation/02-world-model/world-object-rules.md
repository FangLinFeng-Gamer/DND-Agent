---
doc_id: isekai.world_object_rules
status: active
layer: world-model
owner: architecture
created_at: 2026-07-10
updated_at: 2026-07-18
depends_on:
  - isekai.field_domain_registry_rules
  - isekai.location_space_rules
provides:
  - WorldObject
  - object_type
  - object_components
  - WorldObjectValidator
  - ContainmentTransferResolver
  - QuantityTransferResolver
  - WeightDeriver
  - ContainerOccupancyDeriver
---

# 异世界模式 WorldObject 规则设计

## 背景

地点/空间规则已经确定：外部世界用 `WorldChunk` 表示，进入具体地点后使用 `Site -> LocationNode -> Zone`，所有对象通过位置链挂在 chunk、zone、其他对象、角色或玩家物品栏上。

下一步需要统一世界中的非生命对象。水壶、铠甲、战斧、肖像画、柜台、门、捕兽夹、货箱、井、告示牌、钥匙、货币都不能只存在于 DM 文本里，也不能靠具体名称硬编码规则。

本设计将非生命对象统一定义为 `WorldObject`。`WorldObject` 是可被描述、观察、移动、拾取、购买、装备、打开、破坏、修理、阅读、消耗或作为空间锚点引用的权威对象。

## 目标

- 建立所有非生命对象共用的最小 schema。
- 让对象必须有稳定 ID、类型、位置、可见性、物理属性、所有权、可尝试动作和生命周期字段。
- 让对象能力由 `object_type + components + affordances + resolver` 决定，而不是由具体中文名称决定。
- 让 DM 旁白、UI 可互动列表和动作目标绑定都引用已落库 `WorldObject`。
- 支持水壶、铠甲、战斧、肖像画这类内容扩展，而不新增后端硬编码分支。

## 非目标

- 不一次性实现完整装备、战斗、工艺、经济、制造系统。
- 不按具体物品名建立类型，例如不允许 `red_kettle`、`wolf_axe`、`old_portrait` 作为 `object_type`。
- 不让 LLM 直接发放最终物品、扣钱、装备角色或修改资源。
- 不提供制作、合成、配方和打造能力。
- 不把所有可想象物品属性塞进基础 schema。特殊能力通过 components 扩展。
- 不替代地点/空间规则；对象位置必须遵守地点/空间规则文档。

## 核心原则

### 1. 对象必须是真实状态

DM 最终旁白中出现的当前可见主要非生命对象，必须已经存在于 `WorldObject` 状态，或在同轮通过 validator 写入状态。

### 2. 对象类型是规则语义，不是内容名称

`object_type` 只表达稳定规则语义。新增“缺口战斧”“褪色肖像画”“蓝盐水壶”这类内容时，不得新增类型；它们应由 `name`、`aliases`、`tags`、`description` 和 components 表达。

`WorldObject` 禁止使用 `type` 字段。`type` 保留给地点/空间结构，例如 Region、Site、LocationNode、Zone；对象一律使用 `object_type`，避免门、容器、食物等对象被误当成空间节点。

### 3. 位置是权威字段

所有 `WorldObject` 必须有 `placement`。对象不允许只靠 DM 文本、UI 文案或父级字符串表达位置。

### 4. affordance 是可尝试动作，不是成功承诺

`affordances` 表示玩家可以合理尝试的动作。真正成功、失败、耗时、风险和状态变化，由 deterministic resolver 决定。

### 5. 特殊能力走组件

基础 schema 只放所有对象都需要的字段。容器、装备、武器、护甲、钥匙、陷阱、文档、艺术品、光源等能力使用组件扩展。

## P0 最小 Schema

P0 必填字段：

```json
{
  "id": "water_kettle_01",
  "name": "凹陷水壶",
  "object_type": "container",
  "placement": {
    "kind": "zone",
    "node_id": "hunter_cabin_inside",
    "zone_id": "old_stove",
    "local_position": "beside_stove"
  },
  "visibility": "visible",
  "physical": {
    "size": "small",
    "tare_weight_kg": "0.800",
    "portable": true,
    "condition": "worn",
    "materials": ["iron"],
    "traits": ["rust_prone", "water_container"]
  },
  "components": {
    "container": {
      "capacity": {
        "liquid_liters": "1.500",
        "mass_kg": "8.000",
        "slot_count": 2
      },
      "quantity_contents": [],
      "contained_object_ids": []
    }
  },
  "derived": {
    "contained_mass_kg": "0.000",
    "occupied_liquid_liters": "0.000",
    "occupied_slot_count": 0,
    "total_weight_kg": "0.800"
  },
  "affordances": ["observe", "take", "drink", "refill_water"],
  "state": {},
  "created_turn": 0,
  "updated_turn": 0
}
```

P0 推荐字段：

```json
{
  "aliases": ["水壶", "壶"],
  "description": "壶身被撞凹，壶嘴有干涸的水垢。",
  "ownership": {
    "owner_id": null,
    "legal_status": "abandoned"
  },
  "tags": ["water_container", "metal"],
  "provenance": {
    "source_kind": "content_pack",
    "content_pack_id": "isekai_containers_p0",
    "content_pack_version": "2026-07-18.1",
    "catalog_kind": "container_catalog",
    "catalog_id": "container_dented_kettle",
    "catalog_version": "2026-07-18.1",
    "materializer_id": "ContainerMaterializer",
    "materializer_version": "2026-07-18.1",
    "materialization_id": "mat_water_kettle_01",
    "instance_key": "hunter_cabin_inside/old_stove/water_kettle_01",
    "schema_version": "world_object@2026-07-18",
    "registry_hash": "sha256:registry_hash",
    "rule_bundle_hash": "sha256:rule_bundle_hash",
    "content_pack_hash": "sha256:content_pack_hash",
    "catalog_entry_hash": "sha256:catalog_entry_hash"
  }
}
```

完整 P0 示例：

```json
{
  "id": "water_kettle_01",
  "name": "凹陷水壶",
  "aliases": ["水壶", "壶"],
  "description": "壶身被撞凹，壶嘴有干涸的水垢。",
  "object_type": "container",
  "placement": {
    "kind": "zone",
    "node_id": "hunter_cabin_inside",
    "zone_id": "old_stove",
    "local_position": "beside_stove"
  },
  "visibility": "visible",
  "physical": {
    "size": "small",
    "tare_weight_kg": "0.800",
    "portable": true,
    "condition": "worn",
    "materials": ["iron"],
    "traits": ["rust_prone", "water_container"]
  },
  "ownership": {
    "owner_id": null,
    "legal_status": "abandoned"
  },
  "components": {
    "container": {
      "capacity": {
        "liquid_liters": "1.500",
        "mass_kg": "8.000",
        "slot_count": 2
      },
      "quantity_contents": [],
      "contained_object_ids": []
    }
  },
  "derived": {
    "contained_mass_kg": "0.000",
    "occupied_liquid_liters": "0.000",
    "occupied_slot_count": 0,
    "total_weight_kg": "0.800"
  },
  "affordances": ["observe", "take", "drink", "refill_water"],
  "state": {
    "opened": true
  },
  "tags": ["water_container", "metal"],
  "provenance": {
    "source_kind": "content_pack",
    "content_pack_id": "isekai_containers_p0",
    "content_pack_version": "2026-07-18.1",
    "catalog_kind": "container_catalog",
    "catalog_id": "container_dented_kettle",
    "catalog_version": "2026-07-18.1",
    "materializer_id": "ContainerMaterializer",
    "materializer_version": "2026-07-18.1",
    "materialization_id": "mat_water_kettle_01",
    "instance_key": "hunter_cabin_inside/old_stove/water_kettle_01",
    "schema_version": "world_object@2026-07-18",
    "registry_hash": "sha256:registry_hash",
    "rule_bundle_hash": "sha256:rule_bundle_hash",
    "content_pack_hash": "sha256:content_pack_hash",
    "catalog_entry_hash": "sha256:catalog_entry_hash"
  },
  "created_turn": 0,
  "updated_turn": 0
}
```

## 字段定义

### id

稳定唯一 ID，不依赖对象中文名称。对象被改名或本地化后，`id` 不变。

```json
{
  "id": "battle_axe_01"
}
```

### name

玩家可见名称。

```json
{
  "name": "缺口战斧"
}
```

### aliases

用于玩家自然语言目标绑定。可为空数组。

```json
{
  "aliases": ["战斧", "斧头", "旧斧"]
}
```

### description

短描述，用于 DM 叙事和观察反馈。描述不能包含未经落库的其他当前可互动对象。

```json
{
  "description": "斧刃有两处缺口，木柄缠着旧皮条。"
}
```

### object_type

抽象对象类型。P0 允许类型：

```text
item
weapon
armor
tool
container
resource
food
water_source
furniture
fixture
portal
clue
document
artwork
trap
mechanism
currency
key
vehicle
material
light_source
```

类型扩展规则：

```text
只有新增规则语义时才能扩展 object_type。
新增具体内容名时不得扩展 object_type。
```

### object_type 分类表

`object_type` 是规则类型闭集。它只回答“这个对象主要按哪套规则结算”，不回答具体内容名字。

| object_type | 含义 | 示例 | 默认 affordances | 推荐 components |
| --- | --- | --- | --- | --- |
| item | 通用小物件，没有特殊规则语义时使用 | 石子、布条、碎陶片 | observe, take, search | none |
| weapon | 武器，可装备或用于攻击 | 战斧、匕首、猎弓、长矛 | observe, take, equip, attack, repair | weapon_stats |
| armor | 护甲或防具 | 锁子甲、皮甲、头盔、盾牌 | observe, take, equip, repair | armor_stats |
| tool | 工具，用于修理、撬开、攀爬等动作 | 锤子、撬棍、绳索、火镰、铲子 | observe, take, repair, move | tool_profile |
| container | 容器，可承载内容 | 水壶、木箱、背包、袋子、柜子、桶 | observe, open, close, search, take | container |
| resource | 可采集或消耗的资源 | 干柴、草药束、兽皮、盐块 | observe, take, gather, use | resource_profile |
| food | 食物 | 干粮、炖菜、浆果、肉干 | observe, take, eat, purchase | consumable |
| water_source | 水源或补水对象 | 井、溪流、泉眼、蓄水池 | observe, drink, refill_water | water_profile |
| furniture | 家具，通常不可携带 | 床、桌子、椅子、柜子 | observe, search, move, hide_behind | furniture_profile |
| fixture | 固定物或空间锚点 | 柜台、墙、炉灶、栏杆、木桩 | observe, search, repair | fixture_profile |
| portal | 连接空间的对象 | 门、楼梯、地窖口、车厢破口、桥 | observe, enter, leave, open, close | portal_profile |
| clue | 线索对象 | 血迹、脚印、爪痕、符号、异常气味 | observe, search, track | clue_profile |
| document | 可读文本 | 信件、地图、账本、告示、契约、书页 | observe, read, take, search | document_profile |
| artwork | 艺术或装饰物 | 肖像画、雕像、挂毯、纹章 | observe, search, take | art_profile |
| trap | 陷阱或危险装置 | 捕兽夹、绊索、落石机关、毒针匣 | observe, disarm, trigger, avoid | trap_profile |
| mechanism | 机关或机械设施 | 锁、杠杆、绞盘、升降机、闸门机构 | observe, open, close, repair, break | mechanism_profile |
| currency | 货币 | 金币、银币、铜币、代币 | observe, take, trade, purchase | currency_value |
| key | 钥匙或凭证 | 房间钥匙、铜牌、通行令、印章 | observe, take, unlock, trade | key_profile |
| vehicle | 载具或大型运输物 | 马车、小船、雪橇、手推车 | observe, enter, search, move, repair | vehicle_profile |
| material | 材料；本版只用于交易、叙事或未来预留，不参与制作结算 | 铁锭、布料、木板、皮革、药粉 | observe, take, use, trade | material_profile |
| light_source | 光源 | 火把、油灯、蜡烛、发光石 | observe, take, use, repair | light_profile |

分类原则：

```text
一个对象只能有一个 primary object_type。
如果一个对象同时像多类，选择对结算最重要的一类。
额外身份用 tags 或 components 表达。
```

示例：

```text
水壶：object_type=container，tags=[water_container]，components.container。
战斧：object_type=weapon，components.weapon_stats。
锁子甲：object_type=armor，components.armor_stats。
肖像画：object_type=artwork，components.art_profile。
柜台：object_type=fixture，components.fixture_profile。
门：object_type=portal，components.portal_profile。
捕兽夹：object_type=trap，components.trap_profile。
井：object_type=water_source，components.water_profile。
木箱：object_type=container，components.container。
地图：object_type=document，components.document_profile。
金币：object_type=currency，components.currency_value。
```

禁止新增的类型示例：

```text
kettle
axe
portrait
inn_door
wolf_claw_mark
magic_sword
```

这些内容必须通过 `name`、`aliases`、`tags`、`description` 和 components 表达。

### 通用小物件 Catalog

`generic_item_catalog` 是内容包里的通用小物件目录，用于世界生成。它不是运行时对象，不参与玩家交互，不改变 `WorldObject` 基础结构。

P0 catalog 草案文件：

- [generic-item-catalog.json](../05-content-packs/catalogs/generic-item-catalog.json)

```text
generic_item_catalog entry
-> WorldObject(object_type=item) instance
```

运行时真实物品仍然必须是 `WorldObject`。catalog 只提供一致的默认名称、别名、描述、物理属性、默认 affordances 和 tags。

Catalog 存放位置：

```json
{
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

Catalog 条目 schema：

```json
{
  "catalog_id": "generic_bent_nail",
  "name": "弯曲钉子",
  "aliases": ["弯钉", "钉子", "旧钉子"],
  "description": "一枚弯曲的旧钉子，钉身有些发黑。",
  "object_type": "item",
  "category": "metal_small",
  "physical_override": {
    "weight_kg": 0.02,
    "condition": "worn"
  },
  "default_affordances": ["observe", "take", "search"],
  "default_tags": ["small_item", "metal", "scrap"]
}
```

Category 默认属性：

```json
{
  "natural": {
    "physical": { "size": "tiny", "weight_kg": 0.03, "portable": true, "condition": "worn" },
    "affordances": ["observe", "take", "search"],
    "tags": ["small_item", "natural"]
  },
  "waste": {
    "physical": { "size": "tiny", "weight_kg": 0.04, "portable": true, "condition": "damaged" },
    "affordances": ["observe", "take", "search"],
    "tags": ["small_item", "debris"]
  },
  "domestic": {
    "physical": { "size": "tiny", "weight_kg": 0.03, "portable": true, "condition": "worn" },
    "affordances": ["observe", "take", "search"],
    "tags": ["small_item", "domestic"]
  },
  "cloth": {
    "physical": { "size": "tiny", "weight_kg": 0.02, "portable": true, "condition": "worn" },
    "affordances": ["observe", "take", "search"],
    "tags": ["small_item", "cloth"]
  },
  "animal_remain": {
    "physical": { "size": "tiny", "weight_kg": 0.02, "portable": true, "condition": "worn" },
    "affordances": ["observe", "take", "search"],
    "tags": ["small_item", "animal_remain"]
  },
  "metal_small": {
    "physical": { "size": "tiny", "weight_kg": 0.04, "portable": true, "condition": "worn" },
    "affordances": ["observe", "take", "search"],
    "tags": ["small_item", "metal"]
  },
  "wooden": {
    "physical": { "size": "small", "weight_kg": 0.06, "portable": true, "condition": "worn" },
    "affordances": ["observe", "take", "search"],
    "tags": ["small_item", "wood"]
  },
  "ceramic_glass": {
    "physical": { "size": "tiny", "weight_kg": 0.04, "portable": true, "condition": "damaged" },
    "affordances": ["observe", "take", "search"],
    "tags": ["small_item", "shard"]
  },
  "mark_symbol": {
    "physical": { "size": "tiny", "weight_kg": 0.03, "portable": true, "condition": "worn" },
    "affordances": ["observe", "take", "search"],
    "tags": ["small_item", "mark"]
  },
  "suspicious_trace": {
    "physical": { "size": "tiny", "weight_kg": 0.02, "portable": true, "condition": "damaged" },
    "affordances": ["observe", "take", "search"],
    "tags": ["small_item", "suspicious_trace"]
  },
  "trade_trinket": {
    "physical": { "size": "tiny", "weight_kg": 0.02, "portable": true, "condition": "worn" },
    "affordances": ["observe", "take", "search", "trade"],
    "tags": ["small_item", "trinket"]
  }
}
```

Catalog 字段说明：

| 字段 | 含义 |
| --- | --- |
| `content_pack_id` | 提供该 catalog 的内容包 ID。 |
| `content_pack_version` | 提供该 catalog 的内容包版本。任何影响物化结果的修改都必须递增。 |
| `kind` | catalog 类型，通用小物件为 `generic_item_catalog`。 |
| `catalog_version` | catalog 内容版本。任何 entry 或 category default 变更都必须递增。 |
| `generic_item_catalog` | 通用小物件 catalog 根对象。 |
| `generic_item_catalog.category_defaults` | 按 category 存放的默认属性表。 |
| `generic_item_catalog.entries` | catalog 条目列表。 |
| `catalog_id` | catalog 条目 ID。实例化后不能直接作为 WorldObject.id，生成器必须生成实例 ID。 |
| `name` | 条目默认显示名。 |
| `aliases` | 条目默认别名，用于玩家目标绑定。 |
| `description` | 条目默认描述。 |
| `object_type` | 条目实例化后的 WorldObject 类型。通用小物件只能是 `item`。 |
| `category` | 条目所属 category，用于合并 `category_defaults`。 |
| `physical_override` | 条目对 category 默认物理属性的覆盖。 |
| `default_affordances` | 条目默认可尝试动作。 |
| `default_tags` | 条目默认标签。 |
| `category_defaults.*.physical` | 某类通用小物件的默认物理属性。 |
| `category_defaults.*.affordances` | 某类通用小物件的默认动作能力。 |
| `category_defaults.*.tags` | 某类通用小物件的默认标签。 |

实例化为 `WorldObject` 时，世界生成器必须合并：

```text
category_defaults
-> catalog entry physical_override / tags / affordances
-> placement / visibility / ownership / turns
```

实例化结果示例：

```json
{
  "id": "item_bent_nail_001",
  "name": "弯曲钉子",
  "aliases": ["弯钉", "钉子", "旧钉子"],
  "description": "一枚弯曲的旧钉子，钉身有些发黑。",
  "object_type": "item",
  "placement": {
    "kind": "zone",
    "node_id": "hunter_cabin_inside",
    "zone_id": "dark_corner"
  },
  "visibility": "visible",
  "physical": {
    "size": "tiny",
    "weight_kg": 0.02,
    "portable": true,
    "condition": "worn"
  },
  "ownership": {
    "owner_id": null,
    "legal_status": "abandoned"
  },
  "affordances": ["observe", "take", "search"],
  "components": {},
  "state": {},
  "tags": ["small_item", "metal", "scrap"],
  "provenance": {
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
  },
  "created_turn": 0,
  "updated_turn": 0
}
```

Catalog 硬规则：

```text
Catalog 只允许 object_type=item。
Catalog 不允许定义 components。
Catalog 不允许定义扩展能力字段、制作字段、合成字段或配方字段。
Catalog 的 default_affordances 只能从 observe、take、search、trade 中选择。
Catalog 实例化后的 WorldObject 必须保持 object_type=item。
Catalog 实例化后的 WorldObject 必须保持 components={}。
Catalog 实例化后的 WorldObject 不能新增 catalog 未允许的 affordance。
通用小物件不直接改变核心生存数值。
通用小物件不直接推进 quest_stage。
通用小物件不直接解锁地点或发放关键奖励。
如果小物件需要以上能力，必须升级为 clue、tool、key、weapon、document、resource、food、water_source 等正式 object_type。
```

P0 catalog entries：

| catalog_id | name | aliases | description | category | physical_override | tags |
| --- | --- | --- | --- | --- | --- | --- |
| generic_pebble | 石子 | 石头, 小石子 | 一颗普通石子，边缘被磨得发圆。 | natural | weight_kg=0.03 | stone |
| generic_flat_stone | 扁平石片 | 石片, 扁石 | 一片扁平石片，表面有水磨痕迹。 | natural | size=small, weight_kg=0.12 | stone |
| generic_sharp_flint | 尖锐燧石 | 燧石, 尖石片 | 一块边缘锋利的燧石，握起来有些硌手。 | natural | size=small, weight_kg=0.08 | stone, sharp |
| generic_dry_twig | 干树枝 | 树枝, 枯枝 | 一截干树枝，轻轻一折就会断。 | natural | size=small, weight_kg=0.05 | wood |
| generic_pine_cone | 松果 | 干松果 | 一个干松果，鳞片间夹着灰尘。 | natural | weight_kg=0.03 | forest |
| generic_dead_leaf_clump | 枯叶团 | 枯叶, 叶团 | 一团发脆的枯叶，散着潮土味。 | natural | weight_kg=0.02 | leaves |
| generic_mud_clod | 泥块 | 干泥块, 泥团 | 一块半干的泥团，表面粘着草屑。 | natural | size=small, weight_kg=0.15 | earth |
| generic_shell | 贝壳 | 小贝壳 | 一枚暗淡贝壳，边缘缺了一角。 | trade_trinket | weight_kg=0.02 | natural |
| generic_feather | 羽毛 | 鸟羽, 干净羽毛 | 一根细长羽毛，羽轴还算完整。 | trade_trinket | weight_kg=0.01 | animal_trace |
| generic_animal_fur_clump | 兽毛团 | 毛团, 兽毛 | 一小团粗硬兽毛，颜色发灰。 | natural | weight_kg=0.01 | animal_trace |
| generic_pottery_shard | 碎陶片 | 陶片, 破陶片 | 一片粗陶碎片，断口还留着黑灰。 | waste | weight_kg=0.04 | ceramic |
| generic_bottle_cork | 破瓶塞 | 瓶塞, 旧瓶塞 | 一个破损瓶塞，闻起来有陈酒味。 | waste | weight_kg=0.01 | cork |
| generic_empty_vial | 空小瓶 | 小瓶, 空瓶 | 一只空小瓶，瓶口有细裂纹。 | waste | size=small, weight_kg=0.08 | glass |
| generic_wax_stub | 断蜡块 | 蜡块, 蜡头 | 一小截断蜡，芯线已经烧黑。 | waste | weight_kg=0.03 | wax |
| generic_crumpled_paper | 旧纸团 | 纸团, 废纸 | 一团皱巴巴的旧纸，字迹已经糊开。 | waste | weight_kg=0.01 | paper |
| generic_charred_wood_chip | 烧焦木片 | 焦木片, 黑木片 | 一片烧焦木片，指尖一碰就掉黑灰。 | waste | weight_kg=0.02 | wood, burned |
| generic_torn_leather_thong | 破皮绳 | 皮绳, 断皮绳 | 一截断开的皮绳，边缘被磨得发毛。 | waste | weight_kg=0.03 | leather |
| generic_broken_arrow_shaft | 断箭杆 | 箭杆, 断箭 | 半截箭杆，尾羽已经脱落。 | waste | size=small, weight_kg=0.06 | wood, arrow_debris |
| generic_bent_nail | 弯曲钉子 | 弯钉, 钉子, 旧钉子 | 一枚弯曲的旧钉子，钉身有些发黑。 | metal_small | weight_kg=0.02 | scrap |
| generic_rusty_metal_shard | 生锈铁片 | 铁片, 锈铁片 | 一小片生锈铁片，边缘钝而参差。 | metal_small | weight_kg=0.05, condition=damaged | scrap |
| generic_old_button | 旧纽扣 | 纽扣, 破纽扣 | 一枚旧纽扣，孔眼里嵌着灰尘。 | domestic | weight_kg=0.01 | clothing |
| generic_copper_button | 铜扣 | 小铜扣, 铜纽扣 | 一枚发暗铜扣，边缘还有浅浅花纹。 | trade_trinket | weight_kg=0.02 | metal |
| generic_comb_tooth | 木梳齿 | 梳齿, 断梳齿 | 一截断掉的木梳齿，表面被磨得光滑。 | domestic | weight_kg=0.01 | wood |
| generic_pipe_mouthpiece | 破烟斗嘴 | 烟斗嘴, 斗嘴 | 一个破烟斗嘴，咬痕很深。 | domestic | weight_kg=0.03, condition=damaged | personal |
| generic_small_cloth_pouch | 小布包 | 布包, 空布包 | 一个空小布包，束口绳已经松了。 | domestic | size=small, weight_kg=0.04 | cloth |
| generic_empty_spool | 空线轴 | 线轴, 木线轴 | 一个空线轴，木芯上还残着几圈细线。 | domestic | weight_kg=0.02 | wood |
| generic_needle_case | 针盒 | 空针盒, 旧针盒 | 一个小针盒，盖子有点松。 | domestic | weight_kg=0.03 | sewing |
| generic_bone_die | 骨骰子 | 骰子, 旧骰子 | 一枚骨骰子，点数刻得并不规整。 | trade_trinket | weight_kg=0.02 | bone |
| generic_wooden_cup | 木杯 | 旧木杯, 杯子 | 一个旧木杯，杯沿裂开一道细口。 | domestic | size=small, weight_kg=0.10, condition=damaged | wood |
| generic_cracked_spoon | 裂开的勺子 | 勺子, 破勺子 | 一把裂开的旧勺子，柄端被火燎黑。 | domestic | size=small, weight_kg=0.06, condition=damaged | utensil |
| generic_torn_cloth_strip | 破布条 | 布条, 破布 | 一条脏破布条，边缘起了毛。 | cloth | weight_kg=0.02 | scrap |
| generic_bloodstained_cloth | 染血布片 | 血布, 带血布片 | 一块染血布片，血迹已经发暗。 | suspicious_trace | weight_kg=0.02 | cloth, blood |
| generic_coarse_thread | 粗麻线 | 麻线, 粗线 | 几缕粗麻线，缠成一个小结。 | cloth | weight_kg=0.01 | thread |
| generic_leather_offcut | 皮革边角 | 皮革碎片, 皮边角 | 一小块皮革边角，边缘参差。 | cloth | weight_kg=0.03 | leather |
| generic_old_glove | 旧手套 | 手套, 破手套 | 一只旧手套，指尖已经磨穿。 | cloth | size=small, weight_kg=0.06, condition=damaged | clothing |
| generic_torn_cloak_corner | 撕裂斗篷角 | 斗篷角, 破斗篷布 | 一角撕裂的厚布，像是从斗篷上扯下来的。 | cloth | size=small, weight_kg=0.05, condition=damaged | clothing |
| generic_shoelace | 鞋带 | 旧鞋带 | 一根旧鞋带，末端已经散开。 | cloth | weight_kg=0.01 | cord |
| generic_sewing_needle | 缝补针 | 针, 细针 | 一根缝补针，针尖略微发钝。 | metal_small | weight_kg=0.01 | sewing |
| generic_wool_thread_ball | 羊毛线团 | 线团, 毛线团 | 一小团羊毛线，混着草屑。 | cloth | weight_kg=0.02 | wool |
| generic_small_bone_chip | 小骨片 | 骨片, 碎骨 | 一小块骨片，断面已经发黄。 | animal_remain | weight_kg=0.02 | bone |
| generic_animal_tooth | 兽牙 | 牙, 小兽牙 | 一枚小兽牙，根部还带着干硬污垢。 | trade_trinket | weight_kg=0.02 | bone |
| generic_bird_bone | 鸟骨 | 细鸟骨 | 一根细鸟骨，轻得几乎没有分量。 | animal_remain | weight_kg=0.01 | bone |
| generic_fishbone | 鱼刺 | 细鱼刺 | 几根细鱼刺，已经干硬发白。 | animal_remain | weight_kg=0.01 | bone |
| generic_dried_skin_flake | 干硬皮屑 | 皮屑, 干皮片 | 一片干硬皮屑，边缘卷曲。 | animal_remain | weight_kg=0.01 | hide |
| generic_broken_horn_piece | 断角片 | 角片, 断角 | 一小片断角，表面有细密纹路。 | trade_trinket | weight_kg=0.04 | horn |
| generic_claw_shell | 爪壳 | 爪片, 兽爪壳 | 一片脱落的爪壳，尖端还很硬。 | animal_remain | weight_kg=0.01 | claw |
| generic_insect_shell | 虫壳 | 空虫壳 | 一枚空虫壳，背部泛着暗光。 | animal_remain | weight_kg=0.01 | insect |
| generic_quill_stem | 羽梗 | 羽轴, 羽梗 | 一截断掉的羽梗，中空而脆。 | animal_remain | weight_kg=0.01, condition=damaged | feather |
| generic_iron_ring | 铁环 | 小铁环, 锈铁环 | 一个小铁环，内侧有磨损痕。 | metal_small | weight_kg=0.04 | scrap |
| generic_copper_wire | 铜线 | 细铜线 | 一小截铜线，被拧得有些变形。 | trade_trinket | weight_kg=0.01 | metal |
| generic_rusty_buckle | 生锈扣环 | 扣环, 锈扣 | 一个生锈扣环，扣舌已经卡住。 | metal_small | weight_kg=0.05, condition=damaged | clothing |
| generic_broken_chain_link | 断链节 | 链节, 断铁链节 | 一枚断开的链节，裂口很旧。 | metal_small | weight_kg=0.06, condition=damaged | scrap |
| generic_rivet | 铆钉 | 小铆钉 | 一枚脱落铆钉，帽面被磨平。 | metal_small | weight_kg=0.02 | scrap |
| generic_broken_bell | 破铃铛 | 铃铛, 坏铃铛 | 一个破铃铛，摇起来只有哑声。 | trade_trinket | weight_kg=0.06, condition=damaged | metal |
| generic_bad_pin | 坏扣针 | 扣针, 断扣针 | 一枚坏扣针，针脚已经歪了。 | metal_small | weight_kg=0.01, condition=damaged | clothing |
| generic_wooden_wedge | 木楔 | 楔子, 小木楔 | 一枚粗糙木楔，尖端有压痕。 | wooden | weight_kg=0.08 | wedge |
| generic_short_wood_chip | 短木片 | 木片, 碎木片 | 一截短木片，断口粗糙。 | wooden | weight_kg=0.06, condition=damaged | scrap |
| generic_notched_wood_tag | 刻痕木牌 | 木牌, 刻痕牌 | 一块带刻痕的小木牌，纹路像是人为划出的。 | wooden | weight_kg=0.05 | mark |
| generic_broken_wooden_handle | 断木柄 | 木柄, 断柄 | 一截断掉的木柄，握痕还在。 | wooden | weight_kg=0.12, condition=damaged | handle |
| generic_wooden_bead | 小木珠 | 木珠 | 一颗小木珠，表面被磨得发亮。 | trade_trinket | weight_kg=0.01 | wood |
| generic_charred_wooden_peg | 烧焦木钉 | 木钉, 焦木钉 | 一枚烧焦木钉，半边已经碳化。 | wooden | weight_kg=0.02, condition=damaged | burned |
| generic_rough_wooden_plug | 粗糙木塞 | 木塞, 旧木塞 | 一个粗糙木塞，边缘削得不平。 | wooden | weight_kg=0.03 | plug |
| generic_spoon_handle | 木勺柄 | 勺柄, 断勺柄 | 一截木勺柄，尾端有烧痕。 | wooden | weight_kg=0.03, condition=damaged | utensil |
| generic_white_pottery_shard | 白陶碎片 | 白陶片, 陶片 | 一片白陶碎片，釉面已经开裂。 | ceramic_glass | weight_kg=0.04 | ceramic |
| generic_black_glaze_shard | 黑釉陶片 | 黑陶片, 黑釉片 | 一片黑釉陶片，边缘锋利。 | ceramic_glass | weight_kg=0.04 | ceramic |
| generic_cracked_cup_shard | 裂杯片 | 杯片, 破杯片 | 一块裂杯片，还能看出杯沿弧度。 | ceramic_glass | weight_kg=0.05 | ceramic |
| generic_glass_bead | 玻璃珠 | 小玻璃珠, 珠子 | 一颗玻璃珠，里面有一道淡绿气泡。 | trade_trinket | weight_kg=0.01 | glass |
| generic_green_bottle_base | 绿色瓶底 | 瓶底, 绿玻璃底 | 一块绿色瓶底，厚重而浑浊。 | ceramic_glass | size=small, weight_kg=0.10 | glass |
| generic_mirror_shard | 镜片碎片 | 镜片, 破镜片 | 一片镜片碎片，映出的影子被裂纹切开。 | ceramic_glass | weight_kg=0.03 | glass, reflective |
| generic_frosted_glass_piece | 磨砂玻璃片 | 磨砂片, 玻璃片 | 一块磨砂玻璃片，透光但看不清另一侧。 | ceramic_glass | weight_kg=0.04 | glass |
| generic_rune_pebble | 刻符石子 | 符石, 刻字石子 | 一颗刻着浅符号的石子，笔画很旧。 | mark_symbol | weight_kg=0.03 | stone |
| generic_tied_wood_tag | 系绳木牌 | 木牌, 挂牌 | 一块系着短绳的小木牌，牌面被雨水泡花。 | mark_symbol | size=small, weight_kg=0.05 | wood |
| generic_marked_cloth_strip | 带记号布条 | 记号布条, 布条 | 一条带记号的布条，颜料已经褪色。 | mark_symbol | weight_kg=0.02 | cloth |
| generic_painted_wood_chip | 涂漆木片 | 漆木片, 彩木片 | 一块涂漆木片，只剩半块颜色。 | mark_symbol | weight_kg=0.03, condition=damaged | wood |
| generic_notched_bone_chip | 刻痕骨片 | 骨片, 刻痕骨 | 一片带刻痕的骨片，刻线很浅。 | mark_symbol | weight_kg=0.02 | bone |
| generic_old_wax_seal_fragment | 旧封蜡碎块 | 封蜡, 蜡封碎片 | 一块旧封蜡碎片，纹章只剩一角。 | mark_symbol | weight_kg=0.02, condition=damaged | wax |
| generic_scored_stone_chip | 有划线的石片 | 划线石片, 石片 | 一片有划线的石片，像被人刻意记过数。 | mark_symbol | weight_kg=0.03 | stone |
| generic_muddy_shoelace | 带泥鞋带 | 泥鞋带, 鞋带 | 一根带泥鞋带，泥里夹着细草根。 | suspicious_trace | weight_kg=0.01 | clothing |
| generic_black_blood_cloth | 沾黑血的布片 | 黑血布片, 血布 | 一块沾着黑血的布片，血迹带着怪异腥味。 | suspicious_trace | weight_kg=0.02 | cloth, blood |
| generic_odd_smell_feather | 带异味羽毛 | 异味羽毛, 羽毛 | 一根带异味的羽毛，闻起来像潮铁和腐叶。 | suspicious_trace | weight_kg=0.01 | feather |
| generic_chewed_bone_chip | 咬碎骨片 | 咬痕骨片, 碎骨 | 一块咬碎的骨片，齿痕细密。 | suspicious_trace | weight_kg=0.02 | bone |
| generic_burned_charm_paper | 烧焦符纸 | 符纸, 焦符纸 | 一角烧焦符纸，残留的墨线像符号。 | suspicious_trace | weight_kg=0.01 | paper |
| generic_wet_paper_corner | 湿透纸角 | 纸角, 湿纸片 | 一角湿透纸片，纤维快要散开。 | suspicious_trace | weight_kg=0.01, condition=ruined | paper |
| generic_tooth_marked_wood | 带齿痕木片 | 齿痕木片, 木片 | 一块带齿痕木片，咬痕深得不正常。 | suspicious_trace | size=small, weight_kg=0.05 | wood |
| generic_medicinal_smell_pouch | 有药味的小布包 | 药味布包, 小布包 | 一个有药味的小布包，里面已经空了。 | suspicious_trace | size=small, weight_kg=0.03 | cloth |
| generic_tiny_silver_thread | 小银线 | 银线, 细银线 | 一小截细银线，在暗处也有微光。 | trade_trinket | weight_kg=0.01 | metal |
| generic_old_badge_fragment | 旧徽章碎片 | 徽章碎片, 旧徽章 | 一片旧徽章碎片，背面还有断针。 | trade_trinket | weight_kg=0.03, condition=damaged | mark |

### 容器 Catalog

`container_catalog` 是内容包里的容器目录，用于世界生成水囊、背包、木箱、货箱、柜子、桶、抽屉等可承载内容的对象。它不是运行时对象，不改变 `WorldObject` 基础结构。

P0 catalog 草案文件：

- [container-catalog.json](../05-content-packs/catalogs/container-catalog.json)

```text
container_catalog entry
-> WorldObject(object_type=container, components.container) instance
```

Catalog 条目 schema：

```json
{
  "catalog_id": "container_waterskin",
  "name": "皮水囊",
  "aliases": ["水囊", "皮囊", "装水皮囊"],
  "description": "一只旧皮水囊，缝线处有反复补过的痕迹。",
  "object_type": "container",
  "category": "liquid_vessel",
  "physical_override": {
    "tare_weight_kg": "0.250"
  },
  "container_override": {
    "capacity": {
      "liquid_liters": "1.200",
      "mass_kg": "8.000",
      "slot_count": 0
    },
    "quantity_contents": [],
    "contained_object_ids": []
  },
  "default_tags": ["leather", "water_container"]
}
```

Catalog 字段说明：

| 字段 | 含义 |
| --- | --- |
| `content_pack_id` | 提供该 catalog 的内容包 ID。 |
| `content_pack_version` | 提供该 catalog 的内容包版本。任何影响物化结果的修改都必须递增。 |
| `kind` | catalog 类型，容器为 `container_catalog`。 |
| `catalog_version` | catalog 内容版本。任何 entry 或 category default 变更都必须递增。 |
| `container_catalog` | 容器 catalog 根对象。 |
| `catalog_id` | 容器 catalog 条目 ID。实例化时生成器必须转换成独立 WorldObject.id。 |
| `name` | 容器默认显示名。 |
| `aliases` | 容器默认别名。 |
| `description` | 容器默认描述。 |
| `object_type` | 条目实例化后的 WorldObject 类型。容器 catalog 只能是 `container`。 |
| `category` | 容器所属 category，用于合并容器默认值。 |
| `physical_override` | 条目对默认物理属性的覆盖。 |
| `container_override` | 条目对默认 `components.container` 的覆盖。 |
| `container_override.capacity` | 容器容量。 |
| `container_override.capacity.liquid_liters` | 液体容量，单位 liter。不能装液体的容器省略或为 0。 |
| `container_override.capacity.mass_kg` | 最大内容承重，单位 kg，不包含容器自重。没有承重限制的 P1 容器必须显式声明规则来源，不能省略为无限。 |
| `container_override.capacity.slot_count` | 离散物品槽位数量，整数。不能装离散物品的容器为 0。 |
| `container_override.quantity_contents` | 默认数量资源内容。P1 必须为空数组，具体内容由场景实例、发现表或 resolver 写入。 |
| `container_override.contained_object_ids` | 默认离散子物品列表。Catalog 条目必须为空数组，具体内容由场景实例、发现表或 resolver 写入。 |
| `default_tags` | 容器默认标签。 |

实例化为 `WorldObject` 时，世界生成器必须合并：

```text
category_defaults
-> catalog entry physical_override / container_override / tags / affordances / state
-> placement / visibility / ownership / turns
-> WorldObjectValidator
```

实例化结果必须把容器能力写入 `components.container`：

```json
{
  "object_type": "container",
  "components": {
    "container": {
      "capacity": {
        "liquid_liters": "1.200",
        "mass_kg": "8.000",
        "slot_count": 0
      },
      "quantity_contents": [],
      "contained_object_ids": []
    }
  }
}
```

Catalog 硬规则：

```text
Catalog 只允许 object_type=container。
Catalog 必须提供 category，并能从 category_defaults 合并出 components.container。
Catalog 的 container_override 只能覆盖 components.container.capacity、components.container.quantity_contents 和 components.container.contained_object_ids。
Catalog 默认 quantity_contents 和 contained_object_ids 必须为空数组；具体装了什么由场景实例、发现表或 resolver 决定。
Catalog 不允许定义 weapon_stats、armor_stats、tool_profile、consumable、currency_value、key_profile 等非容器组件。
Catalog 不允许定义制作字段、合成字段或配方字段。
Catalog 实例化后的 WorldObject 必须保持 object_type=container。
Catalog 实例化后的 WorldObject 必须包含 components.container。
liquid_vessel category 可以默认声明 drink、refill_water、pour；这些 affordance 只表示液体容器可以作为 drink.source、refill_water.target 或 pour.source 被尝试。
liquid_vessel 实例化结果不得添加 water_profile；水囊、水壶、瓶子不是水源。
portable=false 的容器不能被直接拾取到玩家物品栏。
带锁容器的锁具必须由 mechanism/key 规则表达，不能只靠容器名称表达。
```

### placement

权威位置。必须符合地点/空间规则文档的 `ObjectPlacement`。

允许的 `placement.kind`：

```text
chunk
zone
on_object
inside_object
contained_by_parent
under_object
attached_to_object
near_object
carried_by_actor
player_inventory
offscreen
removed
```

`inside_object` 是旧版离散物品包含关系表达。P1-02 后，新写入的离散物品包含关系必须使用父容器 `components.container.contained_object_ids`；被包含的子物品自身只允许使用 `placement.kind=contained_by_parent`，且不得携带父容器 ID。迁移工具可以读取旧 `placement.kind=inside_object` 并转换为父容器记录。新生成、新 resolver 和新内容包不得写入 `inside_object`。

### visibility

玩家当前可见性：

```text
visible：当前能直接看到。
hinted：有线索暗示，但对象未完全确认。
hidden：隐藏，普通投影不显示。
discovered：已被发现，可被玩家指代。
removed：已消失、消耗或销毁。
```

### physical

最小物理属性：

```json
{
  "size": "medium",
  "tare_weight_kg": "3.500",
  "portable": true,
  "condition": "worn",
  "materials": ["iron", "wood"],
  "traits": ["sharp_edge", "breakable"]
}
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `size` | 对象体积等级。影响携带、遮挡、移动和空间投影。 |
| `tare_weight_kg` | 对象空重或皮重，单位 kg。它不包含 `quantity_contents` 和 `contained_object_ids` 中的内容重量。 |
| `portable` | 是否可直接进入携带/背包类位置。 |
| `condition` | 当前完好程度。 |
| `materials` | 对象的主要构成材料。它描述“这个对象由什么构成”。 |
| `traits` | 由材料、结构或状态带来的物理交互倾向。它描述“这个对象大概能怎样互动”。 |

`physical.tare_weight_kg` 是唯一可由内容包、生成器或 resolver 写入的基础重量字段。旧字段 `physical.weight_kg` 不再作为 WorldState 权威字段；迁移时按“旧 weight_kg 表示空重”转换为 `tare_weight_kg`。对象当前总重必须由 `WeightDeriver` 写入 `derived.total_weight_kg`。

`size` 枚举：

```text
tiny
small
medium
large
huge
structure
```

`condition` 枚举：

```text
intact
worn
damaged
broken
ruined
```

`materials` P0 闭集：

```text
wood
iron
steel
bronze
copper
stone
clay
glass
ceramic
cloth
leather
bone
paper
wax
water
food
plant_fiber
organic
crystal
unknown
```

`traits` P0 闭集：

```text
flammable
breakable
brittle
waterproof
absorbent
sharp_edge
blocks_movement
blocks_sight
blocks_sound
anchor_point
heavy
fragile
lockable
rust_prone
rot_prone
poisonous
slippery
insulating
water_container
```

规则：

```text
portable=false 的对象不能直接进入玩家物品栏。
condition=broken 的对象不能执行正常使用类动作，除非 resolver 允许修理、拆解或强行使用。
condition=ruined 的对象不能恢复为正常使用状态，除非专门规则允许。
materials 表示对象构成，不表示这件对象本身就是材料资源。
object_type=material + components.material_profile 表示“这件对象是一份可作为资源处理的材料”。
traits 不是自动成功规则，只是 resolver 判断燃烧、破坏、遮挡、腐蚀、滑倒等交互的输入。
具体能不能点燃、破坏、移动、修理，仍由 affordances、components、placement、HazardSource/ObstacleSource 和 resolver 共同决定。
```

### derived

`derived` 保存可缓存的派生物理值。它是 `WorldObject` 的一部分，不是独立实体。内容包、LLM proposal、DM 文本和通用 patch 接口不能直接写入这些字段。

```json
{
  "derived": {
    "contained_mass_kg": "1.400",
    "occupied_liquid_liters": "1.200",
    "occupied_slot_count": 1,
    "total_weight_kg": "2.200"
  }
}
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `derived.contained_mass_kg` | 当前容器内容总质量，单位 kg。由数量资源质量与离散子物品总重相加得到。 |
| `derived.occupied_liquid_liters` | 当前液体占用，单位 liter。只统计 `quantity_contents` 中 liquid 维度资源。 |
| `derived.occupied_slot_count` | 当前离散物品槽位占用，整数。由 `contained_object_ids` 中每个对象的槽位占用相加得到。 |
| `derived.total_weight_kg` | 当前对象总重，单位 kg。由 `WeightDeriver` 递归计算。 |

总重公式：

```text
derived.total_weight_kg(object)
= physical.tare_weight_kg
+ sum(quantity_contents[].amount * ResourceMassRegistry.mass_per_unit_kg)
+ sum(derived.total_weight_kg(child_object) for child_object_id in components.container.contained_object_ids)
```

占用公式：

```text
derived.occupied_liquid_liters = sum(quantity_contents 中 unit=liter 的 amount)
derived.occupied_slot_count = sum(ObjectSlotRule.slot_cost(child_object))
derived.contained_mass_kg = derived.total_weight_kg - physical.tare_weight_kg
```

规则：

```text
WeightDeriver 是 derived.total_weight_kg 和 derived.contained_mass_kg 的唯一写者。
ContainerOccupancyDeriver 是 derived.occupied_liquid_liters 和 derived.occupied_slot_count 的唯一写者。
内容包和 LLM proposal 不能写 derived。
derived 字段可以缓存，但 validator 必须能从权威内容重算并校验一致。
```

### ownership

所有权和合法状态。P0 推荐必填，允许 `owner_id=null`。

```json
{
  "owner_id": "innkeeper_01",
  "faction_id": "graystone_town",
  "legal_status": "owned"
}
```

`legal_status` 枚举：

```text
owned：有主人，拿走算偷。
for_sale：可购买。
abandoned：废弃，可拿但仍可能有风险。
public：公共物。
quest_locked：任务锁定。
unknown：所有权不明。
```

### affordances

玩家可以合理尝试的动作能力。P0 允许能力：

```text
observe
take
equip
unequip
attack
open
close
lock
unlock
search
read
track
repair
break
move
push
pull
use
gather
drink
eat
refill_water
pour
trade
purchase
hide_behind
avoid
disarm
trigger
enter
leave
```

不在允许集合内的 affordance 必须被 validator 拒绝。Validator 不允许删除未知 affordance 后继续物化，也不允许写入未声明的 `blocked_affordances` 字段。

`affordances` 只表示“玩家可以尝试这个动作”。它不等于“该对象独自满足动作结算所需的所有组件”。动作结算必须按参数角色校验，例如同一个 `refill_water`：

```text
source：水源，必须是 ResourceNode 或带 water_profile 的 WorldObject。
target：盛水容器，必须是带 components.container 且容量单位支持液体的 WorldObject。
```

因此，水囊、水壶、桶可以声明 `refill_water`，因为它们可以作为 `refill_water.target`；它们不需要 `water_profile`。井、溪流、蓄水池可以声明 `refill_water`，因为它们可以作为 `refill_water.source`，并且必须具备 `water_profile` 或对应 ResourceNode 水源事实。

### state

对象当前状态，轻量 key-value。P0 允许常用键：

```text
durability
opened
locked
equipped_by
charges
fuel
amount
quality
```

规则：

```text
state 不能承载位置、所有权和可见性；这些必须写入专用字段。
resolver 可以修改 state，LLM proposal 不能直接提交最终 state 变更。
```

### tags

用于搜索、叙事、规则分类和内容过滤，不参与核心结算。

```json
{
  "tags": ["rusty", "two_handed", "hunter_cabin"]
}
```

### provenance

对象来源证明，用于调试、重放、迁移和存档版本校验。P1 起运行时对象必须使用 `provenance`，不得只写 `source: content_pack`。

```text
source_kind
content_pack_id
content_pack_version
catalog_kind
catalog_id
catalog_version
materializer_id
materializer_version
materialization_id
instance_key
schema_version
registry_hash
rule_bundle_hash
content_pack_hash
catalog_entry_hash
```

完整结构见 [内容包、Catalog 与物化版本规则](../05-content-packs/content-pack-materialization-rules.md) 的 `MaterializationProvenance`。

### created_turn / updated_turn

生命周期追踪。对象创建和每次状态变化后必须更新。

## 组件扩展

基础 schema 不为每种对象加专用字段。特殊能力通过 `components` 扩展。

```json
{
  "components": {
    "container": {},
    "weapon_stats": {},
    "armor_stats": {}
  }
}
```

### container

```json
{
  "components": {
    "container": {
      "capacity": {
        "liquid_liters": "2.000",
        "mass_kg": "8.000",
        "slot_count": 4
      },
      "quantity_contents": [
        {
          "resource_type": "water",
          "amount": "0.400",
          "unit": "liter",
          "quality": "stale"
        }
      ],
      "contained_object_ids": ["key_01"]
    }
  }
}
```

### tool_profile

```json
{
  "components": {
    "tool_profile": {
      "tool_kinds": ["pry", "repair"],
      "quality": "rough",
      "required_hands": 1,
      "use_noise": "medium"
    }
  }
}
```

### 容器分账与守恒规则

容器仍然是 `WorldObject`，不新增 `Container` 实体。容器能力只存在于 `WorldObject.components.container`。

```text
离散物品：WorldObject，由父容器 components.container.contained_object_ids 记录。
数量资源：resource quantity，由 components.container.quantity_contents 记录。
```

示例：

```text
箱子里的钥匙：chest_01.components.container.contained_object_ids = ["key_01"]
水袋里的水：waterskin_01.components.container.quantity_contents = [{ resource_type=water, amount=0.400, unit=liter }]
背包里的装水瓶：backpack_01.components.container.contained_object_ids 包含 bottle_01；bottle_01.components.container.quantity_contents 包含 water。
```

禁止：

```text
quantity_contents 中出现 object_id。
contained_object_ids 中出现非 WorldObject ID。
同一 object_id 同时出现在两个容器的 contained_object_ids 中。
离散物品继续用新写入的 placement.kind=inside_object 表达权威包含关系。
```

### ContainmentTransferResolver

离散物品移动必须由 `ContainmentTransferResolver.move_object` 原子执行，不能让 LLM、DM 文本、agent 或通用 patch 接口分别修改 source/target 容器。

输入：

```text
object_id
source_container_id
target_container_id
caused_by
```

预检：

```text
source_container_id 必须引用存在且有 components.container 的 WorldObject。
target_container_id 必须引用存在且有 components.container 的 WorldObject。
source.components.container.contained_object_ids 必须包含 object_id。
target.components.container.contained_object_ids 必须不包含 object_id。
object_id 不能出现在除 source 以外的任何容器 contained_object_ids 中。
移动后 target 的 occupied_slot_count 不得超过 capacity.slot_count。
移动后 target 的 contained_mass_kg 不得超过 capacity.mass_kg。
移动不能形成容器包含循环。
```

提交：

```text
从 source.components.container.contained_object_ids 移除 object_id。
向 target.components.container.contained_object_ids 添加 object_id。
调用 WeightDeriver 和 ContainerOccupancyDeriver 重算 source 与 target 的 derived 字段。
写入单条 ContainerObjectTransferred EventLog。
```

事务规则：

```text
move_object 是单一 StateTransition。
任一预检失败，WorldState 不发生任何变化。
禁止提交“只删 source”“只加 target”“先改 contents 后补重量”的中间状态。
validator 负责拒绝非法最终状态；resolver 负责只生成合法原子变更。
```

### QuantityTransferResolver

数量资源转移必须由 `QuantityTransferResolver.move_quantity_resource` 原子执行。

输入：

```text
resource_type
amount
unit
source_ref
target_ref
allowed_loss
caused_by
```

守恒公式：

```text
source_delta + target_delta + loss_delta = 0
```

规则：

```text
amount 必须为正数，且单位、精度和资源类型兼容。
source 必须有足够数量。
target 必须有足够 liquid_liters、mass_kg 或其他适用容量。
allowed_loss 必须由具体规则声明，例如倒水洒出；不能由 LLM 自由填写。
成功后必须重算 source 与 target 的 derived 字段，并写 QuantityResourceTransferred EventLog。
失败时 WorldState 不发生任何变化。
```

### weapon_stats

```json
{
  "components": {
    "weapon_stats": {
      "damage_profile": "heavy_slash",
      "hands": 2,
      "range": "melee",
      "reach": "close",
      "noise": "medium"
    }
  }
}
```

### armor_stats

```json
{
  "components": {
    "armor_stats": {
      "slot": "body",
      "armor_rating": 3,
      "mobility_penalty": 1,
      "noise": "medium",
      "coverage": ["torso"]
    }
  }
}
```

### resource_profile

```json
{
  "components": {
    "resource_profile": {
      "resource_kind": "firewood",
      "amount": 3,
      "unit": "bundle",
      "quality": "dry",
      "uses": ["fuel", "trade"]
    }
  }
}
```

### consumable

```json
{
  "components": {
    "consumable": {
      "consume_action": "eat",
      "servings": 1,
      "effects": [
        {
          "stat": "hunger",
          "delta": -18,
          "reason": "吃下干粮"
        }
      ],
      "spoilage": "stable"
    }
  }
}
```

### water_profile

```json
{
  "components": {
    "water_profile": {
      "capacity_liters": null,
      "available_liters": "unlimited",
      "quality": "uncertain",
      "requires_filtering": false,
      "refill_rate": "steady"
    }
  }
}
```

### furniture_profile

```json
{
  "components": {
    "furniture_profile": {
      "supports_rest": true,
      "supports_storage": false,
      "cover_value": "low",
      "movable_by_player": false
    }
  }
}
```

### fixture_profile

```json
{
  "components": {
    "fixture_profile": {
      "fixed": true,
      "blocks_movement": true,
      "access_sides": ["customer_side", "staff_side"],
      "can_anchor_objects": true
    }
  }
}
```

### portal_profile

```json
{
  "components": {
    "portal_profile": {
      "edge_id": "edge_front_hall_to_kitchen",
      "portal_kind": "door",
      "open_state": "closed",
      "locked": false,
      "blocks_sight": true,
      "blocks_sound": false
    }
  }
}
```

### clue_profile

```json
{
  "components": {
    "clue_profile": {
      "clue_kind": "track",
      "points_to": ["night_wolf_pack_01"],
      "freshness": "fresh",
      "confidence": 0.7,
      "reveals": ["route_to_ravine_edge"]
    }
  }
}
```

### document_profile

```json
{
  "components": {
    "document_profile": {
      "language": "common",
      "readability": "clear",
      "summary": "账本记录了最近三晚的异常肉价。",
      "reveals": ["graystone_meat_price_hook"]
    }
  }
}
```

### art_profile

```json
{
  "components": {
    "art_profile": {
      "subject": "一名戴银扣斗篷的猎人",
      "value_hint": "low",
      "hidden_detail": "画框背面刻着北坡旧猎径的符号"
    }
  }
}
```

### currency_value

```json
{
  "components": {
    "currency_value": {
      "currency": "copper",
      "amount": 3
    }
  }
}
```

### key_profile

```json
{
  "components": {
    "key_profile": {
      "opens_lock_ids": ["inn_room_03_lock"],
      "single_use": false
    }
  }
}
```

### trap_profile

```json
{
  "components": {
    "trap_profile": {
      "trigger_condition": "step_near",
      "severity": "medium",
      "disarm_difficulty": "moderate",
      "armed": true
    }
  }
}
```

### mechanism_profile

```json
{
  "components": {
    "mechanism_profile": {
      "mechanism_kind": "lock",
      "operable": true,
      "requires_key_id": "inn_room_03_key",
      "force_difficulty": "moderate",
      "repair_difficulty": "easy"
    }
  }
}
```

### vehicle_profile

```json
{
  "components": {
    "vehicle_profile": {
      "vehicle_kind": "wagon",
      "capacity": {
        "passengers": 2,
        "cargo_kg": 200
      },
      "mobility_state": "disabled",
      "entry_node_ids": ["overturned_wagon_side"],
      "requires_repair_to_move": true
    }
  }
}
```

P1 载具内部空间限制：

```text
vehicle_profile.entry_node_ids 非空时，vehicle_profile.mobility_state 必须是 static、disabled 或 anchored。
vehicle_profile.entry_node_ids 非空时，该 vehicle 不得通过 move/travel 结算改变 chunk。
vehicle_profile.mobility_state 为 movable、moving 或 operational 时，entry_node_ids 必须为空。
可移动 vehicle 在 P1 只能作为普通 WorldObject 被观察、搜索、乘坐、推动、修理或移动，不能拥有内部 LocationNode / Site。
MobileSite 延后到 P2 单独设计。
```

### material_profile

```json
{
  "components": {
    "material_profile": {
      "material_kind": "iron",
      "amount": 2,
      "unit": "ingot",
      "quality": "poor",
      "uses": ["repair", "trade"]
    }
  }
}
```

### light_profile

```json
{
  "components": {
    "light_profile": {
      "light_radius_band": "near",
      "fuel_type": "oil",
      "fuel_remaining_minutes": 45,
      "can_ignite": true,
      "smoke": "low"
    }
  }
}
```

### 组件字段说明

| 字段 | 含义 |
| --- | --- |
| `components.container.capacity` | 容器最大容量。P1 使用多维容量，不再使用单一 `amount/unit`。 |
| `components.container.capacity.liquid_liters` | 液体容量，单位 liter，定点三位小数。不能装液体时为 0 或省略。 |
| `components.container.capacity.mass_kg` | 最大内容承重，单位 kg，定点三位小数，不包含容器自重。 |
| `components.container.capacity.slot_count` | 离散物品槽位容量，整数。不能装离散物品时为 0。 |
| `components.container.quantity_contents` | 当前数量资源内容。只允许水、油、沙、米、盐等数量资源，不能出现 `object_id`。 |
| `components.container.quantity_contents[].resource_type` | 内容资源类型，例如 water。 |
| `components.container.quantity_contents[].amount` | 内容数量，必须使用定点十进制字符串。 |
| `components.container.quantity_contents[].unit` | 内容单位，例如 liter、kg、count。 |
| `components.container.quantity_contents[].quality` | 内容质量。 |
| `components.container.contained_object_ids` | 当前被该容器包含的离散 WorldObject ID 列表。钥匙、苹果、书、瓶子等独立对象必须进入这里，不能进入 `quantity_contents`。 |
| `components.tool_profile.tool_kinds` | 工具用途类别，例如 pry、repair。 |
| `components.tool_profile.quality` | 工具质量。影响成功率、耗时和损坏风险。 |
| `components.tool_profile.required_hands` | 使用所需手数。 |
| `components.tool_profile.use_noise` | 使用时噪音。 |
| `components.weapon_stats.damage_profile` | 伤害轮廓。P0 只作为战斗/威慑规则输入，不直接写叙事结果。 |
| `components.weapon_stats.hands` | 使用所需手数。 |
| `components.weapon_stats.range` | 攻击距离类型，例如 melee、ranged。 |
| `components.weapon_stats.reach` | 近战触达距离。 |
| `components.weapon_stats.noise` | 使用噪音。 |
| `components.armor_stats.slot` | 装备槽位。 |
| `components.armor_stats.armor_rating` | 护甲值。 |
| `components.armor_stats.mobility_penalty` | 行动惩罚。 |
| `components.armor_stats.noise` | 穿戴或行动噪音。 |
| `components.armor_stats.coverage` | 覆盖部位。 |
| `components.resource_profile.resource_kind` | 资源种类。 |
| `components.resource_profile.amount` | 资源数量。 |
| `components.resource_profile.unit` | 资源单位。 |
| `components.resource_profile.quality` | 资源质量。 |
| `components.resource_profile.uses` | 可用于哪些规则用途。 |
| `components.consumable.consume_action` | 消耗动作，例如 eat、drink。 |
| `components.consumable.servings` | 可消耗份数。 |
| `components.consumable.effects` | 消耗成功后的状态变化建议，最终仍由 resolver 应用。 |
| `components.consumable.effects[].stat` | 被影响的生存数值。 |
| `components.consumable.effects[].delta` | 数值变化。 |
| `components.consumable.effects[].reason` | 给玩家解释变化原因的文本来源。 |
| `components.consumable.spoilage` | 变质稳定性。 |
| `components.water_profile.capacity_liters` | 水源或水体对象的容量。无限水源可为 `null`。 |
| `components.water_profile.available_liters` | 当前可获得水量，可为数值或 `unlimited`。 |
| `components.water_profile.quality` | 水质。 |
| `components.water_profile.requires_filtering` | 是否需要过滤或净化。 |
| `components.water_profile.refill_rate` | 水源恢复速度。 |
| `components.furniture_profile.supports_rest` | 是否可用于休息。 |
| `components.furniture_profile.supports_storage` | 是否可用于存放物品。 |
| `components.furniture_profile.cover_value` | 可提供的掩护价值。 |
| `components.furniture_profile.movable_by_player` | 玩家是否可移动。 |
| `components.fixture_profile.fixed` | 是否固定在场景中。 |
| `components.fixture_profile.blocks_movement` | 是否阻挡通行。 |
| `components.fixture_profile.access_sides` | 可接近的方向或侧面。 |
| `components.fixture_profile.can_anchor_objects` | 是否可作为其他对象的承载点。 |
| `components.portal_profile.edge_id` | 该 portal 对应的 LocationEdge 或 ChunkEdge。 |
| `components.portal_profile.portal_kind` | portal 类型，例如 door、stairs、gap。 |
| `components.portal_profile.open_state` | 开合状态。 |
| `components.portal_profile.locked` | 是否上锁。 |
| `components.portal_profile.blocks_sight` | 是否阻挡视线。 |
| `components.portal_profile.blocks_sound` | 是否阻挡声音。 |
| `components.clue_profile.clue_kind` | 线索类型。 |
| `components.clue_profile.points_to` | 线索指向的对象、实体、地点或事件 ID。 |
| `components.clue_profile.freshness` | 线索新鲜度。 |
| `components.clue_profile.confidence` | 线索可信度。 |
| `components.clue_profile.reveals` | 观察或解读后可揭示的事实 ID。 |
| `components.document_profile.language` | 文档语言。 |
| `components.document_profile.readability` | 可读性。 |
| `components.document_profile.summary` | 文档摘要。不能替代完整状态变化。 |
| `components.document_profile.reveals` | 阅读后揭示的事实 ID。 |
| `components.art_profile.subject` | 艺术品主题。 |
| `components.art_profile.value_hint` | 价值提示。 |
| `components.art_profile.hidden_detail` | 观察或搜索后可能发现的隐藏细节。 |
| `components.currency_value.currency` | 货币单位。 |
| `components.currency_value.amount` | 货币数量。 |
| `components.key_profile.opens_lock_ids` | 可开启的锁 ID 列表。 |
| `components.key_profile.single_use` | 是否一次性使用。 |
| `components.trap_profile.trigger_condition` | 触发条件。 |
| `components.trap_profile.severity` | 陷阱严重程度。 |
| `components.trap_profile.disarm_difficulty` | 拆除难度。 |
| `components.trap_profile.armed` | 是否处于待触发状态。 |
| `components.mechanism_profile.mechanism_kind` | 机关类型，例如 lock。 |
| `components.mechanism_profile.operable` | 当前是否可操作。 |
| `components.mechanism_profile.requires_key_id` | 需要的钥匙 ID。 |
| `components.mechanism_profile.force_difficulty` | 强行开启难度。 |
| `components.mechanism_profile.repair_difficulty` | 修理难度。 |
| `components.vehicle_profile.vehicle_kind` | 载具类型。 |
| `components.vehicle_profile.capacity.passengers` | 载客数量。 |
| `components.vehicle_profile.capacity.cargo_kg` | 载货重量。 |
| `components.vehicle_profile.mobility_state` | 载具移动状态。P1 闭集为 static、disabled、anchored、movable、moving、operational。 |
| `components.vehicle_profile.entry_node_ids` | 可进入该载具内部的 LocationNode。P1 中非空时载具必须不可移动。 |
| `components.vehicle_profile.requires_repair_to_move` | 移动前是否需要修理。 |
| `components.material_profile.material_kind` | 材料类型。 |
| `components.material_profile.amount` | 材料数量。 |
| `components.material_profile.unit` | 材料单位。 |
| `components.material_profile.quality` | 材料质量。 |
| `components.material_profile.uses` | 材料可用于哪些规则用途。 |
| `components.light_profile.light_radius_band` | 光照范围分级。 |
| `components.light_profile.fuel_type` | 燃料类型。 |
| `components.light_profile.fuel_remaining_minutes` | 剩余燃烧时间。 |
| `components.light_profile.can_ignite` | 是否可以点燃。 |
| `components.light_profile.smoke` | 烟雾程度。 |

P0 组件白名单：

```text
container
tool_profile
weapon_stats
armor_stats
resource_profile
consumable
water_profile
furniture_profile
fixture_profile
portal_profile
clue_profile
document_profile
art_profile
currency_value
key_profile
trap_profile
mechanism_profile
vehicle_profile
material_profile
light_profile
```

### object_type 到组件兼容规则

| object_type | 必须/推荐组件 | 禁止或限制 |
| --- | --- | --- |
| item | 无必须组件 | 只能执行通用物品动作 |
| weapon | 推荐 `weapon_stats` | 无 `weapon_stats` 时不能执行 `attack` 的战斗结算 |
| armor | 推荐 `armor_stats` | 无 `armor_stats` 时不能提供防护数值 |
| tool | 推荐 `tool_profile` | 无 `tool_profile` 时只能作为普通 item 使用 |
| container | 推荐 `container` | 无 `container` 时不能装载数量资源或离散子物品 |
| resource | 推荐 `resource_profile` | 资源数量不得只写在 description |
| food | 必须 `consumable` | 无 `consumable` 时不能作为 `eat.source` |
| water_source | 必须 `water_profile` | 无 `water_profile` 时不能作为 `drink.source` 或 `refill_water.source` |
| furniture | 推荐 `furniture_profile` | 大型家具通常 `portable=false` |
| fixture | 推荐 `fixture_profile` | fixture 默认 `portable=false` |
| portal | 必须 `portal_profile` | 无 `portal_profile` 时不能连接 LocationEdge |
| clue | 推荐 `clue_profile` | 线索指向必须是对象、路线、事件或任务状态的 ID |
| document | 必须 `document_profile` | 无 `document_profile` 时不能执行 `read` |
| artwork | 推荐 `art_profile` | 隐藏信息必须通过 search/observe 揭示 |
| trap | 必须 `trap_profile` | 无 `trap_profile` 时不能触发伤害或拆除难度 |
| mechanism | 推荐 `mechanism_profile` | 机关操作必须通过 resolver 校验 |
| currency | 必须 `currency_value` | 金额不能只写在 name |
| key | 必须 `key_profile` | 开锁目标必须引用 lock/mechanism/entitlement ID |
| vehicle | 推荐 `vehicle_profile` | 可进入载具必须有 entry node 或 portal |
| material | 推荐 `material_profile` | 材料数量不得只写在 description |
| light_source | 必须 `light_profile` | 无 `light_profile` 时不能改变可见性 |

实现必须把上表物化为机器可读矩阵。P0 使用以下结构：

```yaml
object_type_component_matrix:
  item: { required: [], recommended: [], allowed: [], forbidden_policy: all_components_except_allowed }
  weapon: { required: [], recommended: [weapon_stats], allowed: [weapon_stats], forbidden_policy: all_components_except_allowed }
  armor: { required: [], recommended: [armor_stats], allowed: [armor_stats], forbidden_policy: all_components_except_allowed }
  tool: { required: [], recommended: [tool_profile], allowed: [tool_profile], forbidden_policy: all_components_except_allowed }
  container: { required: [], recommended: [container], allowed: [container], forbidden_policy: all_components_except_allowed }
  resource: { required: [], recommended: [resource_profile], allowed: [resource_profile], forbidden_policy: all_components_except_allowed }
  food: { required: [consumable], recommended: [], allowed: [consumable], forbidden_policy: all_components_except_allowed }
  water_source: { required: [water_profile], recommended: [], allowed: [water_profile], forbidden_policy: all_components_except_allowed }
  furniture: { required: [], recommended: [furniture_profile], allowed: [furniture_profile], forbidden_policy: all_components_except_allowed }
  fixture: { required: [], recommended: [fixture_profile], allowed: [fixture_profile], forbidden_policy: all_components_except_allowed }
  portal: { required: [portal_profile], recommended: [], allowed: [portal_profile], forbidden_policy: all_components_except_allowed }
  clue: { required: [], recommended: [clue_profile], allowed: [clue_profile], forbidden_policy: all_components_except_allowed }
  document: { required: [document_profile], recommended: [], allowed: [document_profile], forbidden_policy: all_components_except_allowed }
  artwork: { required: [], recommended: [art_profile], allowed: [art_profile], forbidden_policy: all_components_except_allowed }
  trap: { required: [trap_profile], recommended: [], allowed: [trap_profile], forbidden_policy: all_components_except_allowed }
  mechanism: { required: [], recommended: [mechanism_profile], allowed: [mechanism_profile], forbidden_policy: all_components_except_allowed }
  currency: { required: [currency_value], recommended: [], allowed: [currency_value], forbidden_policy: all_components_except_allowed }
  key: { required: [key_profile], recommended: [], allowed: [key_profile], forbidden_policy: all_components_except_allowed }
  vehicle: { required: [], recommended: [vehicle_profile], allowed: [vehicle_profile], forbidden_policy: all_components_except_allowed }
  material: { required: [], recommended: [material_profile], allowed: [material_profile], forbidden_policy: all_components_except_allowed }
  light_source: { required: [light_profile], recommended: [], allowed: [light_profile], forbidden_policy: all_components_except_allowed }
```

矩阵规则：

```text
required 组件缺失时，WorldObjectValidator 必须拒绝。
allowed 之外的组件出现时，WorldObjectValidator 必须拒绝。
recommended 只用于生成器和内容包质量检查，不作为运行时拒绝条件。
container_catalog 物化出的对象只能使用 container 这一项矩阵；即使带有 refill_water affordance，也不得添加 water_profile。
```

### ActionRoleRequirement

`ActionRoleRequirement` 定义动作参数角色需要什么实体和组件。它是 `ActionGrounder` 与 resolver 的输入，不是 catalog 自动补组件规则。

WorldObjectValidator 只检查：

```text
affordance 是否属于允许集合。
对象是否至少能静态满足该 affordance 的一个合法角色。
对象没有写入与 object_type 互斥的组件。
```

真正执行动作时，ActionGrounder 必须为每个动作绑定完整角色；resolver 必须检查运行时前置条件。

| action | role | 可接受实体 | 静态要求 | 运行时要求 |
| --- | --- | --- | --- | --- |
| eat | source | WorldObject | `components.consumable.consume_action=eat` | servings 或 amount 大于 0，未腐败到不可食用。 |
| drink | source | WorldObject | 满足其一：`components.consumable.consume_action=drink`；`components.water_profile`；`components.container.capacity.liquid_liters > 0`。 | consumable 有剩余；water_profile 可饮且有水；container.quantity_contents 含可饮用液体且数量大于 0。 |
| refill_water | source | ResourceNode 或 WorldObject | ResourceNode 表示可取水资源；或 WorldObject 具备 `components.water_profile`。 | 可获得水量大于 0 或 unlimited，水质和过滤条件通过 resolver 判定。 |
| refill_water | target | WorldObject | `components.container.capacity.liquid_liters > 0`。 | 目标容器可触及，有剩余液体容量，已有 quantity_contents 为空或与水兼容。 |
| pour | source | WorldObject | `components.container.capacity.liquid_liters > 0`。 | container.quantity_contents 存在可倾倒液体且数量大于 0。 |
| pour | target | WorldObject、ResourceNode、LocationNode 或 Zone | 目标能接受液体，或允许倒在地点/区域。 | 由 resolver 根据污染、浪费、火焰、容器容量等规则结算。 |
| read | source | WorldObject | `components.document_profile`。 | 文档可见、可触及，语言和可读性通过 resolver 判定。 |
| unlock | tool | WorldObject | `components.key_profile` 或 `components.tool_profile` 支持开锁用途。 | 钥匙匹配或工具检定通过。 |
| unlock | target | WorldObject | `components.mechanism_profile` 或 portal 关联的 lock/mechanism。 | 目标上锁且可触及。 |
| disarm | target | WorldObject | `components.trap_profile` 或 `components.mechanism_profile`。 | 目标处于 armed/jammed 等可处理状态。 |

角色规则：

```text
一个对象声明某个 affordance，只需要能满足该 action 的至少一个静态角色。
同一动作的多个角色可以绑定到不同实体。
WorldObjectValidator 不检查运行时数量、距离、可见性或水质；这些由 ActionGrounder 和 resolver 检查。
内容包不得为了通过某个 affordance 校验而给对象添加错误组件。例如水囊不能添加 water_profile 来冒充水源。
```

## 示例

### 战斧

```json
{
  "id": "battle_axe_01",
  "name": "缺口战斧",
  "aliases": ["战斧", "斧头", "旧斧"],
  "description": "斧刃有两处缺口，木柄缠着旧皮条。",
  "object_type": "weapon",
  "placement": {
    "kind": "contained_by_parent",
    "reachability": "requires_open_container"
  },
  "visibility": "hidden",
  "physical": {
    "size": "medium",
    "tare_weight_kg": "3.500",
    "portable": true,
    "condition": "worn",
    "materials": ["iron", "wood", "leather"],
    "traits": ["sharp_edge"]
  },
  "ownership": {
    "owner_id": null,
    "legal_status": "abandoned"
  },
  "affordances": ["observe", "take", "equip", "attack", "repair"],
  "components": {
    "weapon_stats": {
      "damage_profile": "heavy_slash",
      "hands": 2,
      "range": "melee",
      "reach": "close",
      "noise": "medium"
    }
  },
  "state": {
    "durability": 62,
    "equipped_by": null
  },
  "tags": ["two_handed", "hunter_cabin"],
  "provenance": {
    "source_kind": "content_pack",
    "content_pack_id": "hunter_cabin_objects_p0",
    "content_pack_version": "2026-07-18.1",
    "catalog_kind": "scene_object_catalog",
    "catalog_id": "scene_battle_axe",
    "catalog_version": "2026-07-18.1",
    "materializer_id": "SceneObjectMaterializer",
    "materializer_version": "2026-07-18.1",
    "materialization_id": "mat_battle_axe_01",
    "instance_key": "hunter_cabin_inside/weapon_rack/battle_axe_01",
    "schema_version": "world_object@2026-07-18",
    "registry_hash": "sha256:registry_hash",
    "rule_bundle_hash": "sha256:rule_bundle_hash",
    "content_pack_hash": "sha256:content_pack_hash",
    "catalog_entry_hash": "sha256:catalog_entry_hash"
  },
  "created_turn": 0,
  "updated_turn": 0
}
```

### 铠甲

```json
{
  "id": "rusted_chainmail_01",
  "name": "生锈锁子甲",
  "aliases": ["锁子甲", "铠甲"],
  "object_type": "armor",
  "placement": {
    "kind": "on_object",
    "object_id": "cabin_armor_stand_01",
    "relation": "hanging_on",
    "reachability": "reachable"
  },
  "visibility": "visible",
  "physical": {
    "size": "medium",
    "tare_weight_kg": "9.000",
    "portable": true,
    "condition": "damaged",
    "materials": ["iron"],
    "traits": ["rust_prone"]
  },
  "ownership": {
    "owner_id": null,
    "legal_status": "abandoned"
  },
  "affordances": ["observe", "take", "equip", "repair"],
  "components": {
    "armor_stats": {
      "slot": "body",
      "armor_rating": 3,
      "mobility_penalty": 1,
      "noise": "medium",
      "coverage": ["torso"]
    }
  },
  "state": {
    "durability": 41,
    "equipped_by": null
  },
  "provenance": {
    "source_kind": "content_pack",
    "content_pack_id": "hunter_cabin_objects_p0",
    "content_pack_version": "2026-07-18.1",
    "catalog_kind": "scene_object_catalog",
    "catalog_id": "scene_rusted_chainmail",
    "catalog_version": "2026-07-18.1",
    "materializer_id": "SceneObjectMaterializer",
    "materializer_version": "2026-07-18.1",
    "materialization_id": "mat_rusted_chainmail_01",
    "instance_key": "hunter_cabin_inside/armor_stand/rusted_chainmail_01",
    "schema_version": "world_object@2026-07-18",
    "registry_hash": "sha256:registry_hash",
    "rule_bundle_hash": "sha256:rule_bundle_hash",
    "content_pack_hash": "sha256:content_pack_hash",
    "catalog_entry_hash": "sha256:catalog_entry_hash"
  },
  "created_turn": 0,
  "updated_turn": 0
}
```

### 肖像画

```json
{
  "id": "old_portrait_01",
  "name": "褪色肖像画",
  "aliases": ["肖像画", "画像", "画"],
  "object_type": "artwork",
  "placement": {
    "kind": "attached_to_object",
    "object_id": "cabin_north_wall_01",
    "relation": "hanging_on",
    "reachability": "reachable"
  },
  "visibility": "visible",
  "physical": {
    "size": "medium",
    "tare_weight_kg": "1.200",
    "portable": true,
    "condition": "worn",
    "materials": ["wood", "cloth"],
    "traits": ["flammable", "fragile"]
  },
  "ownership": {
    "owner_id": null,
    "legal_status": "abandoned"
  },
  "affordances": ["observe", "take", "search"],
  "components": {
    "art_profile": {
      "subject": "一名戴银扣斗篷的猎人",
      "value_hint": "low",
      "hidden_detail": "画框背面刻着北坡旧猎径的符号"
    }
  },
  "state": {},
  "tags": ["family_history", "hidden_clue"],
  "provenance": {
    "source_kind": "content_pack",
    "content_pack_id": "hunter_cabin_objects_p0",
    "content_pack_version": "2026-07-18.1",
    "catalog_kind": "scene_object_catalog",
    "catalog_id": "scene_old_portrait",
    "catalog_version": "2026-07-18.1",
    "materializer_id": "SceneObjectMaterializer",
    "materializer_version": "2026-07-18.1",
    "materialization_id": "mat_old_portrait_01",
    "instance_key": "hunter_cabin_inside/north_wall/old_portrait_01",
    "schema_version": "world_object@2026-07-18",
    "registry_hash": "sha256:registry_hash",
    "rule_bundle_hash": "sha256:rule_bundle_hash",
    "content_pack_hash": "sha256:content_pack_hash",
    "catalog_entry_hash": "sha256:catalog_entry_hash"
  },
  "created_turn": 0,
  "updated_turn": 0
}
```

## 权威操作规则

### 观察

`observe` 不改变对象位置。它可以把 `visibility=hinted` 改为 `visible`，并写入 `ObjectRevealedEvent`。

### 拾取

`take` 成功后必须修改 `placement`：

```text
zone/on_object/contained_by_parent
-> player_inventory
```

如果 `physical.portable=false`，resolver 必须拒绝直接拾取，并给出移动、拆解、推拉或搜索等替代方案。

### 购买

`purchase` 必须同时满足：

```text
ownership.legal_status = for_sale
玩家货币足够
卖方或设施在当前 projection 中可交互
```

成功后：

```text
扣钱
写交易事件
修改 ownership 或 placement
刷新 projection
```

### 装备

`equip` 必须检查：

```text
object_type = weapon 或 armor 或 tool
对象在玩家物品栏或当前可触及位置
装备槽未冲突
condition 不为 broken/ruined
```

成功后写入 `ObjectEquippedEvent`，并更新 `state.equipped_by`。

### 消耗

`eat`、`drink`、`use_consumable` 成功后必须修改资源、对象 state 或 placement：

```text
amount 减少
durability/fuel/charges 减少
对象耗尽后 placement=removed 或 visibility=removed
```

### 打开和搜索

`open` 和 `search` 对容器、机关、画框、柜子等对象生效。搜索结果必须来自：

```text
container.contained_object_ids 中已物化的隐藏离散物品
container.quantity_contents 中已物化的数量资源
DiscoveryTable
```

不能由 DM 临场凭空发放最终物品。

## Validator 规则

实现时必须加入 `WorldObjectValidator`，保证：

1. `id` 全局唯一。
2. `name` 非空。
3. `object_type` 属于允许集合。
4. `WorldObject` 不允许出现 `type` 字段；对象分类只能写 `object_type`。
5. `placement.kind` 属于允许集合。
6. `placement` 引用的 chunk、node、zone、object、actor 必须存在。
7. 对象位置链不能形成循环。
8. `visibility=removed` 时，`placement.kind` 必须是 `removed` 或对象不得出现在当前 projection。
9. `physical.size` 和 `physical.condition` 属于允许集合。
10. `physical.tare_weight_kg` 不能为负数；`physical.weight_kg` 作为新 WorldState 字段必须被拒绝，迁移工具除外。
11. `physical.portable=false` 的对象不能被 resolver 直接放入 `player_inventory`。
12. `physical.materials` 如果存在，所有值必须属于材料闭集。
13. `physical.traits` 如果存在，所有值必须属于物理交互 trait 闭集。
14. `physical.traits` 不能表达具体剧情或任务状态，例如不得写 `opens_wolf_quest`。
15. `ownership.legal_status` 属于允许集合。
16. `affordances` 必须属于允许集合。
17. `components` 必须属于组件白名单。
18. 组件和 `object_type` 必须符合“object_type 到组件兼容规则”表。
19. 带有结算语义的 affordance 必须能静态满足 `ActionRoleRequirement` 中至少一个合法角色；不能按 affordance 字符串直接要求单一组件。例如 `refill_water` 在 source 角色需要 ResourceNode 或 `water_profile`，在 target 角色需要液体 `container`。
20. LLM proposal 不能直接提交 placement、ownership、state 的最终变更，必须经过 resolver。
21. `WorldObject.provenance` 必须存在；P1 起不得只写旧 `source` 字符串。
22. `provenance.source_kind=content_pack` 时，必须完整记录 content pack、catalog、materializer、schema、registry、rule bundle 和 content pack hash。
23. `generic_item_catalog` 条目只允许 `object_type=item`。
24. `generic_item_catalog` 条目不得定义 `components` 或任何制作、合成、配方字段。
25. `generic_item_catalog.default_affordances` 只能从 `observe/take/search/trade` 中选择。
26. `generic_item_catalog` 实例化后的 `WorldObject` 必须保持 `object_type=item` 且 `components={}`。
27. `generic_item_catalog` 实例化不能绕过 `WorldObjectValidator`。
28. `container_catalog` 条目只允许 `object_type=container`。
29. `container_catalog` 条目必须能合并出 `components.container.capacity`、`components.container.quantity_contents` 和 `components.container.contained_object_ids`。
30. `container_catalog` 默认 `quantity_contents` 和 `contained_object_ids` 必须为空数组，具体内容由场景实例、发现表或 resolver 写入。
31. `container_catalog` 不得定义非容器组件。
32. `container_catalog` 实例化不能绕过 `WorldObjectValidator`。
33. `components.container.capacity` 不允许使用旧 `{amount, unit}` 结构。
34. `components.container.quantity_contents` 不允许出现 `object_id`。
35. `components.container.contained_object_ids` 必须全部引用存在的 WorldObject。
36. 同一 WorldObject ID 只能出现在一个容器的 `contained_object_ids` 中。
37. `contained_object_ids` 不能形成包含循环。
38. `derived.total_weight_kg`、`derived.contained_mass_kg`、`derived.occupied_liquid_liters`、`derived.occupied_slot_count` 必须能由 `WeightDeriver` / `ContainerOccupancyDeriver` 重算得到。
39. 当前占用不得超过 `capacity.liquid_liters`、`capacity.mass_kg` 或 `capacity.slot_count`。
40. `vehicle_profile.entry_node_ids` 非空时，`vehicle_profile.mobility_state` 必须为 static、disabled 或 anchored。
41. `vehicle_profile.mobility_state` 为 movable、moving 或 operational 时，`vehicle_profile.entry_node_ids` 必须为空。
42. P1 中拥有内部 `LocationNode` 的 vehicle 不得通过正常玩法 resolver 改变 chunk；需要移动内部空间时必须等待 P2 `MobileSite` 设计。

## 与其他文档关系

本设计依赖：

- [地点与空间规则](./location-space-rules.md)
- [2026-07-08-isekai-scene-object-structuring-design.md](../../2026-07-08-isekai-scene-object-structuring-design.md)
- [2026-07-08-isekai-content-agnostic-refactor-design.md](../../2026-07-08-isekai-content-agnostic-refactor-design.md)
- [2026-07-08-isekai-llm-intent-resolution-design.md](../../2026-07-08-isekai-llm-intent-resolution-design.md)

数据流：

```text
ContentPack / LLM Proposal
-> WorldObject Materializer
-> WorldObject Validator
-> Authoritative WorldState
-> SpaceProjectionService
-> ActionGrounder
-> Deterministic Resolver
-> EventLog
-> Narration Projection
-> UI Projection
```

## 推荐实现顺序

### P0.1：基础 schema 与 validator

交付内容：

- `WorldObject` schema。
- `WorldObjectValidator`。
- object_type、visibility、placement.kind、condition、legal_status、affordance、component 白名单。

验收：

- 缺少 `id/name/object_type/placement/visibility/physical/affordances/state/created_turn/updated_turn` 会被拒绝。
- 非法 object_type 会被拒绝。
- 非法 placement 引用会被拒绝。
- 对象位置链循环会被拒绝。

### P0.2：对象投影

交付内容：

- 将 `WorldObject` 投影接入 `SpaceProjectionService`。
- 当前 chunk/node/zone 可见对象查询。
- hidden/hinted/removed 过滤。

验收：

- `visibility=hidden` 的对象不出现在 visible projection。
- `visibility=hinted` 只作为线索出现，不作为可直接拾取对象。
- `placement=removed` 的对象不出现在可互动列表。

### P0.3：对象状态变更事件

交付内容：

- `ObjectMovedEvent`
- `ObjectRevealedEvent`
- `ObjectStateChangedEvent`
- `ObjectEquippedEvent`
- `ObjectConsumedEvent`
- `ObjectRemovedEvent`

验收：

- 拾取成功后 placement 变成 `player_inventory`。
- 消耗成功后 amount/charges/fuel 或 placement 正确变化。
- 装备成功后 `state.equipped_by` 正确变化。

### P0.4：组件接入

交付内容：

- container
- tool_profile
- weapon_stats
- armor_stats
- resource_profile
- consumable
- water_profile
- furniture_profile
- fixture_profile
- portal_profile
- clue_profile
- key_profile
- trap_profile
- document_profile
- art_profile
- currency_value
- mechanism_profile
- vehicle_profile
- material_profile
- light_profile

验收：

- 容器打开后才能显示内部 hidden contained_object_ids 或 quantity_contents。
- 武器和护甲能被装备，但不能绕过装备槽/condition 校验。
- 肖像画搜索能揭示画框背后的线索对象，而不是 DM 直接发放未落库线索。
- `eat/refill_water/read/unlock/trigger` 等动作缺少对应角色组件或运行时前置条件时会被 resolver 拒绝。
- `vehicle_profile.entry_node_ids` 非空时，`mobility_state` 不是 static、disabled 或 anchored 会被 validator 拒绝。
- `mobility_state` 为 movable、moving 或 operational 的载具携带 `entry_node_ids` 会被 validator 拒绝。

### P0.5：通用小物件 catalog

交付内容：

- 内容包支持 `generic_item_catalog.category_defaults`。
- 内容包支持 `generic_item_catalog.entries`。
- `GenericItemCatalogValidator`。
- `GenericItemMaterializer`，负责把 catalog 条目实例化为 `WorldObject(object_type=item)`。

验收：

- `generic_bent_nail` 能实例化为 `WorldObject`，并带有稳定 `id/name/aliases/description/placement/visibility/physical/affordances/state/tags/provenance/turns`。
- catalog 条目缺少 `catalog_id/name/object_type/category` 会被拒绝。
- catalog 条目的 `object_type` 不是 `item` 会被拒绝。
- catalog 条目定义 `components` 会被拒绝。
- catalog 条目定义制作、合成或配方字段会被拒绝。
- catalog 条目使用 `observe/take/search/trade` 之外的默认 affordance 会被拒绝。
- 实例化结果必须再次经过 `WorldObjectValidator`，不能直接写入 `WorldState`。
- 实例化结果的 `provenance` 必须能追溯到 content pack、catalog entry 和 materializer 版本。

### P0.6：容器 catalog

交付内容：

- 内容包支持 `container_catalog.category_defaults`。
- 内容包支持 `container_catalog.entries`。
- `ContainerCatalogValidator`。
- `ContainerMaterializer`，负责把 catalog 条目实例化为 `WorldObject(object_type=container)` 并写入 `components.container`。

验收：

- `container_waterskin` 能实例化为 `WorldObject`，并带有稳定 `id/name/aliases/description/placement/visibility/physical/affordances/components.container/state/tags/provenance/turns`。
- `container_waterskin` 可以带 `drink/refill_water/pour` affordance，实例化后仍只有 `components.container`，不得要求或自动添加 `components.water_profile`。
- catalog 条目缺少 `catalog_id/name/object_type/category` 会被拒绝。
- catalog 条目的 `object_type` 不是 `container` 会被拒绝。
- catalog 条目缺少可合并的多维 `capacity` 会被拒绝。
- catalog 条目默认 `quantity_contents` 或 `contained_object_ids` 不是空数组会被拒绝。
- catalog 条目定义非容器组件会被拒绝。
- 实例化结果必须再次经过 `WorldObjectValidator`，不能直接写入 `WorldState`。
- 实例化结果的 `provenance` 必须能追溯到 content pack、catalog entry 和 materializer 版本。

## 回归测试要求

新增测试：

- `test_world_object_requires_minimum_fields`
- `test_world_object_rejects_unknown_object_type`
- `test_world_object_rejects_invalid_placement_reference`
- `test_world_object_placement_cycle_is_rejected`
- `test_hidden_object_not_in_visible_projection`
- `test_removed_object_not_in_interactable_projection`
- `test_take_moves_portable_object_to_player_inventory`
- `test_take_rejects_non_portable_object`
- `test_purchase_requires_for_sale_and_balance`
- `test_equip_requires_valid_component_and_condition`
- `test_unknown_affordance_is_rejected_without_blocked_affordances`
- `test_affordance_requires_at_least_one_static_action_role`
- `test_refill_water_source_requires_resource_node_or_water_profile`
- `test_refill_water_target_accepts_liquid_container_without_water_profile`
- `test_drink_accepts_liquid_container_as_attemptable_role`
- `test_drink_from_empty_container_fails_in_resolver_not_validator`
- `test_object_type_component_compatibility_is_enforced`
- `test_consumed_object_updates_amount_or_removed`
- `test_container_contents_revealed_only_after_open_or_search`
- `test_world_object_rejects_new_inside_object_placement`
- `test_contained_by_parent_requires_unique_parent_container`
- `test_physical_weight_kg_is_rejected_after_migration`
- `test_tare_weight_kg_requires_unit_range_precision`
- `test_total_weight_is_derived_recursively`
- `test_container_rejects_legacy_capacity_amount_unit`
- `test_container_quantity_contents_rejects_object_id`
- `test_container_contained_object_ids_must_reference_world_object`
- `test_object_cannot_be_in_two_containers`
- `test_container_containment_cycle_is_rejected`
- `test_container_occupancy_cannot_exceed_liquid_capacity`
- `test_container_occupancy_cannot_exceed_mass_capacity`
- `test_container_occupancy_cannot_exceed_slot_capacity`
- `test_move_object_is_atomic_state_transition`
- `test_move_object_failure_leaves_world_state_unchanged`
- `test_quantity_resource_transfer_conserves_amount`
- `test_currency_amount_must_use_currency_value_component`
- `test_portal_requires_portal_profile_for_location_edge`
- `test_food_requires_consumable_for_eat`
- `test_water_source_requires_water_profile_for_refill_source`
- `test_llm_proposal_cannot_directly_grant_world_object`
- `test_generic_item_catalog_requires_minimum_fields`
- `test_generic_item_catalog_rejects_non_item_type`
- `test_generic_item_catalog_rejects_components`
- `test_generic_item_catalog_rejects_recipe_fields`
- `test_generic_item_catalog_restricts_affordances`
- `test_generic_item_catalog_entry_instantiates_world_object_item`
- `test_generic_item_instance_keeps_components_empty`
- `test_generic_item_instance_runs_world_object_validator`
- `test_container_catalog_requires_minimum_fields`
- `test_container_catalog_rejects_non_container_type`
- `test_container_catalog_requires_capacity`
- `test_container_catalog_rejects_default_quantity_or_contained_objects`
- `test_container_catalog_rejects_non_container_components`
- `test_container_catalog_entry_instantiates_world_object_container`
- `test_container_instance_contains_container_component`
- `test_container_liquid_vessel_refill_water_affordance_passes_without_water_profile`
- `test_container_instance_runs_world_object_validator`

## 架构决策

1. 非生命对象统一建模为 `WorldObject`。
2. `WorldObject` 的基础 schema 只放所有对象都必须有的字段。
3. 具体对象能力通过 components 扩展。
4. `object_type` 是闭集，具体内容名不得成为类型。
5. 所有对象必须有 `placement`。
6. 所有对象必须能通过位置链追溯到 chunk、zone、actor、玩家物品栏、offscreen 或 removed。
7. `affordance` 是可尝试动作，不是成功承诺。
8. 对象状态变化必须写事件。
9. LLM 可以提出对象，但不能直接提交最终状态变化。
10. 容器不是独立 EntityType，只能作为 `WorldObject.components.container` 存在。
11. 离散物品包含关系由父容器 `contained_object_ids` 作为权威记录；子物品只使用 `contained_by_parent` 标记自身处于被包含状态。
12. 物品移动和数量资源转移只能通过原子 resolver 写入，不能由 agent 或 LLM 拼接多个字段 patch。
13. `physical.tare_weight_kg` 是基础重量，`derived.total_weight_kg` 是派生总重。
