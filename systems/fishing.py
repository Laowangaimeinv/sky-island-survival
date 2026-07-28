"""垂钓系统 - 核心产出机制

特性：
- 钓竿有耐久度，每次垂钓消耗1点
- 垂钓需要时间（2小时基础，钓饵可减少）
- 可获得职业卷轴和技能书
- 品质受钓竿、钓饵、天赋影响
"""

import random
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json

from core.events import event_bus, EVT


DATA_DIR = Path(__file__).parent.parent / "data"


def load_gameplay():
    with open(DATA_DIR / "gameplay.json", "r", encoding="utf-8") as f:
        return json.load(f)


class FishingSystem:
    """垂钓系统"""

    def __init__(self, state):
        self.state = state
        self.data = load_gameplay()
        self.chest_tiers = self.data["chest_tiers"]
        self.fishing_rods = self.data["fishing_rods"]
        self.baits = self.data["baits"]

    def start_fishing(self, rod_id: str = "wood_rod", bait_id: str = None) -> Dict:
        """开始垂钓（带时间进度）"""
        # 检查体力
        if self.state.player_stats.hunger <= 5:
            event_bus.emit(EVT.MESSAGE, {"text": "你太饿了，没有力气垂钓...先吃点东西吧。"})
            return {"type": "failed", "reason": "饥饿"}

        # 检查是否已在垂钓
        if self.state.time_system.fishing_progress:
            event_bus.emit(EVT.MESSAGE, {"text": "你已经在垂钓中了，等待结果吧。"})
            return {"type": "failed", "reason": "已在垂钓"}

        # 消耗体力
        self.state.player_stats.hunger = max(0, self.state.player_stats.hunger - 2)

        # 计算钓竿加成
        rod = self.fishing_rods.get(rod_id, self.fishing_rods["wood_rod"])
        rod_bonus = rod.get("tier_bonus", 0)

        # 计算钓饵加成
        bait_bonus = 0
        if bait_id and bait_id in self.baits:
            bait_bonus = self.baits[bait_id].get("tier_bonus", 0)
            # 消耗钓饵
            self.state.inventory.remove_item(bait_id, 1)

        # 开始垂钓（带时间进度）
        self.state.time_system.start_fishing(
            rod_durability=rod.get("durability", -1),
            bait_bonus=bait_bonus
        )

        # 保存垂钓参数
        self.state.time_system.fishing_progress["rod_id"] = rod_id
        self.state.time_system.fishing_progress["bait_bonus"] = bait_bonus
        self.state.time_system.fishing_progress["rod_bonus"] = rod_bonus

        return {"type": "started", "time": self.state.time_system.fishing_progress["total_time"]}

    def complete_fishing(self) -> Dict:
        """完成垂钓并获取奖励"""
        rod_id = "wood_rod"
        bait_bonus = 0
        rod_bonus = 0

        # 从进度中获取参数
        progress = self.state.time_system.fishing_progress
        if progress:
            rod_id = progress.get("rod_id", "wood_rod")
            bait_bonus = progress.get("bait_bonus", 0)
            rod_bonus = progress.get("rod_bonus", 0)

        # 消耗钓竿耐久
        rod_item = None
        for item in self.state.inventory.items:
            if item.item_data.get("tool_type") == "fishing":
                rod_item = item
                break

        if rod_item:
            rod_id_val = None
            for rid, rdata in self.fishing_rods.items():
                if rdata["name"] == rod_item.name:
                    rod_id_val = rid
                    break
            if rod_id_val:
                rod_id = rod_id_val
                rod_bonus = self.fishing_rods.get(rod_id, {}).get("tier_bonus", 0)

            # 消耗耐久（神话钓竿不消耗）
            if rod_item.durability > 0:
                rod_item.durability -= 1
                if rod_item.durability <= 0:
                    event_bus.emit(EVT.MESSAGE, {"text": f"你的{rod_item.name}损坏了！"})

        # 计算天赋加成
        talent_effects = self.state.talent_system.get_passive_effects()
        talent_bonus = 0
        if "fishing_quality" in talent_effects:
            talent_bonus += talent_effects["fishing_quality"]
        if "fishing_rare_bonus" in talent_effects:
            talent_bonus += talent_effects["fishing_rare_bonus"]

        # 职业加成
        prof_effects = {}
        if self.state.profession_system.player_profession:
            prof_effects = self.state.profession_system.player_profession.passive_effects
            if "fishing_quality" in prof_effects:
                talent_bonus += prof_effects["fishing_quality"]

        # 总加成
        total_bonus = rod_bonus + bait_bonus + talent_bonus

        # 抽取宝箱等级
        chest_tier = self._roll_chest_tier(total_bonus)
        chest = self.chest_tiers[chest_tier]

        event_bus.emit(EVT.MESSAGE, {
            "text": f"🎣 钓到了一个 {chest['icon']} {chest['name']}！"
        })

        # 检查钥匙需求
        if chest.get("key_required"):
            key_id = chest.get("key_id", f"key_{chest_tier}")
            if not self.state.inventory.has_item(key_id):
                event_bus.emit(EVT.MESSAGE, {
                    "text": f"需要 {key_id} 来打开这个宝箱！已存入背包。"
                })
                # 将未开的宝箱放入背包
                chest_item_data = {"name": f"未开的{chest['name']}", "stackable": False, "grade": chest_tier}
                self.state.inventory.add_item(f"chest_{chest_tier}", chest_item_data, 1)
                return {"type": "chest_locked", "tier": chest_tier, "chest_name": chest["name"]}
            else:
                # 消耗钥匙
                self.state.inventory.remove_item(key_id, 1)

        # 开箱
        loot = self._open_chest(chest, chest_tier)

        # 检查职业卷轴掉落
        profession_drop = self.state.profession_system.get_profession_drop_from_chest(chest_tier)
        if profession_drop:
            scroll_id = f"profession_scroll_{profession_drop.id}"
            scroll_data = self.state.get_item_data(scroll_id)
            if scroll_data:
                self.state.inventory.add_item(scroll_id, scroll_data, 1)
                event_bus.emit(EVT.MESSAGE, {
                    "text": f"  🎓 获得职业卷轴：{profession_drop.icon} {profession_drop.name}！"
                })
                loot.append({"id": scroll_id, "name": scroll_data["name"], "amount": 1, "special": True})

        # 检查技能书掉落
        skill_drop = self.state.profession_system.get_skill_book_from_chest(chest_tier)
        if skill_drop:
            event_bus.emit(EVT.MESSAGE, {
                "text": f"  📖 获得技能书：{skill_drop.icon} {skill_drop.name}！"
            })
            # 直接学会技能
            self.state.profession_system.learn_skill(skill_drop.id)

        # 推进回合
        self.state.advance_turn()

        return {
            "type": "chest",
            "tier": chest_tier,
            "chest_name": chest["name"],
            "chest_icon": chest["icon"],
            "loot": loot
        }

    def _roll_chest_tier(self, bonus: int) -> str:
        """根据加成抽取宝箱等级"""
        tiers = list(self.chest_tiers.keys())
        weights = [self.chest_tiers[t]["weight"] for t in tiers]

        # 加成提升高品质概率
        if bonus >= 1:
            shift = min(bonus * 5, 20)
            weights[0] = max(5, weights[0] - shift)
            for i in range(1, len(weights)):
                weights[i] += shift / (len(weights) - 1)

        if bonus >= 3:
            for i in range(4, len(weights)):
                weights[i] *= 1.5

        if bonus >= 5:
            weights[-1] = max(weights[-1], 0.5)

        # 天赋额外加成
        talent_effects = self.state.talent_system.get_passive_effects()
        if "fishing_any_item" in talent_effects:
            for i in range(1, len(weights)):
                weights[i] *= 2.0

        return random.choices(tiers, weights=weights, k=1)[0]

    def _open_chest(self, chest: Dict, chest_tier: str) -> List[Dict]:
        """开箱获取物品"""
        loot_pool = chest["loot_pool"]
        total_weight = sum(item["weight"] for item in loot_pool)

        # 决定掉落几件物品
        num_items = random.randint(1, 3)
        if chest["weight"] <= 1:
            num_items = random.randint(2, 4)

        results = []
        for _ in range(num_items):
            roll = random.uniform(0, total_weight)
            cumulative = 0
            chosen = loot_pool[0]
            for item in loot_pool:
                cumulative += item["weight"]
                if roll <= cumulative:
                    chosen = item
                    break

            amount = random.randint(chosen["min"], chosen["max"])

            # 天赋加成
            talent_effects = self.state.talent_system.get_passive_effects()
            if "global_luck_mult" in talent_effects:
                amount = int(amount * talent_effects["global_luck_mult"])

            # 添加到背包
            item_data = self.state.get_item_data(chosen["id"])
            if item_data:
                added = self.state.inventory.add_item(chosen["id"], item_data, amount)
                results.append({
                    "id": chosen["id"],
                    "name": item_data["name"],
                    "amount": added
                })
                event_bus.emit(EVT.MESSAGE, {
                    "text": f"  获得 {item_data['name']} ×{added}"
                })
            else:
                results.append({
                    "id": chosen["id"],
                    "name": chosen["id"],
                    "amount": amount,
                    "special": True
                })
                event_bus.emit(EVT.MESSAGE, {
                    "text": f"  获得 ??? ×{amount}（特殊物品）"
                })

        return results

    def craft_rod(self, rod_id: str) -> bool:
        """制作钓竿"""
        recipes = {
            "iron_rod": {"wood": 5, "iron_ore": 3, "fiber": 5},
            "crystal_rod": {"crystal": 5, "iron_ore": 3, "fiber": 3},
            "void_rod": {"void_stone": 3, "crystal": 5, "iron_ore": 5},
            "mythic_rod": {"void_core": 1, "crystal": 10, "void_stone": 5}
        }

        if rod_id not in recipes:
            return False

        recipe = recipes[rod_id]
        for item_id, qty in recipe.items():
            if not self.state.inventory.has_item(item_id, qty):
                item_data = self.state.get_item_data(item_id)
                name = item_data["name"] if item_data else item_id
                event_bus.emit(EVT.MESSAGE, {"text": f"缺少 {name}×{qty}"})
                return False

        for item_id, qty in recipe.items():
            self.state.inventory.remove_item(item_id, qty)

        rod = self.fishing_rods[rod_id]
        rod_data = self.state.get_item_data(rod_id) or {
            "name": rod["name"], "desc": rod["desc"],
            "type": "tool", "tool_type": "fishing",
            "durability": rod["durability"], "grade": "E"
        }
        self.state.inventory.add_item(rod_id, rod_data, 1)
        event_bus.emit(EVT.MESSAGE, {"text": f"🎣 制作了 {rod['name']}！{rod['desc']}"})
        return True

    def craft_bait(self, bait_id: str) -> bool:
        """制作钓饵"""
        recipes = {
            "basic_bait": {"fiber": 2},
            "ore_bait": {"iron_ore": 2, "fiber": 1},
            "crystal_bait": {"crystal": 1, "fiber": 2},
            "void_bait": {"void_stone": 1, "crystal": 2}
        }

        if bait_id not in recipes:
            return False

        recipe = recipes[bait_id]
        for item_id, qty in recipe.items():
            if not self.state.inventory.has_item(item_id, qty):
                return False

        for item_id, qty in recipe.items():
            self.state.inventory.remove_item(item_id, qty)

        bait = self.baits[bait_id]
        bait_data = self.state.get_item_data(bait_id) or {
            "name": bait["name"], "stackable": True, "max_stack": 20, "grade": "F"
        }
        self.state.inventory.add_item(bait_id, bait_data, 3)
        event_bus.emit(EVT.MESSAGE, {"text": f"制作了 {bait['name']} ×3"})
        return True

    def fish(self, rod_id: str = "wood_rod", bait_id: str = None) -> Dict:
        """兼容旧接口的垂钓方法（直接完成）"""
        result = self.start_fishing(rod_id, bait_id)
        if result["type"] == "failed":
            return result
        # 立即完成
        return self.complete_fishing()
