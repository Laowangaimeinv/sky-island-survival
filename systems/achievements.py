"""成就与称号系统"""

from typing import Dict, List, Set
from core.events import event_bus, EVT


ACHIEVEMENTS = [
    # 建设类
    {"id": "first_build", "name": "初露锋芒", "desc": "建造第一座建筑", "condition": {"type": "building_count", "value": 1}, "reward": {"item": "stone", "amount": 10}},
    {"id": "builder", "name": "建筑师", "desc": "建造5座建筑", "condition": {"type": "building_count", "value": 5}, "reward": {"item": "island_crystal", "amount": 1}},
    {"id": "fortress", "name": "堡垒领主", "desc": "建造防御墙+瞭望塔", "condition": {"type": "has_buildings", "value": ["wall", "watchtower"]}, "reward": {"item": "iron_ore", "amount": 20}},

    # 战斗类
    {"id": "first_kill", "name": "初战告捷", "desc": "击败第一个敌人", "condition": {"type": "kill_count", "value": 1}, "reward": {"item": "bandage", "amount": 3}},
    {"id": "guardian_slayer", "name": "守护者杀手", "desc": "击败第一个守护者", "condition": {"type": "guardian_kill", "value": 1}, "reward": {"item": "island_crystal", "amount": 3}},
    {"id": "warrior", "name": "百战老兵", "desc": "击败100个敌人", "condition": {"type": "kill_count", "value": 100}, "reward": {"item": "crystal_blade", "amount": 1}},

    # 探索类
    {"id": "explorer", "name": "探索者", "desc": "发现3座空岛", "condition": {"type": "island_count", "value": 3}, "reward": {"item": "island_crystal", "amount": 2}},
    {"id": "treasure_hunter", "name": "宝藏猎人", "desc": "开启100个宝箱", "condition": {"type": "chest_count", "value": 100}, "reward": {"item": "crystal", "amount": 10}},
    {"id": "world_traveler", "name": "世界旅行者", "desc": "访问所有空岛", "condition": {"type": "all_islands", "value": True}, "reward": {"item": "void_stone", "amount": 3}},

    # 生存类
    {"id": "survivor_7", "name": "一周幸存者", "desc": "存活7天", "condition": {"type": "survive_days", "value": 7}, "reward": {"item": "cooked_meat", "amount": 5}},
    {"id": "survivor_30", "name": "月度幸存者", "desc": "存活30天", "condition": {"type": "survive_days", "value": 30}, "reward": {"item": "island_crystal", "amount": 5}},
    {"id": "survivor_100", "name": "传奇幸存者", "desc": "存活100天", "condition": {"type": "survive_days", "value": 100}, "reward": {"item": "talent_stone", "amount": 1}},

    # 垂钓类
    {"id": "fisher", "name": "垂钓新手", "desc": "垂钓10次", "condition": {"type": "fish_count", "value": 10}, "reward": {"item": "fishing_rod", "amount": 1}},
    {"id": "master_fisher", "name": "垂钓大师", "desc": "钓到金箱以上", "condition": {"type": "chest_tier", "value": "gold"}, "reward": {"item": "crystal_bait", "amount": 5}},

    # 灾厄类
    {"id": "disaster_survivor", "name": "灾厄幸存者", "desc": "存活3次灾厄潮", "condition": {"type": "disaster_count", "value": 3}, "reward": {"item": "iron_armor", "amount": 1}},
    {"id": "storm_survivor", "name": "风暴行者", "desc": "存活一次虚空风暴", "condition": {"type": "void_storm_survived", "value": 1}, "reward": {"item": "void_stone", "amount": 5}},
]

TITLES = [
    {"id": "newcomer", "name": "新手求生者", "desc": "初来乍到", "effects": {}},
    {"id": "veteran", "name": "资深求生者", "desc": "采集+10%", "effects": {"gather_mult": 1.10}},
    {"id": "disaster_veteran", "name": "灾厄幸存者", "desc": "防御+5", "effects": {"defense": 5}},
    {"id": "island_lord", "name": "空岛领主", "desc": "岛屿融合消耗-10%", "effects": {"island_merge_cost_mult": 0.90}},
    {"id": "void_walker", "name": "虚空行者", "desc": "虚空伤害免疫", "effects": {"void_damage_immune": True}},
    {"id": "legend", "name": "传说中的存在", "desc": "全属性+5%", "effects": {"all_stats_mult": 1.05}},
]


class AchievementSystem:
    """成就系统"""

    def __init__(self, state):
        self.state = state
        self.completed: Set[str] = set()
        self.current_title: str = "newcomer"
        self.kill_count = 0
        self.chest_count = 0
        self.fish_count = 0
        self.disaster_count = 0
        self.void_storm_survived = 0
        self.guardian_kills = 0

    def check_achievements(self):
        """检查并完成成就"""
        for ach in ACHIEVEMENTS:
            if ach["id"] in self.completed:
                continue

            cond = ach["condition"]
            met = False

            if cond["type"] == "building_count":
                met = len(self.state.buildings) >= cond["value"]
            elif cond["type"] == "kill_count":
                met = self.kill_count >= cond["value"]
            elif cond["type"] == "guardian_kill":
                met = self.guardian_kills >= cond["value"]
            elif cond["type"] == "island_count":
                met = len(self.state.explored_islands) >= cond["value"]
            elif cond["type"] == "chest_count":
                met = self.chest_count >= cond["value"]
            elif cond["type"] == "survive_days":
                met = self.state.day >= cond["value"]
            elif cond["type"] == "fish_count":
                met = self.fish_count >= cond["value"]
            elif cond["type"] == "disaster_count":
                met = self.disaster_count >= cond["value"]
            elif cond["type"] == "void_storm_survived":
                met = self.void_storm_survived >= cond["value"]

            if met:
                self._complete_achievement(ach)

    def _complete_achievement(self, ach: Dict):
        """完成成就"""
        self.completed.add(ach["id"])
        event_bus.emit(EVT.MESSAGE, {
            "text": f"\n  🏆 成就解锁：{ach['name']}！"
        })
        event_bus.emit(EVT.MESSAGE, {
            "text": f"  {ach['desc']}"
        })

        # 发放奖励
        reward = ach.get("reward")
        if reward:
            item_data = self.state.get_item_data(reward["item"])
            if item_data:
                self.state.inventory.add_item(reward["item"], item_data, reward["amount"])
                event_bus.emit(EVT.MESSAGE, {
                    "text": f"  奖励：{item_data['name']} ×{reward['amount']}"
                })

    def get_title_effects(self) -> Dict:
        """获取当前称号效果"""
        for t in TITLES:
            if t["id"] == self.current_title:
                return t["effects"]
        return {}

    def get_all_progress(self) -> List[Dict]:
        """获取所有成就进度"""
        result = []
        for ach in ACHIEVEMENTS:
            result.append({
                **ach,
                "completed": ach["id"] in self.completed
            })
        return result
