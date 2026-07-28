"""制作与建造系统"""

from typing import Dict, Optional
from core.events import event_bus, EVT
from core.world import GameState, Building


class CraftSystem:
    """制作系统"""

    def __init__(self, state: GameState):
        self.state = state

    def can_craft(self, recipe: dict) -> tuple[bool, str]:
        """检查是否可以制作，返回(能否制作, 原因)"""
        # 检查解锁条件
        unlock = recipe.get("unlock", "start")
        if unlock not in self.state.unlocked_recipes:
            return False, "尚未解锁此配方"

        # 检查材料
        for item_id, required in recipe.get("ingredients", {}).items():
            if not self.state.inventory.has_item(item_id, required):
                item_data = self.state.get_item_data(item_id)
                name = item_data["name"] if item_data else item_id
                have = self.state.inventory.get_count(item_id)
                return False, f"缺少{name}（需要{required}，拥有{have}）"

        return True, "可以制作"

    def craft_item(self, recipe: dict) -> bool:
        """执行制作"""
        can, reason = self.can_craft(recipe)
        if not can:
            event_bus.emit(EVT.CRAFT_FAILED, {"reason": reason, "recipe": recipe["name"]})
            event_bus.emit(EVT.MESSAGE, {"text": f"制作失败：{reason}"})
            return False

        # 消耗材料
        for item_id, required in recipe.get("ingredients", {}).items():
            self.state.inventory.remove_item(item_id, required)

        # 获得成品
        result_id = recipe["result"]
        amount = recipe.get("amount", 1)
        item_data = self.state.get_item_data(result_id)
        self.state.inventory.add_item(result_id, item_data, amount)

        event_bus.emit(EVT.ITEM_CRAFTED, {
            "item": item_data["name"],
            "amount": amount
        })
        event_bus.emit(EVT.MESSAGE, {"text": f"🔧 制作了 {item_data['name']}×{amount}"})

        return True

    def build_structure(self, recipe: dict) -> bool:
        """建造设施"""
        can, reason = self.can_craft(recipe)
        if not can:
            event_bus.emit(EVT.MESSAGE, {"text": f"建造失败：{reason}"})
            return False

        # 检查是否已建造
        result_id = recipe["result"]
        if result_id in self.state.building_ids:
            event_bus.emit(EVT.MESSAGE, {"text": f"{recipe['name']}已经建造过了！"})
            return False

        # 消耗材料
        for item_id, required in recipe.get("ingredients", {}).items():
            self.state.inventory.remove_item(item_id, required)

        # 建造
        building = Building(
            id=result_id,
            name=recipe["name"],
            desc=recipe.get("desc", "")
        )
        self.state.buildings.append(building)
        self.state.building_ids.add(result_id)

        # 解锁相关配方
        self.state.unlocked_recipes.add(result_id)

        # 建筑效果
        if result_id == "storage":
            self.state.inventory.max_slots += 20
        elif result_id == "wall":
            self.state.player_stats.defense += 2

        event_bus.emit(EVT.BUILDING_BUILT, {
            "building": recipe["name"],
            "desc": recipe.get("desc", "")
        })
        event_bus.emit(EVT.MESSAGE, {"text": f"🏗️ 建造了 {recipe['name']}！{recipe.get('desc', '')}"})

        return True

    def get_available_recipes(self) -> list:
        """获取所有可用配方（含状态）"""
        all_recipes = self.state.get_all_recipes()
        result = []
        for recipe in all_recipes:
            can, reason = self.can_craft(recipe)
            result.append({
                **recipe,
                "can_craft": can,
                "reason": reason
            })
        return result

    def get_available_buildings(self) -> list:
        """获取可建造的建筑"""
        result = []
        for category in self.state.recipes_data.values():
            for recipe in category:
                if recipe.get("result") in [b["id"] for b in self.state.recipes_data.get("buildings", [])]:
                    continue
        # 直接从buildings分类获取
        for recipe in self.state.recipes_data.get("buildings", []):
            unlock = recipe.get("unlock", "start")
            if unlock in self.state.unlocked_recipes:
                can, reason = self.can_craft(recipe)
                already_built = recipe["result"] in self.state.building_ids
                result.append({
                    **recipe,
                    "can_craft": can and not already_built,
                    "reason": "已建造" if already_built else reason
                })
        return result
