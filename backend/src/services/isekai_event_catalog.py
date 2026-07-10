from __future__ import annotations

from typing import Any


class IsekaiEventCatalog:
    SEEDS = [
        {
            "id": "fresh_claw_marks",
            "scope": "local",
            "title": "猎径旁发现新鲜爪痕",
            "description": "你在泥地边缘看见几道深爪痕，旁边的灌木被什么沉重的东西压弯。",
            "tags": ["danger", "wildlife"],
            "channels": ["direct_observation", "environment_sign"],
            "impact_context": "附近野兽活动增强，夜间旅行和单独搜索更危险。",
        },
        {
            "id": "cold_spring",
            "scope": "local",
            "title": "石缝里传来冷泉水声",
            "description": "你听见岩石下方有细小水声，潮湿苔藓一路延伸到一处裂缝。",
            "tags": ["resource", "water"],
            "channels": ["direct_observation", "environment_sign"],
            "impact_context": "附近可能存在可取水点，但接近裂缝需要谨慎。",
        },
        {
            "id": "guard_notice",
            "scope": "settlement",
            "title": "镇上贴出临时护卫告示",
            "description": "你从来往旅人那里听说，附近镇子正在招募临时护卫，报酬包括食宿和少量银币。",
            "tags": ["work", "security", "settlement"],
            "channels": ["merchant_news", "notice_board", "tavern_gossip"],
            "impact_context": "附近聚落的治安压力上升，护卫工作和盘查都会变多。",
        },
        {
            "id": "outsider_tax_notice",
            "scope": "settlement",
            "title": "异族税告示钉上集市木柱",
            "description": "一张盖着领主蜡印的告示要求摊贩向外来种族加收异族税，旁边还写着魔灾标记者不得赊账。",
            "tags": ["outsider", "law", "trade", "survival_pressure"],
            "channels": ["direct_observation", "notice_board", "merchant_news"],
            "impact_context": "外来者和非本地种族购买食物、住宿或工具时更容易被加价，NPC 会根据种族和外来者身份改变态度。",
        },
        {
            "id": "temple_taboo_bell",
            "scope": "settlement",
            "title": "神殿敲响禁忌钟",
            "description": "镇中神殿敲响三声短钟，祭司宣布夜色前不得收留来历不明者，否则要向领主巡礼队登记。",
            "tags": ["taboo", "temple", "law", "outsider"],
            "channels": ["direct_observation", "temple_bell", "tavern_gossip"],
            "impact_context": "落脚身份变得重要；旅店、摊主和守卫会追问玩家来源，玩家若无法解释异界身份会提高警戒和住宿难度。",
        },
        {
            "id": "spice_cart",
            "scope": "settlement",
            "title": "香料货车滞留在集市口",
            "description": "商队传来消息，一辆装着异域香料的货车坏在集市口，车主急需帮手。",
            "tags": ["food", "trade", "opportunity"],
            "channels": ["merchant_news", "tavern_gossip"],
            "impact_context": "集市附近出现食材和贸易机会，关注料理或经营的角色更容易接触相关线索。",
        },
        {
            "id": "curfew_patrol_prices",
            "scope": "settlement",
            "title": "宵禁巡逻推高晚市价格",
            "description": "披灰斗篷的巡逻队开始在街口查问陌生人，水囊、干粮和落脚铺位的价格都被临时抬高。",
            "tags": ["patrol", "law", "trade", "survival_pressure", "reputation"],
            "channels": ["direct_observation", "merchant_news", "notice_board"],
            "impact_context": "夜晚行动更危险，物价上涨；玩家的声望、解释身份的方式和是否配合盘查会影响 NPC 报价与警戒。",
        },
        {
            "id": "border_patrol",
            "scope": "regional",
            "title": "边境巡逻队开始封查旧路",
            "description": "你从商旅口中得知，边境巡逻队正在封查几条旧路，理由是近期有失踪传闻。",
            "tags": ["law", "travel", "danger"],
            "channels": ["merchant_news", "tavern_gossip", "magic_message"],
            "impact_context": "区域旅行更容易遇到盘查，绕路会增加时间和补给压力。",
        },
        {
            "id": "lord_marked_outsiders",
            "scope": "regional",
            "title": "领主悬赏登记灾厄征兆",
            "description": "商旅传言领主正在悬赏登记带有陌生口音、异界衣料或异常种族特征的旅人。",
            "tags": ["outsider", "law", "reputation", "survival_pressure"],
            "channels": ["merchant_news", "tavern_gossip", "magic_message"],
            "impact_context": "玩家的异界来客身份会影响区域声望和盘查强度；公开暴露异常身份可能换来赏金猎人、守卫或神殿审问。",
        },
    ]

    def random_candidate(self, turn: dict[str, Any], scope: str, location: str) -> dict[str, Any] | None:
        options = [seed for seed in self.SEEDS if seed["scope"] == scope]
        if not options:
            return None
        index = self._stable_index(turn, len(options))
        seed = options[index]
        tags = list(seed["tags"])
        return {
            "event_type": "world",
            "title": seed["title"],
            "description": seed["description"],
            "scope": seed["scope"],
            "source": "random_world",
            "affected_area": location,
            "preference_tags": [],
            "triggering_action": "",
            "allowed_channels": list(seed["channels"]),
            "impact": {
                "event_id": seed["id"],
                "title": seed["title"],
                "scope": seed["scope"],
                "affected_area": location,
                "tags": tags,
                "dm_context": seed["impact_context"],
            },
        }

    def _stable_index(self, turn: dict[str, Any], option_count: int) -> int:
        text = f"{turn.get('player_input', '')} {self._scene_text(turn)}"
        return sum(ord(char) for char in text) % max(1, option_count)

    def _scene_text(self, turn: dict[str, Any]) -> str:
        scene = turn.get("scene")
        return f"{getattr(scene, 'location', '')} {getattr(scene, 'environment', '')}"
