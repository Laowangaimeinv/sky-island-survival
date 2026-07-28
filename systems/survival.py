"""生存系统 - 饥饿、生命、使用物品

特性：
- 支持HP恢复、MP恢复、饱食度恢复
- 支持职业卷轴使用
- 支持种子种植
"""

from core.events import event_bus, EVT
from core.world import GameState


class SurvivalSystem:
    """生存系统"""

    def __init__(self, state: GameState):
        self.state = state

    def use_item(self, item_id: str) -> bool:
        """使用消耗品"""
        inv = self.state.inventory
        stats = self.state.player_stats
        item_data = self.state.get_item_data(item_id)

        if not item_data or not inv.has_item(item_id):
            event_bus.emit(EVT.MESSAGE, {"text": f"你没有 {item_data.get('name', item_id) if item_data else item_id}！"})
            return False

        item_type = item_data.get("type")

        if item_type == "food":
            restore = item_data.get("hunger_restore", 0)
            old_hunger = stats.hunger
            stats.hunger = min(stats.max_hunger, stats.hunger + restore)
            actual = stats.hunger - old_hunger

            # 部分食物也恢复HP
            heal = item_data.get("heal", 0)
            healed = 0
            if heal > 0:
                healed = stats.heal(heal)

            inv.remove_item(item_id, 1)
            event_bus.emit(EVT.HUNGER_CHANGED, {"hunger": stats.hunger, "amount": actual})
            msg = f"你吃了{item_data['name']}，饱食度+{actual}"
            if healed > 0:
                msg += f"，HP+{healed}"
            event_bus.emit(EVT.MESSAGE, {"text": msg})
            self.state.advance_turn()
            return True

        elif item_type == "potion":
            heal = item_data.get("heal", 0)
            mana_restore = item_data.get("mana_restore", 0)

            msg_parts = []

            if heal > 0:
                actual = stats.heal(heal)
                msg_parts.append(f"HP+{actual}")

            if mana_restore > 0 and stats.max_mana > 0:
                actual = stats.restore_mana(mana_restore)
                msg_parts.append(f"MP+{actual}")

            inv.remove_item(item_id, 1)
            event_bus.emit(EVT.MESSAGE, {"text": f"你使用了{item_data['name']}，{', '.join(msg_parts)}"})
            self.state.advance_turn()
            return True

        elif item_type == "profession_scroll":
            # 使用职业卷轴
            profession_id = item_data.get("profession_id")
            if profession_id:
                profession = self.state.profession_system.professions.get(profession_id)
                if profession:
                    inv.remove_item(item_id, 1)
                    self.state.profession_system.learn_profession(profession, stats)
                    return True
                else:
                    event_bus.emit(EVT.MESSAGE, {"text": "无效的职业卷轴！"})
                    return False

        elif item_type == "seed":
            # 种植种子
            return self._plant_seed(item_id, item_data)

        event_bus.emit(EVT.MESSAGE, {"text": f"{item_data['name']}无法在此使用"})
        return False

    def _plant_seed(self, item_id: str, item_data: dict) -> bool:
        """种植种子"""
        growth_time = item_data.get("growth_time", 12)
        stages = item_data.get("stages", 4)
        crop_name = item_data["name"].replace("种子", "")

        # 季节加成
        season_effects = self.state.time_system.time.season_info["effects"]
        growth_mult = season_effects.get("growth_mult", 1.0)
        actual_time = max(4, int(growth_time / growth_mult))

        self.state.inventory.remove_item(item_id, 1)
        self.state.time_system.add_farming_plot(item_id, crop_name, actual_time, stages)

        self.state.advance_turn()
        return True

    def eat_cooked_meat(self) -> bool:
        """吃烤肉（快捷方法）"""
        return self.use_item("cooked_meat")

    def use_bandage(self) -> bool:
        """使用绷带"""
        return self.use_item("bandage")
