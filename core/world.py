"""世界管理 - 空岛、资源点、游戏状态
管理整个游戏世界的运行状态。
2D版中，本模块的坐标/区域数据可直接映射到2D场景。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import json
import random
from pathlib import Path

from .entities import Stats, Inventory, Equipment, EquipSlot, Creature, Player
from .events import event_bus, EVT
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from systems.talent import TalentSystem
from systems.profession import ProfessionSystem
from systems.time_system import TimeSystem


DATA_DIR = Path(__file__).parent.parent / "data"


def load_json(filename: str) -> dict:
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class ResourceNode:
    """资源点"""
    id: str           # 资源类型ID（如 "wood"）
    name: str         # 显示名（如 "枯树"）
    min_yield: int
    max_yield: int
    tool_required: Optional[str] = None  # 需要的工具类型
    respawn_turns: int = 5
    remaining_turns: int = 0  # 采集后需等待的回合数

    @property
    def available(self) -> bool:
        return self.remaining_turns == 0

    def harvest(self, tool_type: Optional[str] = None) -> int:
        """采集资源，返回获得数量"""
        if not self.available:
            return 0
        if self.tool_required and tool_type != self.tool_required:
            return 0
        amount = random.randint(self.min_yield, self.max_yield)
        self.remaining_turns = self.respawn_turns
        return amount

    def tick(self):
        """回合推进"""
        if self.remaining_turns > 0:
            self.remaining_turns -= 1


@dataclass
class Building:
    """已建造的建筑"""
    id: str
    name: str
    desc: str


@dataclass
class Island:
    """空岛"""
    id: str
    name: str
    level: int
    desc: str
    resources: List[ResourceNode] = field(default_factory=list)
    creature_ids: List[str] = field(default_factory=list)
    guardian_id: str = ""
    event_ids: List[str] = field(default_factory=list)
    explored: bool = False
    guardian_defeated: bool = False

    def get_available_resources(self) -> List[ResourceNode]:
        return [r for r in self.resources if r.available]


class GameState:
    """游戏状态管理器 - 核心类"""

    def __init__(self):
        # 加载数据
        self.items_data = load_json("items.json")
        self.recipes_data = load_json("recipes.json")
        self.creatures_data = load_json("creatures.json")
        self.islands_data = load_json("islands.json")
        self.events_data = load_json("events.json")
        self.gameplay_data = load_json("gameplay.json")

        # 合并所有物品数据
        self.all_items = {}
        for category in self.items_data.values():
            if isinstance(category, dict):
                self.all_items.update(category)

        # 玩家实体（v2: 统一为Player对象）
        self.player = Player()
        # 向后兼容：保留旧引用
        self.player_stats = self.player.stats
        self.inventory = self.player.inventory
        self.buildings: List[Building] = []
        self.building_ids: set = set()
        self.talent_system = TalentSystem()
        self.profession_system = ProfessionSystem()
        self.time_system = TimeSystem()

        # 世界状态
        self.islands: Dict[str, Island] = {}
        self.current_island_id: str = ""
        self.turn: int = 0
        self.day: int = 1
        self.explored_islands: set = set()
        self.unlocked_recipes: set = {"start"}

        # 初始化世界
        self._init_islands()

        # 给玩家初始物品
        self.inventory.add_item("wood", self.all_items["wood"], 5)
        self.inventory.add_item("stone", self.all_items["stone"], 3)
        self.inventory.add_item("fiber", self.all_items["fiber"], 3)

    def _init_islands(self):
        """初始化所有空岛"""
        creature_map = {}
        for c in self.creatures_data.get("wild_beasts", []):
            creature_map[c["id"]] = c
        for c in self.creatures_data.get("island_guardians", []):
            creature_map[c["id"]] = c

        for island_data in self.islands_data["islands"]:
            # 创建资源点
            resources = []
            for res in island_data.get("resources", []):
                resources.append(ResourceNode(
                    id=res["id"],
                    name=res["node"],
                    min_yield=res["yield"][0],
                    max_yield=res["yield"][1],
                    tool_required=res.get("tool"),
                    respawn_turns=res.get("respawn_turns", 5)
                ))

            island = Island(
                id=island_data["id"],
                name=island_data["name"],
                level=island_data["level"],
                desc=island_data["desc"],
                resources=resources,
                creature_ids=island_data.get("creatures", []),
                guardian_id=island_data.get("guardian", ""),
                event_ids=island_data.get("events", [])
            )
            self.islands[island.id] = island

        # 起始岛
        self.current_island_id = "starter_island"
        self.explored_islands.add("starter_island")
        self.islands["starter_island"].explored = True

    @property
    def current_island(self) -> Island:
        return self.islands[self.current_island_id]

    def get_item_data(self, item_id: str) -> Optional[Dict]:
        return self.all_items.get(item_id)

    def create_creature(self, creature_id: str) -> Optional[Creature]:
        """创建生物实例"""
        data = None
        for c in self.creatures_data.get("wild_beasts", []):
            if c["id"] == creature_id:
                data = c
                break
        if not data:
            for c in self.creatures_data.get("island_guardians", []):
                if c["id"] == creature_id:
                    data = c
                    break
        if not data:
            return None
        return Creature(
            id=data["id"],
            name=data["name"],
            hp=data["hp"],
            max_hp=data["hp"],
            atk=data["atk"],
            defense=data["def"],
            exp=data["exp"],
            drops=data.get("drops", {}),
            desc=data.get("desc", ""),
            grade=data.get("grade", "F")
        )

    def get_all_recipes(self) -> List[Dict]:
        """获取所有可用配方"""
        recipes = []
        for category in self.recipes_data.values():
            for recipe in category:
                unlock = recipe.get("unlock", "start")
                if unlock in self.unlocked_recipes:
                    recipes.append(recipe)
        return recipes

    def check_building_unlock(self, building_id: str) -> bool:
        """检查建筑是否已建造"""
        return building_id in self.building_ids

    def advance_turn(self):
        """推进一个游戏回合"""
        self.turn += 1

        # 使用时间系统推进
        self.time_system.advance_hour(1)

        # 同步天数
        self.day = self.time_system.time.day + (self.time_system.time.month - 1) * 30

        # 饥饿衰减（每3回合）
        if self.turn % 3 == 0:
            hunger_mult = self.time_system.time.season_info["effects"].get("hunger_mult", 1.0)
            hunger_loss = 1
            if random.random() < (hunger_mult - 1.0):
                hunger_loss = 2
            self.player_stats.hunger = max(0, self.player_stats.hunger - hunger_loss)
            if self.player_stats.hunger == 0:
                dmg = 5
                self.player_stats.hp = max(0, self.player_stats.hp - dmg)
                event_bus.emit(EVT.PLAYER_DAMAGED, {
                    "amount": dmg, "source": "饥饿", "hp": self.player_stats.hp
                })

        # MP自然恢复（每回合恢复1点）
        if self.player_stats.max_mana > 0 and self.player_stats.mana < self.player_stats.max_mana:
            self.player_stats.mana = min(self.player_stats.max_mana, self.player_stats.mana + 1)

        # 资源点刷新
        for island in self.islands.values():
            for node in island.resources:
                node.tick()

        # 职业技能冷却减少
        self.profession_system.tick_cooldowns()

        event_bus.emit(EVT.TURN_PASSED, {"turn": self.turn, "day": self.day})

    def save_state(self) -> Dict:
        """导出游戏状态（用于存档）"""
        return {
            "turn": self.turn,
            "day": self.day,
            "player": self.player.to_dict(),
            "stats": {
                "hp": self.player_stats.hp,
                "max_hp": self.player_stats.max_hp,
                "hunger": self.player_stats.hunger,
                "max_hunger": self.player_stats.max_hunger,
                "mana": self.player_stats.mana,
                "max_mana": self.player_stats.max_mana,
                "atk": self.player_stats.atk,
                "defense": self.player_stats.defense,
                "level": self.player_stats.level,
                "exp": self.player_stats.exp,
                "exp_to_next": self.player_stats.exp_to_next,
                "crit_chance": self.player_stats.crit_chance,
                "crit_damage_mult": self.player_stats.crit_damage_mult,
            },
            "inventory": [
                {"item_id": i.item_id, "quantity": i.quantity, "durability": i.durability, "grade": i.grade}
                for i in self.inventory.items
            ],
            "buildings": list(self.building_ids),
            "current_island": self.current_island_id,
            "explored_islands": list(self.explored_islands),
            "unlocked_recipes": list(self.unlocked_recipes),
            "talent_id": self.talent_system.player_talent.id if self.talent_system.player_talent else None,
            "profession": self.profession_system.save_state(),
            "time": self.time_system.save_state(),
        }
