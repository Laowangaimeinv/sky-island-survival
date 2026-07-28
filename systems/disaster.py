"""灾厄潮系统 - 定期威胁事件"""

import random
from typing import Dict, List, Optional
from pathlib import Path
import json

from core.events import event_bus, EVT
from core.entities import Creature


DATA_DIR = Path(__file__).parent.parent / "data"


def load_gameplay():
    with open(DATA_DIR / "gameplay.json", "r", encoding="utf-8") as f:
        return json.load(f)


class DisasterSystem:
    """灾厄潮系统"""

    def __init__(self, state):
        self.state = state
        self.data = load_gameplay()
        self.disaster_types = self.data["disaster_types"]
        self.last_disaster_day = 0
        self.disaster_count = 0
        self.disaster_history = []

    def check_disaster(self) -> Optional[Dict]:
        """检查是否触发灾厄潮"""
        day = self.state.day
        days_since_last = day - self.last_disaster_day

        # 灾厄周期：每7天一次
        if days_since_last < 7:
            return None

        # 找到适合当前天数的灾厄
        eligible = [d for d in self.disaster_types if d["min_day"] <= day]
        if not eligible:
            return None

        # 选择难度匹配的灾厄（偏向当前天数能触发的最难灾厄）
        disaster = eligible[-1]  # 取最难的

        # 触发灾厄
        self.last_disaster_day = day
        self.disaster_count += 1
        self.disaster_history.append({"day": day, "type": disaster["id"]})

        return disaster

    def start_disaster(self, disaster: Dict) -> List[Creature]:
        """开始灾厄潮"""
        event_bus.emit(EVT.MESSAGE, {
            "text": f"\n{'='*50}"
        })
        event_bus.emit(EVT.MESSAGE, {
            "text": f"  ⚠️ 灾厄潮来袭！"
        })
        event_bus.emit(EVT.MESSAGE, {
            "text": f"  {disaster['name']}"
        })
        event_bus.emit(EVT.MESSAGE, {
            "text": f"{'='*50}"
        })

        # 生成敌人
        enemies = []
        for spawn in disaster["creatures"]:
            count = random.randint(spawn["count"][0], spawn["count"][1])
            for _ in range(count):
                creature = self.state.create_creature(spawn["id"])
                if creature:
                    enemies.append(creature)

        if enemies:
            names = ", ".join(f"{e.name}" for e in enemies)
            event_bus.emit(EVT.MESSAGE, {
                "text": f"  敌人出现了：{names}"
            })

        return enemies

    def resolve_disaster(self, victory: bool, disaster: Dict) -> Dict:
        """灾厄潮结算"""
        result = {
            "victory": victory,
            "day": self.state.day,
            "type": disaster["name"]
        }

        if victory:
            exp_reward = disaster.get("reward_exp", 50)
            self.state.player_stats.add_exp(exp_reward)

            # 灾厄积分
            points = exp_reward // 10
            result["points"] = points

            event_bus.emit(EVT.MESSAGE, {
                "text": f"\n  ✅ 灾厄潮被击退！"
            })
            event_bus.emit(EVT.MESSAGE, {
                "text": f"  获得 {exp_reward} 经验，{points} 灾厄积分"
            })

            # 额外奖励
            if self.disaster_count % 5 == 0:
                # 每5次灾厄额外奖励
                item_data = self.state.get_item_data("island_crystal")
                if item_data:
                    self.state.inventory.add_item("island_crystal", item_data, 1)
                    event_bus.emit(EVT.MESSAGE, {"text": "  🎁 额外奖励：空岛水晶 ×1"})
        else:
            event_bus.emit(EVT.MESSAGE, {
                "text": f"\n  ❌ 灾厄潮造成了严重破坏..."
            })
            # 建筑受损
            if self.state.buildings:
                damaged = random.choice(self.state.buildings)
                event_bus.emit(EVT.MESSAGE, {
                    "text": f"  {damaged.name} 受到了损坏！"
                })

        return result

    def get_next_disaster_info(self) -> Dict:
        """获取下次灾厄信息"""
        day = self.state.day
        days_until = 7 - (day - self.last_disaster_day)

        eligible = [d for d in self.disaster_types if d["min_day"] <= day + days_until]
        next_type = eligible[-1] if eligible else None

        return {
            "days_until": max(0, days_until),
            "expected_type": next_type["name"] if next_type else "未知",
            "disaster_count": self.disaster_count
        }
