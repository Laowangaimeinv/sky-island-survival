"""GameEngine - 游戏引擎层

位于 UI 和 Systems 之间，负责：
- 接收 InputAction 并分发给对应系统
- 管理游戏状态（世界、玩家）
- 收集事件并返回给 UI
- 未来：网络同步、回放

v2 新增模块，与 main.py 的 TextUI 并行存在。
TextUI 逐步迁移为调用 GameEngine API。
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from core.events import event_bus, EVT, InputAction, ActionType, DisplayEvent, GameEvent
from core.entities import (
    Player, Stats, Inventory, Equipment, EquipSlot,
    Creature, IslandPosition, GRADE_CONFIG,
)
from core.world import GameState, Island


class GameEngine:
    """游戏引擎 - 纯逻辑层，不含任何 UI 代码

    职责：
    1. 管理玩家和世界状态
    2. 接收 InputAction，分发给系统处理
    3. 收集产生的事件（包括展示事件）
    4. 提供查询接口供 UI 使用

    使用方式：
        engine = GameEngine()
        events = engine.submit_action(InputAction("player1", ActionType.FISH))
        for event in events:
            # 处理事件...
    """

    def __init__(self):
        self.world = GameState()
        self.players: Dict[str, Player] = {}
        self.display_events: List[DisplayEvent] = []  # 待处理的展示事件

        # 创建默认玩家
        self.local_player = Player(
            id="local",
            name="求生者",
            stats=self.world.player_stats,
            inventory=self.world.inventory,
        )
        self.players["local"] = self.local_player

    def submit_action(self, action: InputAction) -> List[GameEvent]:
        """提交玩家操作，返回产生的事件列表

        这是引擎的核心接口。所有玩家操作都通过此方法提交。
        多人模式下，服务器接收 InputAction 后调用此方法。
        """
        self.display_events.clear()
        event_bus.emit(EVT.ACTION_SUBMITTED, action.to_dict())

        handler = self._get_handler(action.action_type)
        if handler:
            events = handler(action)
        else:
            event_bus.emit(EVT.ACTION_REJECTED, {
                "reason": f"未知操作: {action.action_type.value}"
            })
            events = []

        event_bus.emit(EVT.ACTION_PROCESSED, {
            "action": action.action_type.value,
            "event_count": len(events),
        })
        return events

    def _get_handler(self, action_type: ActionType):
        """获取操作对应的处理函数"""
        handlers = {
            ActionType.FISH: self._handle_fish,
            ActionType.GATHER: self._handle_gather,
            ActionType.USE_ITEM: self._handle_use_item,
            ActionType.CRAFT: self._handle_craft,
            ActionType.BUILD: self._handle_build,
            ActionType.PLANT: self._handle_plant,
            ActionType.HARVEST: self._handle_harvest,
            ActionType.EXPLORE: self._handle_explore,
            ActionType.TRAVEL: self._handle_travel,
            ActionType.ATTACK: self._handle_attack,
            ActionType.DEFEND: self._handle_defend,
            ActionType.USE_SKILL: self._handle_use_skill,
            ActionType.FLEE: self._handle_flee,
            ActionType.EQUIP: self._handle_equip,
            ActionType.UNEQUIP: self._handle_unequip,
            ActionType.ADVANCE_TIME: self._handle_advance_time,
        }
        return handlers.get(action_type)

    # === 操作处理函数 ===

    def _handle_fish(self, action: InputAction) -> List:
        """处理垂钓操作"""
        from systems.fishing import FishingSystem
        fishing = FishingSystem(self.world)
        rod_id = action.params.get("rod_id", "wood_rod")

        # 播放垂钓动画
        self.display_events.append(Display.fishing_anim(2.0))

        result = fishing.start_fishing(rod_id)
        return [("fishing_started", result)]

    def _handle_gather(self, action: InputAction) -> List:
        """处理采集操作"""
        from systems.explore import ExploreSystem
        explore = ExploreSystem(self.world)
        resource_idx = action.params.get("resource_idx", 0)

        result = explore.gather_resource(resource_idx)
        return [("gathered", result)]

    def _handle_use_item(self, action: InputAction) -> List:
        """处理使用物品操作"""
        from systems.survival import SurvivalSystem
        survival = SurvivalSystem(self.world)
        item_id = action.params.get("item_id", "")

        result = survival.use_item(item_id)
        return [("item_used", {"item_id": item_id, "result": result})]

    def _handle_craft(self, action: InputAction) -> List:
        """处理制作操作"""
        from systems.craft import CraftSystem
        craft = CraftSystem(self.world)
        recipe = action.params.get("recipe", {})

        result = craft.craft_item(recipe)
        return [("crafted", result)]

    def _handle_build(self, action: InputAction) -> List:
        """处理建造操作"""
        from systems.craft import CraftSystem
        craft = CraftSystem(self.world)
        building = action.params.get("building", {})

        result = craft.build_structure(building)
        return [("built", result)]

    def _handle_plant(self, action: InputAction) -> List:
        """处理种植操作"""
        seed_id = action.params.get("seed_id", "")
        result = self.world.time_system.plant_crop(seed_id)
        return [("planted", {"seed_id": seed_id, "result": result})]

    def _handle_harvest(self, action: InputAction) -> List:
        """处理收获操作"""
        plot_idx = action.params.get("plot_idx", 0)
        result = self.world.time_system.harvest_crop(plot_idx)
        if result:
            crop_data = self.world.get_item_data(result["crop_id"])
            if crop_data:
                self.world.inventory.add_item(result["crop_id"], crop_data, result["yield"])
        return [("harvested", result)]

    def _handle_explore(self, action: InputAction) -> List:
        """处理探索操作"""
        from systems.explore import ExploreSystem
        explore = ExploreSystem(self.world)

        result = explore.explore_island()
        if result and result.get("type") == "combat":
            creature = result["creature"]
            # 播放战斗开始动画
            self.display_events.append(Display.combat_anim("encounter"))
            return [("combat_encounter", {"creature": creature})]
        elif result and result.get("type") == "choice":
            return [("event_choice", result)]
        return [("explored", result)]

    def _handle_travel(self, action: InputAction) -> List:
        """处理旅行操作"""
        from systems.explore import ExploreSystem
        explore = ExploreSystem(self.world)
        island_id = action.params.get("island_id", "")

        # 播放场景切换动画
        self.display_events.append(Display.transition_fade(1.0))

        explore.travel_to_island(island_id)
        return [("traveled", {"island_id": island_id})]

    def _handle_attack(self, action: InputAction) -> List:
        """处理战斗攻击操作"""
        from systems.combat import CombatSystem
        combat = CombatSystem(self.world)
        target_idx = action.params.get("target_idx", 0)

        # 播放攻击动画和音效
        self.display_events.append(Display.combat_anim("slash"))
        self.display_events.append(Display.hit_sfx())
        self.display_events.append(Display.screen_shake(0.3))

        result = combat.player_attack(target_idx)
        return [("attack", result)]

    def _handle_defend(self, action: InputAction) -> List:
        """处理防御操作"""
        from systems.combat import CombatSystem
        combat = CombatSystem(self.world)
        result = combat.player_defend()
        return [("defend", result)]

    def _handle_use_skill(self, action: InputAction) -> List:
        """处理使用技能操作"""
        from systems.combat import CombatSystem
        combat = CombatSystem(self.world)
        skill_id = action.params.get("skill_id", "")
        target_idx = action.params.get("target_idx", 0)

        # 播放技能动画
        self.display_events.append(Display.combat_anim("skill"))

        result = combat.player_skill_attack(skill_id, target_idx)
        return [("skill_used", result)]

    def _handle_flee(self, action: InputAction) -> List:
        """处理逃跑操作"""
        from systems.combat import CombatSystem
        combat = CombatSystem(self.world)
        result = combat.player_flee()
        return [("flee", {"success": result})]

    def _handle_equip(self, action: InputAction) -> List:
        """处理装备操作"""
        item_id = action.params.get("item_id", "")
        slot_name = action.params.get("slot", "weapon")

        try:
            slot = EquipSlot(slot_name)
        except ValueError:
            return [("equip_failed", {"reason": f"无效槽位: {slot_name}"})]

        # 从背包找到物品
        target_item = None
        for item in self.world.inventory.items:
            if item.item_id == item_id:
                target_item = item
                break

        if not target_item:
            return [("equip_failed", {"reason": "物品不存在"})]

        # 卸下旧装备
        old = self.local_player.equipment.equip(target_item, slot)
        if old:
            self.world.inventory.add_item(
                old.item_id, old.item_data, old.quantity, grade=old.grade
            )

        # 从背包移除新装备
        self.world.inventory.remove_item(item_id, 1)

        event_bus.emit(EVT.ITEM_EQUIPPED, {"item_id": item_id, "slot": slot_name})
        return [("equipped", {"item_id": item_id, "slot": slot_name})]

    def _handle_unequip(self, action: InputAction) -> List:
        """处理卸下装备操作"""
        slot_name = action.params.get("slot", "weapon")
        try:
            slot = EquipSlot(slot_name)
        except ValueError:
            return [("unequip_failed", {"reason": f"无效槽位: {slot_name}"})]

        item = self.local_player.equipment.unequip(slot)
        if item:
            self.world.inventory.add_item(
                item.item_id, item.item_data, item.quantity, grade=item.grade
            )
            event_bus.emit(EVT.ITEM_UNEQUIPPED, {"slot": slot_name})
            return [("unequipped", {"slot": slot_name, "item_id": item.item_id})]
        return [("unequip_failed", {"reason": "槽位为空"})]

    def _handle_advance_time(self, action: InputAction) -> List:
        """处理时间推进操作"""
        hours = action.params.get("hours", 1)
        for _ in range(hours):
            self.world.advance_turn()
        return [("time_advanced", {"hours": hours})]

    # === 查询接口 ===

    def get_player_status(self) -> Dict:
        """获取玩家状态摘要"""
        p = self.local_player
        return {
            "hp": p.stats.hp, "max_hp": p.stats.max_hp,
            "hunger": p.stats.hunger, "max_hunger": p.stats.max_hunger,
            "mana": p.stats.mana, "max_mana": p.stats.max_mana,
            "atk": p.total_atk, "defense": p.total_def,
            "level": p.stats.level, "exp": p.stats.exp,
            "exp_to_next": p.stats.exp_to_next,
            "crit_chance": p.crit_chance,
            "island": p.position.island_id,
            "profession_id": p.profession_id,
            "talent_id": p.talent_id,
        }

    def get_display_events(self) -> List[DisplayEvent]:
        """获取待处理的展示事件"""
        return list(self.display_events)

    def get_save_data(self) -> Dict:
        """获取存档数据"""
        save = self.world.save_state()
        save["player"] = self.local_player.to_dict()
        return save

    def load_save_data(self, data: Dict):
        """加载存档数据"""
        if "player" in data:
            player_data = data["player"]
            self.local_player = Player.from_dict(player_data, self.world.all_items)
            self.players["local"] = self.local_player
            # 同步引用
            self.world.player_stats = self.local_player.stats
            self.world.inventory = self.local_player.inventory
