"""实体定义 - 玩家、生物、物品等游戏对象
纯数据类，不包含渲染逻辑。
2D版只需为每个实体添加Sprite组件即可。

v2: 新增 Player 实体、Equipment 装备槽位、IslandPosition 位置
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import json
import uuid


# ============================================================
# 品阶配置
# ============================================================

GRADE_CONFIG = {
    "F":  {"name": "凡品", "color": "⬜", "stat_mult": 1.0},
    "E":  {"name": "凡品+", "color": "🟩", "stat_mult": 1.1},
    "D":  {"name": "精良", "color": "🟦", "stat_mult": 1.2},
    "C":  {"name": "稀有", "color": "🟪", "stat_mult": 1.4},
    "B":  {"name": "珍贵", "color": "🪙", "stat_mult": 1.6},
    "A":  {"name": "奢华", "color": "🥇", "stat_mult": 1.8},
    "S":  {"name": "传说", "color": "🌈", "stat_mult": 2.0},
    "SS": {"name": "神话", "color": "⭐", "stat_mult": 2.5},
    "SSS":{"name": "至高", "color": "✨", "stat_mult": 3.0},
}


# ============================================================
# 装备槽位
# ============================================================

class EquipSlot(Enum):
    """装备槽位枚举"""
    WEAPON = "weapon"
    HEAD = "head"
    BODY = "body"
    ACCESSORY = "accessory"


# ============================================================
# 属性系统
# ============================================================

@dataclass
class Stats:
    """属性统计"""
    max_hp: int = 100
    hp: int = 100
    max_hunger: int = 100
    hunger: int = 100
    max_mana: int = 0
    mana: int = 0
    atk: int = 5
    defense: int = 0
    level: int = 1
    exp: int = 0
    exp_to_next: int = 50
    crit_chance: float = 0.05
    crit_damage_mult: float = 1.5
    dodge_chance: float = 0.0
    # 精力系统
    max_energy: int = 100
    energy: int = 100
    spirit: int = 10  # 精神属性，影响精力上限和恢复速度

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        """受到伤害，返回实际伤害值"""
        actual = max(1, amount - self.defense)
        self.hp = max(0, self.hp - actual)
        return actual

    def heal(self, amount: int) -> int:
        """恢复生命，返回实际恢复值"""
        actual = min(amount, self.max_hp - self.hp)
        self.hp += actual
        return actual

    def restore_mana(self, amount: int) -> int:
        """恢复魔力"""
        actual = min(amount, self.max_mana - self.mana)
        self.mana += actual
        return actual

    def consume_energy(self, amount: int) -> bool:
        """消耗精力，返回是否足够"""
        if self.energy < amount:
            return False
        self.energy -= amount
        return True

    def regen_energy(self, dt_hours: float = 1.0):
        """精力随时间恢复，dt_hours为经过的小时数
        公式：每小时恢复 = 5 + spirit * 0.5 + max_energy * 0.02
        """
        regen_rate = 5 + self.spirit * 0.5 + self.max_energy * 0.02
        regen_amount = int(regen_rate * dt_hours)
        self.energy = min(self.max_energy, self.energy + regen_amount)

    def calc_max_energy(self):
        """根据精神属性计算精力上限
        公式：max_energy = 80 + spirit * 3 + level * 2
        """
        self.max_energy = 80 + self.spirit * 3 + self.level * 2
        self.energy = min(self.energy, self.max_energy)

    @staticmethod
    def randomize_initial() -> "Stats":
        """创建随机初始属性"""
        import random
        return Stats(
            max_hp=random.randint(90, 120),
            hp=0,  # 后面设置
            max_hunger=100,
            hunger=100,
            atk=random.randint(4, 8),
            defense=random.randint(0, 3),
            spirit=random.randint(6, 15),
        )

    def reset_for_profession(self):
        """转职时重置等级和经验，保留基本属性"""
        self.level = 1
        self.exp = 0
        self.exp_to_next = 50
        # 不重置hp/atk/defense/spirit等基本属性

    def add_exp(self, amount: int) -> bool:
        """增加经验，返回是否升级"""
        self.exp += amount
        if self.exp >= self.exp_to_next:
            self.exp -= self.exp_to_next
            self.level += 1
            self.exp_to_next = int(self.exp_to_next * 1.5)
            self.max_hp += 10
            self.hp = self.max_hp
            self.atk += 2
            self.calc_max_energy()  # 升级重新计算精力上限
            if self.max_mana > 0:
                self.mana = self.max_mana
            return True
        return False

    def to_dict(self) -> Dict:
        return {
            "max_hp": self.max_hp, "hp": self.hp,
            "max_hunger": self.max_hunger, "hunger": self.hunger,
            "max_mana": self.max_mana, "mana": self.mana,
            "atk": self.atk, "defense": self.defense,
            "level": self.level, "exp": self.exp,
            "exp_to_next": self.exp_to_next,
            "crit_chance": self.crit_chance,
            "crit_damage_mult": self.crit_damage_mult,
            "dodge_chance": self.dodge_chance,
            "max_energy": self.max_energy, "energy": self.energy,
            "spirit": self.spirit,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Stats":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ============================================================
# 物品系统
# ============================================================

@dataclass
class InventoryItem:
    """背包物品"""
    item_id: str
    item_data: Dict[str, Any]
    quantity: int = 1
    durability: int = -1  # -1表示无耐久
    grade: str = "F"

    @property
    def name(self) -> str:
        return self.item_data.get("name", self.item_id)

    @property
    def is_stackable(self) -> bool:
        return self.item_data.get("stackable", False)

    @property
    def max_stack(self) -> int:
        return self.item_data.get("max_stack", 1)

    @property
    def is_broken(self) -> bool:
        return self.durability == 0

    @property
    def grade_info(self) -> Dict:
        return GRADE_CONFIG.get(self.grade, GRADE_CONFIG["F"])

    @property
    def grade_name(self) -> str:
        return self.grade_info["name"]

    @property
    def grade_color(self) -> str:
        return self.grade_info["color"]

    @property
    def item_type(self) -> str:
        return self.item_data.get("type", "")

    def to_dict(self) -> Dict:
        return {
            "item_id": self.item_id,
            "quantity": self.quantity,
            "durability": self.durability,
            "grade": self.grade,
        }


class Inventory:
    """背包系统"""

    def __init__(self, max_slots: int = 20):
        self.max_slots = max_slots
        self.items: List[InventoryItem] = []

    def add_item(self, item_id: str, item_data: Dict, quantity: int = 1, grade: str = None) -> int:
        """添加物品，返回实际添加数量"""
        remaining = quantity
        if grade is None:
            grade = item_data.get("grade", "F")

        # 尝试堆叠
        if item_data.get("stackable"):
            for item in self.items:
                if item.item_id == item_id and item.grade == grade and item.quantity < item.max_stack:
                    can_add = min(remaining, item.max_stack - item.quantity)
                    item.quantity += can_add
                    remaining -= can_add
                    if remaining == 0:
                        break

        # 创建新堆叠
        while remaining > 0:
            if len(self.items) >= self.max_slots:
                return quantity - remaining
            stack_size = min(remaining, item_data.get("max_stack", 1))
            dur = item_data.get("durability", -1)
            self.items.append(InventoryItem(
                item_id=item_id, item_data=item_data,
                quantity=stack_size, durability=dur, grade=grade
            ))
            remaining -= stack_size
        return quantity

    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        """移除物品，返回是否成功"""
        total = sum(i.quantity for i in self.items if i.item_id == item_id)
        if total < quantity:
            return False
        remaining = quantity
        to_remove = []
        for item in self.items:
            if item.item_id == item_id:
                if item.quantity <= remaining:
                    remaining -= item.quantity
                    to_remove.append(item)
                else:
                    item.quantity -= remaining
                    remaining = 0
                    break
        for item in to_remove:
            self.items.remove(item)
        return True

    def discard_item(self, index: int, quantity: int = 1) -> tuple:
        """丢弃物品，返回(成功与否, 物品名, 数量)"""
        if index < 0 or index >= len(self.items):
            return False, "", 0
        item = self.items[index]
        actual_qty = min(quantity, item.quantity)
        item_name = item.name
        item.quantity -= actual_qty
        if item.quantity <= 0:
            self.items.remove(item)
        return True, item_name, actual_qty

    def has_item(self, item_id: str, quantity: int = 1) -> bool:
        return sum(i.quantity for i in self.items if i.item_id == item_id) >= quantity

    def get_count(self, item_id: str) -> int:
        return sum(i.quantity for i in self.items if i.item_id == item_id)

    def find_items(self, item_type: str = None) -> List[InventoryItem]:
        """按类型查找物品"""
        if item_type is None:
            return list(self.items)
        return [i for i in self.items if i.item_type == item_type]

    def consume_durability(self, item: InventoryItem, amount: int = 1) -> bool:
        """消耗耐久，返回是否损坏"""
        if item.durability < 0:
            return False
        item.durability = max(0, item.durability - amount)
        return item.durability <= 0

    def to_list(self) -> List[Dict]:
        return [i.to_dict() for i in self.items]


# ============================================================
# 装备系统
# ============================================================

class Equipment:
    """装备槽位系统 - 从背包独立出来"""

    def __init__(self):
        self.slots: Dict[EquipSlot, Optional[InventoryItem]] = {
            EquipSlot.WEAPON: None,
            EquipSlot.HEAD: None,
            EquipSlot.BODY: None,
            EquipSlot.ACCESSORY: None,
        }

    def equip(self, item: InventoryItem, slot: EquipSlot) -> Optional[InventoryItem]:
        """装备物品，返回被替换的旧装备（如果有）"""
        old = self.slots.get(slot)
        self.slots[slot] = item
        return old

    def unequip(self, slot: EquipSlot) -> Optional[InventoryItem]:
        """卸下装备，返回卸下的物品"""
        item = self.slots.get(slot)
        self.slots[slot] = None
        return item

    def get_weapon(self) -> Optional[InventoryItem]:
        return self.slots.get(EquipSlot.WEAPON)

    def get_armor(self) -> Optional[InventoryItem]:
        return self.slots.get(EquipSlot.BODY)

    def get_helmet(self) -> Optional[InventoryItem]:
        return self.slots.get(EquipSlot.HEAD)

    def get_total_def(self) -> int:
        """获取总防御力"""
        total = 0
        for item in self.slots.values():
            if item and not item.is_broken:
                total += item.item_data.get("def", 0)
        return total

    def get_total_atk(self) -> int:
        """获取武器攻击力"""
        weapon = self.get_weapon()
        if weapon and not weapon.is_broken:
            return weapon.item_data.get("atk", 0)
        return 0

    def get_crit_bonus(self) -> float:
        """获取暴击率加成"""
        weapon = self.get_weapon()
        if weapon and not weapon.is_broken:
            return weapon.item_data.get("crit_chance", 0)
        return 0

    def get_crit_mult_bonus(self) -> float:
        """获取暴击伤害加成"""
        weapon = self.get_weapon()
        if weapon and not weapon.is_broken:
            return weapon.item_data.get("crit_damage_mult", 0)
        return 0

    def consume_weapon_durability(self, amount: int = 1) -> bool:
        """消耗武器耐久，返回是否损坏"""
        weapon = self.get_weapon()
        if weapon and weapon.durability > 0:
            weapon.durability = max(0, weapon.durability - amount)
            if weapon.durability <= 0:
                return True
        return False

    def consume_armor_durability(self, amount: int = 1) -> bool:
        """消耗护甲耐久，返回是否损坏"""
        armor = self.get_armor()
        if armor and armor.durability > 0:
            armor.durability = max(0, armor.durability - amount)
            if armor.durability <= 0:
                return True
        return False

    def to_dict(self) -> Dict:
        result = {}
        for slot, item in self.slots.items():
            if item:
                result[slot.value] = item.to_dict()
            else:
                result[slot.value] = None
        return result


# ============================================================
# 位置系统
# ============================================================

@dataclass
class IslandPosition:
    """玩家在空岛世界中的位置"""
    island_id: str = "starter_island"
    x: float = 0.0
    y: float = 0.0

    def to_dict(self) -> Dict:
        return {"island_id": self.island_id, "x": self.x, "y": self.y}


# ============================================================
# 生物（敌人）
# ============================================================

@dataclass
class Creature:
    """生物（敌人）"""
    id: str
    name: str
    hp: int
    max_hp: int
    atk: int
    defense: int
    exp: int
    drops: Dict[str, list]
    desc: str = ""
    grade: str = "F"

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        actual = max(1, amount - self.defense)
        self.hp = max(0, self.hp - actual)
        return actual

    def roll_drops(self) -> Dict[str, int]:
        import random
        result = {}
        for item_id, (max_amt, chance) in self.drops.items():
            if random.random() < chance:
                result[item_id] = random.randint(1, max_amt)
        return result

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "name": self.name,
            "hp": self.hp, "max_hp": self.max_hp,
            "atk": self.atk, "defense": self.defense,
            "grade": self.grade,
        }


# ============================================================
# Player 玩家实体（v2 新增）
# ============================================================

@dataclass
class Player:
    """玩家实体 - 多人游戏的核心对象

    将 Stats、Inventory、Equipment、Position 合并为统一实体。
    每个玩家有唯一ID，支持序列化用于网络同步。
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "求生者"
    stats: Stats = field(default_factory=Stats)
    inventory: Inventory = field(default_factory=Inventory)
    equipment: Equipment = field(default_factory=Equipment)
    position: IslandPosition = field(default_factory=IslandPosition)

    # 天赋和职业的ID引用（具体数据由各自的System管理）
    talent_id: Optional[str] = None
    profession_id: Optional[str] = None
    profession_level: int = 0
    profession_exp: int = 0

    # 战斗状态（运行时，不序列化）
    in_combat: bool = False
    combat_enemies: List[Creature] = field(default_factory=list)

    @property
    def is_alive(self) -> bool:
        return self.stats.is_alive()

    @property
    def total_atk(self) -> int:
        """总攻击力 = 基础 + 武器 + 职业加成（由系统计算）"""
        return self.stats.atk + self.equipment.get_total_atk()

    @property
    def total_def(self) -> int:
        """总防御力 = 基础 + 装备"""
        return self.stats.defense + self.equipment.get_total_def()

    @property
    def crit_chance(self) -> float:
        return self.stats.crit_chance + self.equipment.get_crit_bonus()

    @property
    def crit_damage_mult(self) -> float:
        return max(self.stats.crit_damage_mult, self.equipment.get_crit_mult_bonus())

    def to_dict(self) -> Dict:
        """序列化为字典（用于网络同步和存档）"""
        return {
            "id": self.id,
            "name": self.name,
            "stats": self.stats.to_dict(),
            "inventory": self.inventory.to_list(),
            "equipment": self.equipment.to_dict(),
            "position": self.position.to_dict(),
            "talent_id": self.talent_id,
            "profession_id": self.profession_id,
            "profession_level": self.profession_level,
            "profession_exp": self.profession_exp,
        }

    @classmethod
    def from_dict(cls, d: Dict, all_items: Dict) -> "Player":
        """从字典反序列化"""
        player = cls(
            id=d.get("id", ""),
            name=d.get("name", "求生者"),
        )
        # 恢复属性
        if "stats" in d:
            player.stats = Stats.from_dict(d["stats"])
        # 恢复背包
        if "inventory" in d:
            for item_save in d["inventory"]:
                item_data = all_items.get(item_save["item_id"])
                if item_data:
                    player.inventory.add_item(
                        item_save["item_id"], item_data,
                        item_save.get("quantity", 1),
                        grade=item_save.get("grade", "F")
                    )
                    # 恢复耐久
                    if "durability" in item_save:
                        for item in player.inventory.items:
                            if item.item_id == item_save["item_id"]:
                                item.durability = item_save["durability"]
                                break
        # 恢复装备
        if "equipment" in d:
            for slot_name, item_save in d["equipment"].items():
                if item_save:
                    try:
                        slot = EquipSlot(slot_name)
                        item_data = all_items.get(item_save["item_id"])
                        if item_data:
                            item = InventoryItem(
                                item_id=item_save["item_id"],
                                item_data=item_data,
                                quantity=item_save.get("quantity", 1),
                                durability=item_save.get("durability", -1),
                                grade=item_save.get("grade", "F"),
                            )
                            player.equipment.equip(item, slot)
                    except (ValueError, KeyError):
                        pass
        # 恢复位置
        if "position" in d:
            player.position = IslandPosition(**d["position"])
        # 恢复天赋和职业
        player.talent_id = d.get("talent_id")
        player.profession_id = d.get("profession_id")
        player.profession_level = d.get("profession_level", 0)
        player.profession_exp = d.get("profession_exp", 0)
        return player
