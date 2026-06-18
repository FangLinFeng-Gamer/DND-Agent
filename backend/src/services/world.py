from sqlite3 import Row
from typing import Any

from backend.src.db.sqlite import SQLiteStore, decode_json, encode_json
from backend.src.schemas.world import WorldEntryOut, WorldSearchOut


def race_entry(
    name: str,
    content: str,
    tags: list[str],
    summary_en: str,
    summary_zh: str,
    traits_en: str,
    traits_zh: str,
    mechanics: dict[str, dict[str, str]],
    subraces: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "category": "race",
        "name": name,
        "content": content,
        "tags": tags,
        "metadata": {
            "summary": {"en": summary_en, "zh": summary_zh},
            "traits": {"en": traits_en, "zh": traits_zh},
            "mechanics": mechanics,
            "subraces": subraces or [],
        },
    }


SEED_ENTRIES = [
    race_entry(
        "Human",
        "Humans are adaptable people found across many cultures, known for ambition, versatility, and broad talents.",
        ["ancestry", "versatile", "people"],
        "Humans are the most widespread and culturally varied people in many DND worlds. They mature quickly, build kingdoms and frontier towns with equal energy, and are often driven by ambition, curiosity, faith, or the desire to leave a lasting mark.",
        "人类是许多 DND 世界中分布最广、文化差异最大的种族。他们成长较快，既能建立王国，也能开拓边境城镇，常被野心、好奇心、信仰或留下功绩的愿望驱动。",
        "A human character can come from almost any social class or tradition, so their personality is usually shaped more by homeland, background, and personal goals than by a single shared culture. They fit nearly every class and are easy to connect to local politics, guilds, temples, armies, and settlements.",
        "人类角色可以来自几乎任何阶层和传统，因此性格通常更受家乡、背景和个人目标影响，而不是由单一文化决定。他们适合几乎所有职业，也很容易和地方政治、行会、神殿、军队或定居点建立联系。",
        {
            "ability_score": {"en": "+1 to all ability scores.", "zh": "所有属性值 +1。"},
            "size": {"en": "Medium.", "zh": "中型。"},
            "speed": {"en": "30 feet.", "zh": "30 尺。"},
            "languages": {"en": "Common and one extra language.", "zh": "通用语，以及一种额外语言。"},
            "features": {"en": "Broad adaptability; variant human can be added later as an optional rule.", "zh": "适应性强；变体人类可在后续作为可选规则加入。"},
        },
    ),
    race_entry(
        "Elf",
        "Elves are graceful, long-lived folk with keen senses, magical traditions, and ties to ancient forests or courts.",
        ["ancestry", "keen senses", "magic"],
        "Elves are long-lived, perceptive people whose lives often span centuries. Their communities may be tied to ancient forests, refined cities, hidden courts, or magical traditions, and they often see events through a wider historical lens than shorter-lived folk.",
        "精灵寿命漫长、感官敏锐，生命常以世纪计算。他们的社群可能与古老森林、优雅城邦、隐秘宫廷或魔法传统相连，往往会用比短寿种族更长远的历史视角看待事件。",
        "Elf characters often balance beauty, discipline, memory, and distance from the concerns of younger peoples. Some are serene and artistic, some are proud scholars or duelists, and others are wanderers trying to understand a changing world beyond elven lands.",
        "精灵角色常在优雅、纪律、漫长记忆以及与年轻种族的距离感之间取得平衡。有些宁静而富有艺术气质，有些是骄傲的学者或剑客，也有人离开精灵领地，试图理解变化中的世界。",
        {
            "ability_score": {"en": "+2 Dexterity.", "zh": "敏捷 +2。"},
            "size": {"en": "Medium.", "zh": "中型。"},
            "speed": {"en": "30 feet.", "zh": "30 尺。"},
            "languages": {"en": "Common and Elvish.", "zh": "通用语和精灵语。"},
            "features": {"en": "Darkvision, keen senses, fey ancestry, trance; subrace adds further traits.", "zh": "黑暗视觉、敏锐感官、精类血统、冥想；亚种会提供额外特性。"},
        },
        [
            {"name": "High Elf", "zh": "高等精灵"},
            {"name": "Wood Elf", "zh": "木精灵"},
            {"name": "Drow", "zh": "卓尔"},
        ],
    ),
    race_entry(
        "Dwarf",
        "Dwarves are sturdy folk associated with stonework, endurance, clan loyalty, and skill with tools and arms.",
        ["ancestry", "endurance", "craft"],
        "Dwarves are tough, tradition-minded people famous for endurance, clan bonds, stonework, mining, and metalcraft. Their halls and strongholds often preserve old grudges, honored lineages, masterwork tools, and stories carved into stone.",
        "矮人坚韧、重视传统，以耐力、氏族纽带、石工、采矿和金属工艺闻名。他们的大厅和要塞常保存古老恩怨、荣耀血脉、精良工具，以及刻在石头上的故事。",
        "A dwarf character may be loyal to clan and craft, but that does not make them simple or predictable. They can be grim defenders, practical merchants, exiles seeking lost holds, priests of ancestral gods, or artisans who treat every weapon and wall as a moral statement.",
        "矮人角色可能忠于氏族与工艺，但并不因此单调。他们可以是严肃的守卫、务实的商人、寻找失落要塞的流亡者、祖灵神祇的祭司，或把每件武器和每堵墙都视为信念表达的工匠。",
        {
            "ability_score": {"en": "+2 Constitution.", "zh": "体质 +2。"},
            "size": {"en": "Medium.", "zh": "中型。"},
            "speed": {"en": "25 feet; not reduced by heavy armor.", "zh": "25 尺；不会因重甲降低速度。"},
            "languages": {"en": "Common and Dwarvish.", "zh": "通用语和矮人语。"},
            "features": {"en": "Darkvision, dwarven resilience, combat training, tool proficiency, stonecunning; subrace adds further traits.", "zh": "黑暗视觉、矮人韧性、战斗训练、工具熟练、石工知识；亚种会提供额外特性。"},
        },
        [
            {"name": "Hill Dwarf", "zh": "丘陵矮人"},
            {"name": "Mountain Dwarf", "zh": "山地矮人"},
        ],
    ),
    race_entry(
        "Halfling",
        "Halflings are small, nimble people known for courage, luck, practical kindness, and a talent for staying out of danger.",
        ["ancestry", "small", "lucky", "nimble"],
        "Halflings are small folk who often value comfort, community, food, stories, and the safety of home, but their modest lives can hide remarkable courage. Their luck and agility help them survive dangers that would overwhelm larger heroes.",
        "半身人体型矮小，常重视舒适、社群、食物、故事和家园安全，但朴素生活背后也可能藏着惊人的勇气。他们的幸运与灵巧让他们能从更强大的危险中生还。",
        "A halfling adventurer may be a cheerful traveler, a reluctant hero, a bold burglar, or a loyal friend who refuses to abandon companions. Their stories often contrast ordinary habits with extraordinary nerve when danger reaches the doorstep.",
        "半身人冒险者可以是愉快的旅人、不情愿的英雄、大胆的潜入者，或绝不抛弃伙伴的忠诚朋友。他们的故事常把平凡生活习惯与危急关头的非凡胆量放在一起。",
        {
            "ability_score": {"en": "+2 Dexterity.", "zh": "敏捷 +2。"},
            "size": {"en": "Small.", "zh": "小型。"},
            "speed": {"en": "25 feet.", "zh": "25 尺。"},
            "languages": {"en": "Common and Halfling.", "zh": "通用语和半身人语。"},
            "features": {"en": "Lucky, brave, halfling nimbleness; subrace adds further traits.", "zh": "幸运、勇敢、半身人灵巧；亚种会提供额外特性。"},
        },
        [
            {"name": "Lightfoot", "zh": "轻足半身人"},
            {"name": "Stout", "zh": "强壮半身人"},
        ],
    ),
    race_entry(
        "Dragonborn",
        "Dragonborn carry draconic heritage, marked by proud clans, elemental breath weapons, and a strong sense of honor.",
        ["ancestry", "dragon", "breath weapon", "honor"],
        "Dragonborn are shaped by draconic ancestry, visible in their scaled bodies, powerful presence, and elemental breath. Many dragonborn communities emphasize clan, reputation, honor, and the difficult question of what it means to inherit a dragon's legacy.",
        "龙裔拥有龙族血脉，鳞片身躯、强烈存在感和元素吐息都体现了这种传承。许多龙裔社群重视氏族、名誉和荣誉，也常思考继承龙之遗产究竟意味着什么。",
        "A dragonborn character can be a proud champion, a clan exile, a disciplined soldier, or someone trying to define honor on their own terms. Their draconic ancestry gives strong visual identity and a natural link to ancient powers, rival dragons, or elemental threats.",
        "龙裔角色可以是骄傲的勇士、氏族流亡者、纪律严明的士兵，或试图按自己方式定义荣誉的人。龙族血统带来鲜明外观，也自然连接古老力量、敌对巨龙或元素威胁。",
        {
            "ability_score": {"en": "+2 Strength, +1 Charisma.", "zh": "力量 +2，魅力 +1。"},
            "size": {"en": "Medium.", "zh": "中型。"},
            "speed": {"en": "30 feet.", "zh": "30 尺。"},
            "languages": {"en": "Common and Draconic.", "zh": "通用语和龙语。"},
            "features": {"en": "Draconic ancestry, breath weapon, damage resistance based on ancestry.", "zh": "龙族血统、吐息武器，以及由龙族血统决定的伤害抗性。"},
        },
        [
            {"name": "Black/Blue/Brass/Bronze/Copper/Gold/Green/Red/Silver/White ancestry", "zh": "黑/蓝/黄铜/青铜/赤铜/金/绿/红/银/白龙血统"},
        ],
    ),
    race_entry(
        "Gnome",
        "Gnomes are small, curious folk with lively minds, inventive habits, and natural affinity for illusion or tinkering.",
        ["ancestry", "small", "curious", "illusion", "tinkering"],
        "Gnomes are energetic, clever, and intensely curious. They often delight in invention, hidden knowledge, jokes, illusions, gems, mechanisms, or small wonders that other people overlook, and their communities can feel bright, busy, and eccentric.",
        "侏儒精力旺盛、聪慧且好奇心极强。他们常热爱发明、隐秘知识、玩笑、幻术、宝石、机械，或其他人容易忽略的小奇迹；他们的社群往往明亮、忙碌而古怪。",
        "A gnome character is well suited to scholars, illusionists, inventors, scouts, and problem-solvers. Their small size rarely means small ambitions; many gnomes treat the world as a puzzle box waiting to be opened, improved, or cheerfully disrupted.",
        "侏儒角色很适合学者、幻术师、发明家、斥候和解决问题的人。体型小并不代表志向小；许多侏儒把世界视为等待开启、改良或愉快搅动的谜盒。",
        {
            "ability_score": {"en": "+2 Intelligence.", "zh": "智力 +2。"},
            "size": {"en": "Small.", "zh": "小型。"},
            "speed": {"en": "25 feet.", "zh": "25 尺。"},
            "languages": {"en": "Common and Gnomish.", "zh": "通用语和侏儒语。"},
            "features": {"en": "Darkvision, gnome cunning; subrace adds further traits.", "zh": "黑暗视觉、侏儒狡黠；亚种会提供额外特性。"},
        },
        [
            {"name": "Forest Gnome", "zh": "森林侏儒"},
            {"name": "Rock Gnome", "zh": "岩侏儒"},
        ],
    ),
    race_entry(
        "Half-Elf",
        "Half-elves blend human adaptability with elven grace, often moving between cultures with charm and versatility.",
        ["ancestry", "elf", "human", "versatile", "charisma"],
        "Half-elves combine human flexibility with elven grace and long perspective. They often live between communities, welcomed and misunderstood in equal measure, which can make them skilled negotiators, wanderers, artists, diplomats, or outsiders.",
        "半精灵结合了人类的适应力与精灵的优雅和长远视角。他们常生活在不同社群之间，既可能被欢迎也可能被误解，因此很适合成为谈判者、旅人、艺术家、外交家或局外人。",
        "A half-elf character can lean toward either side of their heritage or reject both expectations. Their natural social talent and broad skills make them flexible party members, and their personal stories often involve identity, belonging, and self-definition.",
        "半精灵角色可以更接近血脉中的任一方，也可以拒绝双方期待。他们天生擅长社交且技能广泛，是灵活的队伍成员；个人故事常围绕身份、归属和自我定义展开。",
        {
            "ability_score": {"en": "+2 Charisma, +1 to two other ability scores.", "zh": "魅力 +2，另外两个属性各 +1。"},
            "size": {"en": "Medium.", "zh": "中型。"},
            "speed": {"en": "30 feet.", "zh": "30 尺。"},
            "languages": {"en": "Common, Elvish, and one extra language.", "zh": "通用语、精灵语，以及一种额外语言。"},
            "features": {"en": "Darkvision, fey ancestry, skill versatility.", "zh": "黑暗视觉、精类血统、技能多才。"},
        },
    ),
    race_entry(
        "Half-Orc",
        "Half-orcs combine human drive with orcish strength, resilience, intensity, and a reputation for fearsome endurance.",
        ["ancestry", "orc", "strength", "resilience"],
        "Half-orcs inherit physical power, endurance, and a fierce presence from orcish ancestry, often combined with human adaptability. Many face suspicion or harsh expectations, but those pressures can forge determined survivors, protectors, and warriors.",
        "半兽人继承了兽人血脉带来的力量、耐力和强烈气势，也常兼具人类的适应力。许多半兽人面对猜疑或苛刻期待，但这些压力也能锻造坚定的幸存者、守护者和战士。",
        "A half-orc character does not need to be defined only by anger. They may be disciplined, spiritual, loyal, humorous, or painfully aware of how others see them. Their mechanics support front-line danger, but their roleplaying can explore restraint, pride, family, and chosen honor.",
        "半兽人角色不必只由愤怒定义。他们可以纪律严明、富有灵性、忠诚、幽默，或非常清楚他人如何看待自己。规则上适合前线危险，但角色扮演可以探索克制、骄傲、家庭和自选的荣誉。",
        {
            "ability_score": {"en": "+2 Strength, +1 Constitution.", "zh": "力量 +2，体质 +1。"},
            "size": {"en": "Medium.", "zh": "中型。"},
            "speed": {"en": "30 feet.", "zh": "30 尺。"},
            "languages": {"en": "Common and Orc.", "zh": "通用语和兽人语。"},
            "features": {"en": "Darkvision, menacing, relentless endurance, savage attacks.", "zh": "黑暗视觉、威吓、坚韧不屈、野蛮攻击。"},
        },
    ),
    race_entry(
        "Tiefling",
        "Tieflings bear infernal legacy, often shown through horns, tails, unusual eyes, fire resistance, and innate magic.",
        ["ancestry", "infernal", "magic", "fire resistance"],
        "Tieflings carry an infernal legacy that can appear as horns, tails, unusual skin tones, strange eyes, or a supernatural presence. Their heritage often attracts fear and prejudice, even when the tiefling has no loyalty to fiends or dark powers.",
        "提夫林带有炼狱血脉，外貌可能表现为犄角、尾巴、异色皮肤、奇异眼睛或超自然气质。即使他们并不效忠邪魔或黑暗力量，这份传承也常招来恐惧与偏见。",
        "A tiefling character can be defiant, charming, secretive, devout, rebellious, or simply tired of being judged by appearance. Their innate magic and resistance make them mechanically distinctive, while their story often asks whether bloodline must define destiny.",
        "提夫林角色可以叛逆、迷人、隐秘、虔诚、反抗成规，或只是厌倦了因外貌被评判。他们的天生魔法和抗性让规则表现鲜明，而故事常追问血脉是否必须决定命运。",
        {
            "ability_score": {"en": "+1 Intelligence, +2 Charisma.", "zh": "智力 +1，魅力 +2。"},
            "size": {"en": "Medium.", "zh": "中型。"},
            "speed": {"en": "30 feet.", "zh": "30 尺。"},
            "languages": {"en": "Common and Infernal.", "zh": "通用语和炼狱语。"},
            "features": {"en": "Darkvision, hellish resistance, infernal legacy spells.", "zh": "黑暗视觉、地狱抗性、炼狱遗赠法术。"},
        },
    ),
    {
        "category": "class",
        "name": "Fighter",
        "content": "Fighters are weapon masters who rely on armor, tactics, and repeated attacks to control the battlefield.",
        "tags": ["class", "martial", "weapons"],
    },
    {
        "category": "class",
        "name": "Wizard",
        "content": "Wizards study arcane magic from spellbooks, solving problems with prepared spells, rituals, and knowledge.",
        "tags": ["class", "arcane", "spells"],
    },
    {
        "category": "class",
        "name": "Ranger",
        "content": "Rangers are scouts and hunters who combine martial skill, wilderness expertise, and practical magic.",
        "tags": ["class", "wilderness", "hunter"],
    },
    {
        "category": "background",
        "name": "Soldier",
        "content": "A soldier has military training, understands ranks and discipline, and may have contacts in an army or militia.",
        "tags": ["background", "military", "discipline"],
    },
    {
        "category": "equipment",
        "name": "Longsword",
        "content": "A longsword is a versatile martial melee weapon commonly used with one hand and a shield or two hands for stronger blows.",
        "tags": ["equipment", "weapon", "martial"],
    },
    {
        "category": "spell",
        "name": "Fire Bolt",
        "content": "Fire Bolt is a ranged spell attack cantrip that hurls flame at a creature or object and deals fire damage on a hit.",
        "tags": ["spell", "cantrip", "fire"],
    },
    {
        "category": "condition",
        "name": "Prone",
        "content": "A prone creature is lying down, moves by crawling unless it stands, and changes how nearby and ranged attacks behave.",
        "tags": ["condition", "combat", "movement"],
    },
    {
        "category": "combat",
        "name": "Initiative",
        "content": "Initiative determines the order of turns when combat starts; each participant rolls and acts from highest to lowest result.",
        "tags": ["combat", "turn order", "initiative"],
    },
    {
        "category": "combat",
        "name": "Attack Roll",
        "content": "An attack roll decides whether an attack hits by rolling a d20, adding modifiers, and comparing the result to Armor Class.",
        "tags": ["combat", "attack", "d20"],
    },
    {
        "category": "adventure",
        "name": "Ability Check",
        "content": "An ability check resolves uncertain actions by rolling a d20, adding the relevant ability modifier and proficiency if it applies.",
        "tags": ["adventure", "check", "d20"],
    },
    {
        "category": "setting",
        "name": "Borderlands",
        "content": "The Borderlands are frontier territories where small settlements, old ruins, rival factions, and wild threats overlap.",
        "tags": ["setting", "frontier", "ruins"],
    },
]


class WorldService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def seed_defaults(self) -> None:
        with self.store.connect() as conn:
            for entry in SEED_ENTRIES:
                conn.execute(
                    """
                INSERT INTO world_entries (
                    category, name, content, tags_json, source, page, metadata_json
                )
                VALUES (
                    :category, :name, :content, :tags_json, :source, :page, :metadata_json
                )
                ON CONFLICT(category, name) DO UPDATE SET
                    content = excluded.content,
                    tags_json = excluded.tags_json,
                    source = excluded.source,
                    page = excluded.page,
                    metadata_json = excluded.metadata_json
                    """,
                    {
                        "category": entry["category"],
                        "name": entry["name"],
                        "content": entry["content"],
                        "tags_json": encode_json(entry["tags"]),
                        "source": entry.get("source"),
                        "page": entry.get("page"),
                        "metadata_json": encode_json(entry.get("metadata", {})),
                    },
                )

    def search(self, query: str | None = None, category: str | None = None) -> WorldSearchOut:
        normalized_query = query.strip().lower() if query else None
        normalized_category = category.strip().lower() if category else None

        clauses = []
        values: dict[str, Any] = {}
        if normalized_category:
            clauses.append("LOWER(category) = :category")
            values["category"] = normalized_category
        if normalized_query:
            clauses.append(
                """
                (
                    LOWER(name) LIKE :query
                    OR LOWER(content) LIKE :query
                    OR LOWER(tags_json) LIKE :query
                    OR LOWER(metadata_json) LIKE :query
                )
                """
            )
            values["query"] = f"%{normalized_query}%"

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.store.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM world_entries
                {where}
                ORDER BY category, name
                """,
                values,
            ).fetchall()

        results = [self._map_row(row) for row in rows]
        message = "Found world entries." if results else "No world entries matched the search."
        return WorldSearchOut(query=query, category=category, results=results, message=message)

    def _map_row(self, row: Row) -> WorldEntryOut:
        return WorldEntryOut(
            id=row["id"],
            category=row["category"],
            name=row["name"],
            content=row["content"],
            tags=decode_json(row["tags_json"], []),
            source=row["source"],
            page=row["page"],
            metadata=decode_json(row["metadata_json"], {}),
        )
