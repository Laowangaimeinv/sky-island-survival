"""探索系统 - 采集资源、探索事件、岛屿切换"""

import random
from typing import Optional, Dict, List

from core.events import event_bus, EVT
from core.world import GameState, ResourceNode, Island
from core.entities import Creature


class ExploreSystem:
    """探索系统"""

    def __init__(self, state: GameState):
        self.state = state

    def gather_resource(self, node_index: int) -> Optional[Dict]:
        """采集资源"""
        island = self.state.current_island
        available = island.get_available_resources()

        if node_index < 0 or node_index >= len(available):
            event_bus.emit(EVT.MESSAGE, {"text": "无效的资源点！"})
            return None

        node = available[node_index]
        inv = self.state.inventory

        # 检查工具
        tool_type = None
        weapon = inv.get_equipped_weapon()
        if node.tool_required:
            # 检查背包中是否有对应工具
            for item in inv.items:
                if item.item_data.get("tool_type") == node.tool_required:
                    tool_type = node.tool_required
                    break
            if not tool_type:
                event_bus.emit(EVT.MESSAGE, {"text": f"采集{node.name}需要{node.tool_required}类工具！"})
                return None

        # 采集
        amount = node.harvest(tool_type)
        if amount == 0:
            event_bus.emit(EVT.MESSAGE, {"text": f"{node.name}已被采空，需等待刷新。"})
            return None

        item_data = self.state.get_item_data(node.id)
        added = inv.add_item(node.id, item_data, amount)

        result = {
            "resource": node.name,
            "item_id": node.id,
            "item_name": item_data["name"],
            "amount": added,
            "overflow": amount - added
        }

        event_bus.emit(EVT.RESOURCE_GATHERED, result)
        event_bus.emit(EVT.MESSAGE, {
            "text": f"从{node.name}采集了{added}个{item_data['name']}" +
                    (f"（{amount - added}个因背包已满丢失）" if result["overflow"] > 0 else "")
        })

        # 可能触发随机事件
        self._check_random_event()

        self.state.advance_turn()
        return result

    def explore_island(self) -> Optional[Dict]:
        """探索当前岛屿（可能遭遇战斗或事件）"""
        island = self.state.current_island

        if not island.explored:
            island.explored = True
            event_bus.emit(EVT.ISLAND_EXPLORED, {
                "island": island.name,
                "desc": island.desc
            })

        # 随机遭遇：40%概率遭遇敌人
        if island.creature_ids and random.random() < 0.4:
            creature_id = random.choice(island.creature_ids)
            creature = self.state.create_creature(creature_id)
            if creature:
                event_bus.emit(EVT.COMBAT_START, {
                    "creature": creature,
                    "can_flee": True
                })
                return {"type": "combat", "creature": creature}

        # 随机探索事件
        if island.event_ids and random.random() < 0.5:
            event_id = random.choice(island.event_ids)
            return self._trigger_event(event_id)

        # 普通探索
        event_bus.emit(EVT.MESSAGE, {"text": f"你小心翼翼地探索着{island.name}...没有发现什么异常。"})
        self.state.advance_turn()
        return {"type": "nothing"}

    def travel_to_island(self, island_id: str) -> bool:
        """前往另一座空岛"""
        if island_id not in self.state.islands:
            event_bus.emit(EVT.MESSAGE, {"text": "目标空岛不存在！"})
            return False

        target = self.state.islands[island_id]

        # 检查前置条件：需要击败当前岛的守护者
        current = self.state.current_island
        if not current.guardian_defeated and current.guardian_id:
            event_bus.emit(EVT.MESSAGE, {"text": f"你必须先击败{current.name}的守护者才能离开！"})
            return False

        self.state.current_island_id = island_id
        self.state.explored_islands.add(island_id)

        event_bus.emit(EVT.ISLAND_CHANGED, {
            "from": current.name,
            "to": target.name,
            "desc": target.desc
        })
        event_bus.emit(EVT.MESSAGE, {"text": f"你跳上了{target.name}。{target.desc}"})

        # 检查解锁新配方
        if target.level >= 2:
            self.state.unlocked_recipes.add("workbench")
        if target.level >= 3:
            self.state.unlocked_recipes.add("forge")

        self.state.advance_turn()
        return True

    def get_available_islands(self) -> List[Dict]:
        """获取可前往的空岛列表"""
        current = self.state.current_island
        result = []
        for island_id, island in self.state.islands.items():
            if island_id == self.state.current_island_id:
                continue
            can_travel = not (not current.guardian_defeated and current.guardian_id)
            result.append({
                "id": island_id,
                "name": island.name,
                "level": island.level,
                "explored": island_id in self.state.explored_islands,
                "can_travel": can_travel
            })
        return result

    def _trigger_event(self, event_id: str) -> Optional[Dict]:
        """触发探索事件"""
        event_data = None
        for e in self.state.events_data.get("exploration_events", []):
            if e["id"] == event_id:
                event_data = e
                break

        if not event_data:
            return None

        event_bus.emit(EVT.EVENT_TRIGGERED, {
            "id": event_id,
            "name": event_data["name"],
            "desc": event_data["desc"]
        })

        event_type = event_data.get("type")

        if event_type == "loot":
            return self._handle_loot_event(event_data)
        elif event_type == "choice":
            return self._handle_choice_event(event_data)
        elif event_type == "combat":
            return self._handle_combat_event(event_data)
        elif event_type == "danger":
            return self._handle_danger_event(event_data)

        return None

    def _handle_loot_event(self, event_data: dict) -> Dict:
        """处理宝箱类事件"""
        rewards = {}
        for item_id, (min_amt, max_amt) in event_data.get("rewards", {}).items():
            amount = random.randint(min_amt, max_amt)
            item_data = self.state.get_item_data(item_id)
            if item_data:
                self.state.inventory.add_item(item_id, item_data, amount)
                rewards[item_id] = amount

        # 稀有奖励
        if "rare_rewards" in event_data:
            rare_chance = event_data.get("rare_chance", 0.1)
            if random.random() < rare_chance:
                for item_id, (min_amt, max_amt) in event_data["rare_rewards"].items():
                    amount = random.randint(min_amt, max_amt)
                    item_data = self.state.get_item_data(item_id)
                    if item_data:
                        self.state.inventory.add_item(item_id, item_data, amount)
                        rewards[f"稀有:{item_id}"] = amount

        event_bus.emit(EVT.LOOT_OBTAINED, {"rewards": rewards})
        return {"type": "loot", "rewards": rewards}

    def _handle_choice_event(self, event_data: dict) -> Dict:
        """处理选择类事件（返回选项列表，由UI层处理选择）"""
        return {
            "type": "choice",
            "name": event_data["name"],
            "desc": event_data["desc"],
            "choices": event_data.get("choices", [])
        }

    def resolve_choice(self, choice_index: int, choices: list) -> Dict:
        """执行选择结果"""
        if choice_index < 0 or choice_index >= len(choices):
            return {"type": "invalid"}

        choice = choices[choice_index]
        outcome = choice.get("outcome", "safe")

        if outcome == "safe":
            event_bus.emit(EVT.MESSAGE, {"text": "你选择了安全的做法。"})
            return {"type": "safe"}

        # 检查物品消耗
        if "cost" in choice:
            for item_id, qty in choice["cost"].items():
                if not self.state.inventory.has_item(item_id, qty):
                    event_bus.emit(EVT.MESSAGE, {"text": f"你缺少所需物品！"})
                    return {"type": "insufficient"}

        # 成功/失败判定
        success_chance = choice.get("success_chance", 1.0)
        success = random.random() < success_chance

        if success:
            result = choice.get("success", choice.get("reward", {}))
            event_bus.emit(EVT.MESSAGE, {"text": "你的选择得到了回报！"})
        else:
            result = choice.get("fail", {})
            event_bus.emit(EVT.MESSAGE, {"text": "事情的发展出乎你的意料..."})

        # 处理结果
        outcome_data = {"type": "resolved", "success": success}

        # 扣除消耗
        if "cost" in choice:
            for item_id, qty in choice["cost"].items():
                self.state.inventory.remove_item(item_id, qty)

        # 经验奖励
        if "exp" in result:
            leveled = self.state.player_stats.add_exp(result["exp"])
            event_bus.emit(EVT.MESSAGE, {"text": f"获得{result['exp']}点经验！"})
            if leveled:
                event_bus.emit(EVT.LEVEL_UP, {"level": self.state.player_stats.level})

        # 物品奖励
        if "items" in result:
            for item_id, (min_amt, max_amt) in result["items"].items():
                amount = random.randint(min_amt, max_amt)
                item_data = self.state.get_item_data(item_id)
                if item_data:
                    self.state.inventory.add_item(item_id, item_data, amount)

        if "loot" in result:
            for item_id, (min_amt, max_amt) in result["loot"].items():
                amount = random.randint(min_amt, max_amt)
                item_data = self.state.get_item_data(item_id)
                if item_data:
                    self.state.inventory.add_item(item_id, item_data, amount)

        # 伤害
        if "damage" in result:
            dmg = result["damage"] if isinstance(result["damage"], int) else random.randint(*result["damage"])
            actual = self.state.player_stats.take_damage(dmg)
            event_bus.emit(EVT.PLAYER_DAMAGED, {"amount": actual, "source": "事件", "hp": self.state.player_stats.hp})

        return outcome_data

    def _handle_combat_event(self, event_data: dict) -> Dict:
        """处理战斗事件"""
        creatures = []
        for cid in event_data.get("creatures", []):
            c = self.state.create_creature(cid)
            if c:
                creatures.append(c)
        if creatures:
            event_bus.emit(EVT.COMBAT_START, {"creatures": creatures, "can_flee": True})
        return {"type": "combat", "creatures": creatures}

    def _handle_danger_event(self, event_data: dict) -> Dict:
        """处理危险事件"""
        dmg_range = event_data.get("damage", [5, 15])
        damage = random.randint(*dmg_range) if isinstance(dmg_range, list) else dmg_range

        # 逃跑判定
        flee_chance = event_data.get("flee_chance", 0.5)
        if random.random() < flee_chance:
            event_bus.emit(EVT.MESSAGE, {"text": "你成功避开了危险！"})
            # 奖励
            if "bonus" in event_data:
                for item_id, (min_amt, max_amt) in event_data["bonus"].items():
                    amount = random.randint(min_amt, max_amt)
                    item_data = self.state.get_item_data(item_id)
                    if item_data:
                        self.state.inventory.add_item(item_id, item_data, amount)
            return {"type": "escaped"}
        else:
            actual = self.state.player_stats.take_damage(damage)
            event_bus.emit(EVT.PLAYER_DAMAGED, {"amount": actual, "source": "危险", "hp": self.state.player_stats.hp})
            event_bus.emit(EVT.MESSAGE, {"text": f"你受到了{actual}点伤害！"})
            return {"type": "damaged", "damage": actual}

    def _check_random_event(self):
        """采集时随机触发事件"""
        if random.random() < 0.15:  # 15%概率
            island = self.state.current_island
            if island.event_ids:
                event_id = random.choice(island.event_ids)
                self._trigger_event(event_id)
