"""天赋系统 - 抽取、应用、被动效果"""

import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import json

from core.events import event_bus, EVT


DATA_DIR = Path(__file__).parent.parent / "data"


def load_talents() -> dict:
    with open(DATA_DIR / "talents.json", "r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class Talent:
    """天赋实例"""
    id: str
    name: str
    grade: str
    category: str
    icon: str
    desc: str
    effect_desc: str
    passive: bool
    effects: Dict
    unique: bool = False

    @property
    def grade_label(self) -> str:
        labels = {
            "F": "凡级", "E": "初阶", "D": "中阶", "C": "高阶",
            "B": "精英", "A": "传说", "S": "神话", "SS": "超神话",
            "SSS": "至高", "MYTHIC": "唯一神话"
        }
        return labels.get(self.grade, self.grade)

    @property
    def rarity_color(self) -> str:
        colors = {
            "F": "灰色", "E": "白色", "D": "绿色", "C": "蓝色",
            "B": "紫色", "A": "橙色", "S": "金色", "SS": "红色",
            "SSS": "七彩", "MYTHIC": "曜白"
        }
        return colors.get(self.grade, "白色")


class TalentSystem:
    """天赋系统管理器"""

    def __init__(self):
        self.data = load_talents()
        self.grade_config = self.data["grade_config"]
        self.all_talents: Dict[str, dict] = {}
        for t in self.data["talents"]:
            self.all_talents[t["id"]] = t

        self.player_talent: Optional[Talent] = None
        self.used_mythic: set = set()  # 已被抽取的唯一神话天赋

    def draw_talent(self, guarantee_grade: str = None) -> Talent:
        """抽取天赋
        Args:
            guarantee_grade: 保底等级（如 "B" 表示至少B级）
        """
        # 确定等级
        grade = self._roll_grade(guarantee_grade)

        # 从该等级中随机选择
        candidates = [
            t for t in self.data["talents"]
            if t["grade"] == grade and (not t.get("unique") or t["id"] not in self.used_mythic)
        ]

        # 如果该等级没有候选（唯一神话被抽走），降级
        while not candidates and grade != "F":
            grade = self._grade_down(grade)
            candidates = [
                t for t in self.data["talents"]
                if t["grade"] == grade and (not t.get("unique") or t["id"] not in self.used_mythic)
            ]

        chosen = random.choice(candidates)

        # 标记唯一神话
        if chosen.get("unique"):
            self.used_mythic.add(chosen["id"])

        # 创建天赋实例
        talent = Talent(
            id=chosen["id"],
            name=chosen["name"],
            grade=chosen["grade"],
            category=chosen["category"],
            icon=chosen["icon"],
            desc=chosen["desc"],
            effect_desc=chosen["effect_desc"],
            passive=chosen.get("passive", True),
            effects=chosen.get("effects", {}),
            unique=chosen.get("unique", False)
        )

        self.player_talent = talent
        return talent

    def draw_three_choose_one(self, guarantee_grade: str = None) -> List[Talent]:
        """抽三选一（经典模式）"""
        results = []
        seen_grades = set()

        for i in range(3):
            # 确保三个天赋等级不同
            grade = self._roll_grade(guarantee_grade)
            attempts = 0
            while grade in seen_grades and attempts < 10:
                grade = self._roll_grade(guarantee_grade)
                attempts += 1
            seen_grades.add(grade)

            candidates = [
                t for t in self.data["talents"]
                if t["grade"] == grade and (not t.get("unique") or t["id"] not in self.used_mythic)
                and t["id"] not in [r.id for r in results]
            ]

            while not candidates and grade != "F":
                grade = self._grade_down(grade)
                candidates = [
                    t for t in self.data["talents"]
                    if t["grade"] == grade and (not t.get("unique") or t["id"] not in self.used_mythic)
                    and t["id"] not in [r.id for r in results]
                ]

            if candidates:
                chosen = random.choice(candidates)
                if chosen.get("unique"):
                    self.used_mythic.add(chosen["id"])
                results.append(Talent(
                    id=chosen["id"],
                    name=chosen["name"],
                    grade=chosen["grade"],
                    category=chosen["category"],
                    icon=chosen["icon"],
                    desc=chosen["desc"],
                    effect_desc=chosen["effect_desc"],
                    passive=chosen.get("passive", True),
                    effects=chosen.get("effects", {}),
                    unique=chosen.get("unique", False)
                ))

        return results

    def apply_talent(self, talent: Talent, player_stats, inventory=None):
        """将天赋效果应用到玩家"""
        self.player_talent = talent

        effects = talent.effects
        if not isinstance(effects, dict):
            return

        # 直接数值加成
        if "max_hp" in effects:
            player_stats.max_hp += effects["max_hp"]
            player_stats.hp += effects["max_hp"]
        if "atk" in effects:
            player_stats.atk += effects["atk"]
        if "defense" in effects:
            player_stats.defense += effects["defense"]

        event_bus.emit(EVT.TALENT_APPLIED, {
            "talent": talent.name,
            "grade": talent.grade,
            "icon": talent.icon
        })

    def get_passive_effects(self) -> Dict:
        """获取当前天赋的被动效果（供战斗/采集等系统查询）"""
        if not self.player_talent:
            return {}
        return self.player_talent.effects if isinstance(self.player_talent.effects, dict) else {}

    def has_effect(self, effect_key: str) -> bool:
        """检查天赋是否拥有某效果"""
        effects = self.get_passive_effects()
        return effect_key in effects

    def get_effect_value(self, effect_key: str, default=None):
        """获取天赋效果值"""
        return self.get_passive_effects().get(effect_key, default)

    def _roll_grade(self, guarantee: str = None) -> str:
        """随机抽取等级"""
        grades = list(self.grade_config.keys())
        weights = [self.grade_config[g]["weight"] for g in grades]

        # 保底处理
        if guarantee:
            guarantee_idx = grades.index(guarantee) if guarantee in grades else 0
            # 先正常抽
            result = random.choices(grades, weights=weights, k=1)[0]
            result_idx = grades.index(result)
            # 如果低于保底，提升到保底
            if result_idx > guarantee_idx:
                return guarantee
            return result

        return random.choices(grades, weights=weights, k=1)[0]

    def _grade_down(self, grade: str) -> str:
        """降一级"""
        grades = list(self.grade_config.keys())
        idx = grades.index(grade) if grade in grades else 0
        return grades[min(idx + 1, len(grades) - 1)]

    def get_talent_pool(self, grade: str = None) -> List[dict]:
        """获取天赋池（用于展示）"""
        if grade:
            return [t for t in self.data["talents"] if t["grade"] == grade]
        return self.data["talents"]

    def get_stats_summary(self) -> Dict:
        """获取天赋统计"""
        pool = self.data["talents"]
        by_grade = {}
        for t in pool:
            g = t["grade"]
            by_grade[g] = by_grade.get(g, 0) + 1

        by_category = {}
        for t in pool:
            c = t["category"]
            by_category[c] = by_category.get(c, 0) + 1

        return {
            "total": len(pool),
            "by_grade": by_grade,
            "by_category": by_category
        }
