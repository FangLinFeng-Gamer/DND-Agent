import assert from "node:assert/strict";
import test from "node:test";

globalThis.window = {
  location: { pathname: "/" },
  localStorage: {
    getItem: () => "zh-CN",
    setItem: () => {},
  },
};
globalThis.document = {
  documentElement: {},
  querySelectorAll: () => [],
};

const game = await import("../../frontend/static/js/game.js?v=isekai-world-events-test");

test("summarizes known isekai world events from adventure payload", () => {
  const event = {
    title: "营地记住了陌生料理的香味",
    description: "热食吸引了附近的人。",
    importance: 3,
    metadata: {
      scope: "local",
      source: "player_triggered",
      knowledge_channel: "direct_observation",
      affected_area: "雾林边境",
      preference_tags: ["美食", "社交"],
    },
  };

  const events = game.getIsekaiKnownWorldEvents({
    messages: [{ role: "dm", content: "这是一段 DM 回复，不应该作为世界事件展示。" }],
    world_events: [event],
  });
  const summary = game.summarizeIsekaiWorldEvent(events[0]);

  assert.equal(events.length, 1);
  assert.equal(summary.title, "营地记住了陌生料理的香味");
  assert.equal(summary.description, "热食吸引了附近的人。");
  assert.deepEqual(summary.meta, ["本地", "直接目击", "玩家行动触发", "重要度 3"]);
  assert.equal(summary.affectedArea, "雾林边境");
  assert.deepEqual(summary.tags, ["美食", "社交"]);
});
