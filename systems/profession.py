"""职业与技能系统

职业获取方式：
- 垂钓获得职业卷轴（稀有掉落）
- 开宝箱获得职业令牌
- 击败特定BOSS掉落

职业等级：
- 见习 (Lv.1-10)
- 正式 (Lv.11-30)
- 精英 (Lv.31-50)
- 大师 (Lv.51-70)
- 宗师 (Lv.71-90)
- 传说 (Lv.91-100)

职业技能通过升级解锁，部分技能需要技能书学习。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import random

from core.events import event_bus, EVT


@dataclass
class Skill:
    """技能"""
    id: str
    name: str
    icon: str
    desc: str
    skill_type: str   # active / passive / buff
    mana_cost: int = 0
    cooldown: int = 0  # 回合数
    damage: int = 0
    heal: int = 0
    duration: int = 0  # 持续回合（buff类）
    effects: Dict = field(default_factory=dict)
    level_required: int = 1
    profession_required: str = ""

    @property
    def is_active(self) -> bool:
        return self.skill_type == "active"

    @property
    def is_passive(self) -> bool:
        return self.skill_type == "passive"


@dataclass
class ProfessionClass:
    """职业"""
    id: str
    name: str
    icon: str
    desc: str
    grade: str           # F/E/D/C/B/A/S/SS/SSS
    category: str        # warrior/mage/ranger/crafter/gatherer/support
    base_stats: Dict = field(default_factory=dict)  # 职业基础属性加成
    skills: List[str] = field(default_factory=list)   # 技能ID列表
    passive_effects: Dict = field(default_factory=dict)  # 被动效果
    growth_stats: Dict = field(default_factory=dict)  # 每级成长

    @property
    def grade_label(self) -> str:
        labels = {
            "F": "凡级", "E": "初阶", "D": "中阶", "C": "高阶",
            "B": "精英", "A": "传说", "S": "神话", "SS": "超神话",
            "SSS": "至高"
        }
        return labels.get(self.grade, self.grade)


class ProfessionSystem:
    """职业系统管理器"""

    def __init__(self):
        self.professions: Dict[str, ProfessionClass] = {}
        self.skills: Dict[str, Skill] = {}
        self.player_profession: Optional[ProfessionClass] = None
        self.player_skills: Dict[str, Skill] = {}  # 已学习的技能
        self.skill_cooldowns: Dict[str, int] = {}  # 技能冷却
        self.profession_level: int = 1
        self.profession_exp: int = 0
        self.profession_exp_to_next: int = 100
        self.available_professions: List[str] = []  # 可用的职业卷轴

        self._init_data()

    def _init_data(self):
        """初始化职业和技能数据"""
        # ===== 技能定义 =====
        all_skills = [
            # --- 战士系 ---
            Skill("warrior_slash", "猛击", "⚔️", "全力一击，造成150%攻击力伤害",
                  "active", mana_cost=5, cooldown=2, damage=150,
                  level_required=1, profession_required="warrior"),
            Skill("warrior_shield", "盾墙", "🛡️", "本回合防御翻倍，反弹30%伤害",
                  "active", mana_cost=8, cooldown=3,
                  effects={"def_mult": 2.0, "reflect": 0.3},
                  level_required=5, profession_required="warrior"),
            Skill("warrior_fury", "狂暴", "😤", "3回合内攻击力+50%，防御-30%",
                  "active", mana_cost=12, cooldown=5, duration=3,
                  effects={"atk_mult": 1.5, "def_mult": 0.7},
                  level_required=15, profession_required="warrior"),
            Skill("warrior_cleave", "横扫", "💥", "攻击所有敌人，造成100%伤害",
                  "active", mana_cost=10, cooldown=3, damage=100,
                  effects={"target": "all"},
                  level_required=25, profession_required="warrior"),
            Skill("warrior_toughness", "铁壁体质", "🏰", "被动：HP上限+20%，防御+15%",
                  "passive",
                  effects={"max_hp_mult": 1.2, "def_mult": 1.15},
                  level_required=10, profession_required="warrior"),
            Skill("warrior_berserk", "狂战之血", "🩸", "被动：HP每损失10%，攻击力+10%",
                  "passive",
                  effects={"berserker_atk_per_10hp": 0.10},
                  level_required=35, profession_required="warrior"),

            # --- 法师系 ---
            Skill("mage_fireball", "火球术", "🔥", "发射火球，造成180%攻击力伤害",
                  "active", mana_cost=8, cooldown=2, damage=180,
                  level_required=1, profession_required="mage"),
            Skill("mage_ice", "冰冻术", "❄️", "冻结敌人1回合，无法行动",
                  "active", mana_cost=10, cooldown=4,
                  effects={"freeze": 1},
                  level_required=10, profession_required="mage"),
            Skill("mage_heal", "治愈术", "💚", "恢复30%最大HP",
                  "active", mana_cost=12, cooldown=3,
                  heal=30, effects={"heal_type": "percent"},
                  level_required=5, profession_required="mage"),
            Skill("mage_lightning", "雷霆万钧", "⚡", "召唤雷电，造成250%伤害，30%概率眩晕",
                  "active", mana_cost=20, cooldown=5, damage=250,
                  effects={"stun_chance": 0.3, "stun_duration": 1},
                  level_required=30, profession_required="mage"),
            Skill("mage_mana_flow", "魔力涌流", "🔮", "被动：MP上限+30%，MP恢复+50%",
                  "passive",
                  effects={"max_mana_mult": 1.3, "mana_regen_mult": 1.5},
                  level_required=15, profession_required="mage"),
            Skill("mage_arcane", "奥术精通", "✨", "被动：所有技能伤害+25%",
                  "passive",
                  effects={"skill_damage_mult": 1.25},
                  level_required=40, profession_required="mage"),

            # --- 游侠系 ---
            Skill("ranger_arrow", "精准射击", "🏹", "远程攻击，造成160%伤害，暴击率+20%",
                  "active", mana_cost=6, cooldown=2, damage=160,
                  effects={"crit_bonus": 0.20},
                  level_required=1, profession_required="ranger"),
            Skill("ranger_trap", "陷阱", "🪤", "设置陷阱，敌人行动时受到最大HP10%伤害",
                  "active", mana_cost=8, cooldown=4,
                  effects={"trap_damage_percent": 0.10, "trap_duration": 3},
                  level_required=10, profession_required="ranger"),
            Skill("ranger_dodge", "闪避翻滚", "💨", "本回合闪避率+80%",
                  "active", mana_cost=5, cooldown=2,
                  effects={"dodge_mult": 0.80},
                  level_required=5, profession_required="ranger"),
            Skill("ranger_multi", "多重射击", "🎯", "攻击3次，每次造成80%伤害",
                  "active", mana_cost=15, cooldown=4, damage=80,
                  effects={"hits": 3},
                  level_required=25, profession_required="ranger"),
            Skill("ranger_eagle_eye", "鹰眼", "🦅", "被动：暴击率+15%，暴击伤害+50%",
                  "passive",
                  effects={"crit_chance": 0.15, "crit_damage_mult": 1.5},
                  level_required=15, profession_required="ranger"),
            Skill("ranger_survival", "生存本能", "🌿", "被动：每回合恢复3%HP，采集+20%",
                  "passive",
                  effects={"hp_regen_percent": 0.03, "gather_mult": 1.20},
                  level_required=20, profession_required="ranger"),

            # --- 工匠系 ---
            Skill("crafter_repair", "修复", "🔧", "恢复装备50%耐久",
                  "active", mana_cost=10, cooldown=5,
                  effects={"repair_percent": 0.50},
                  level_required=1, profession_required="crafter"),
            Skill("crafter_reinforce", "强化", "⚒️", "下一次制作的装备品质+1阶",
                  "active", mana_cost=15, cooldown=10,
                  effects={"quality_boost": 1},
                  level_required=15, profession_required="crafter"),
            Skill("crafter_efficient", "高效工艺", "📐", "被动：制作消耗-20%，耐久+30%",
                  "passive",
                  effects={"craft_cost_mult": 0.80, "durability_mult": 1.30},
                  level_required=10, profession_required="crafter"),
            Skill("crafter_masterwork", "大师之作", "💎", "被动：10%概率制作出品质+2的装备",
                  "passive",
                  effects={"masterwork_chance": 0.10},
                  level_required=35, profession_required="crafter"),

            # --- 采集者系 ---
            Skill("gatherer_harvest", "丰收", "🌾", "下次采集获得双倍资源",
                  "active", mana_cost=8, cooldown=5,
                  effects={"double_gather": True},
                  level_required=1, profession_required="gatherer"),
            Skill("gatherer_sense", "资源感知", "📡", "显示当前岛屿所有资源点",
                  "active", mana_cost=5, cooldown=3,
                  effects={"reveal_resources": True},
                  level_required=5, profession_required="gatherer"),
            Skill("gatherer_lucky", "幸运采集", "🍀", "被动：采集时5%概率获得稀有物品",
                  "passive",
                  effects={"rare_gather_chance": 0.05},
                  level_required=15, profession_required="gatherer"),
            Skill("gatherer_treasure", "寻宝直觉", "💰", "被动：垂钓品质+1，宝箱发现率+20%",
                  "passive",
                  effects={"fishing_quality": 1, "chest_find_bonus": 0.20},
                  level_required=25, profession_required="gatherer"),

            # --- 辅助系 ---
            Skill("support_heal", "治愈之光", "💚", "恢复20%最大HP",
                  "active", mana_cost=8, cooldown=2,
                  heal=20, effects={"heal_type": "percent"},
                  level_required=1, profession_required="support"),
            Skill("support_buff", "战歌", "🎵", "3回合内全属性+15%",
                  "active", mana_cost=12, cooldown=5, duration=3,
                  effects={"all_stats_mult": 1.15},
                  level_required=10, profession_required="support"),
            Skill("support_barrier", "守护屏障", "🛡️", "2回合内免疫所有伤害的50%",
                  "active", mana_cost=15, cooldown=6, duration=2,
                  effects={"damage_reduce": 0.50},
                  level_required=20, profession_required="support"),
            Skill("support_revive", "重生之光", "✨", "战斗中HP归零时自动恢复30%HP（每场战斗一次）",
                  "passive",
                  effects={"revive_percent": 0.30, "revive_per_battle": 1},
                  level_required=35, profession_required="support"),
        ]

        for skill in all_skills:
            self.skills[skill.id] = skill

        # ===== 职业定义 =====
        all_professions = [
            # F级 - 基础职业
            ProfessionClass("warrior", "战士", "⚔️", "精通近战的职业，攻防兼备",
                           "F", "warrior",
                           base_stats={"atk": 3, "defense": 2, "max_hp": 15},
                           skills=["warrior_slash", "warrior_shield", "warrior_fury",
                                   "warrior_cleave", "warrior_toughness", "warrior_berserk"],
                           passive_effects={"weapon_atk_mult": 1.10},
                           growth_stats={"atk": 2, "defense": 1, "max_hp": 8}),

            ProfessionClass("mage", "法师", "🔮", "掌控元素之力的职业，高爆发",
                           "F", "mage",
                           base_stats={"atk": 5, "max_hp": 5, "max_mana": 20},
                           skills=["mage_fireball", "mage_ice", "mage_heal",
                                   "mage_lightning", "mage_mana_flow", "mage_arcane"],
                           passive_effects={"skill_damage_mult": 1.10},
                           growth_stats={"atk": 3, "max_hp": 3, "max_mana": 5}),

            ProfessionClass("ranger", "游侠", "🏹", "远程精准打击，高机动性",
                           "F", "ranger",
                           base_stats={"atk": 4, "defense": 1, "max_hp": 10, "crit_chance": 0.05},
                           skills=["ranger_arrow", "ranger_trap", "ranger_dodge",
                                   "ranger_multi", "ranger_eagle_eye", "ranger_survival"],
                           passive_effects={"crit_chance": 0.05},
                           growth_stats={"atk": 2, "defense": 1, "max_hp": 5}),

            # D级 - 进阶职业
            ProfessionClass("crafter", "工匠", "🔧", "精通制作的大师，装备品质更高",
                           "D", "crafter",
                           base_stats={"defense": 3, "max_hp": 10},
                           skills=["crafter_repair", "crafter_reinforce",
                                   "crafter_efficient", "crafter_masterwork"],
                           passive_effects={"craft_cost_mult": 0.90, "durability_mult": 1.20},
                           growth_stats={"defense": 2, "max_hp": 6}),

            ProfessionClass("gatherer", "采集者", "🌾", "资源获取专家，产量更高",
                           "D", "gatherer",
                           base_stats={"max_hp": 8},
                           skills=["gatherer_harvest", "gatherer_sense",
                                   "gatherer_lucky", "gatherer_treasure"],
                           passive_effects={"gather_mult": 1.25, "fishing_quality": 1},
                           growth_stats={"max_hp": 5}),

            # C级 - 精英职业
            ProfessionClass("paladin", "圣骑士", "🛡️", "神圣的守护者，攻防治疗兼备",
                           "C", "warrior",
                           base_stats={"atk": 6, "defense": 5, "max_hp": 25, "max_mana": 10},
                           skills=["warrior_slash", "warrior_shield", "support_heal",
                                   "support_buff", "warrior_toughness"],
                           passive_effects={"weapon_atk_mult": 1.15, "heal_mult": 1.30},
                           growth_stats={"atk": 3, "defense": 2, "max_hp": 12}),

            ProfessionClass("assassin", "刺客", "🗡️", "暗影中的杀手，极高暴击",
                           "C", "ranger",
                           base_stats={"atk": 8, "max_hp": 8, "crit_chance": 0.15, "dodge": 0.10},
                           skills=["ranger_arrow", "ranger_dodge", "ranger_multi",
                                   "ranger_eagle_eye"],
                           passive_effects={"crit_chance": 0.15, "crit_damage_mult": 1.50,
                                            "backstab_mult": 2.0},
                           growth_stats={"atk": 4, "max_hp": 4}),

            # B级 - 大师职业
            ProfessionClass("berserker", "狂战士", "😤", "越战越勇的战斗机器",
                           "B", "warrior",
                           base_stats={"atk": 12, "defense": -2, "max_hp": 30},
                           skills=["warrior_slash", "warrior_fury", "warrior_cleave",
                                   "warrior_berserk"],
                           passive_effects={"atk_mult": 1.20, "berserker_atk_per_10hp": 0.12,
                                            "lifesteal": 0.10},
                           growth_stats={"atk": 5, "max_hp": 10}),

            ProfessionClass("archmage", "大法师", "🌌", "元素之力的掌控者",
                           "B", "mage",
                           base_stats={"atk": 10, "max_hp": 15, "max_mana": 40},
                           skills=["mage_fireball", "mage_ice", "mage_lightning",
                                   "mage_heal", "mage_mana_flow", "mage_arcane"],
                           passive_effects={"skill_damage_mult": 1.30, "mana_regen_mult": 2.0,
                                            "cooldown_reduction": 0.20},
                           growth_stats={"atk": 4, "max_hp": 5, "max_mana": 8}),

            # A级 - 传说职业
            ProfessionClass("void_knight", "虚空骑士", "🌀", "虚空之力的使者",
                           "A", "warrior",
                           base_stats={"atk": 15, "defense": 10, "max_hp": 40, "max_mana": 15},
                           skills=["warrior_slash", "warrior_shield", "warrior_fury",
                                   "warrior_cleave", "warrior_toughness", "warrior_berserk"],
                           passive_effects={"true_damage": True, "void_aura": True,
                                            "weapon_atk_mult": 1.25, "def_mult": 1.20},
                           growth_stats={"atk": 5, "defense": 3, "max_hp": 15}),

            ProfessionClass("elementalist", "元素使", "🌈", "同时掌控火冰雷三元素",
                           "A", "mage",
                           base_stats={"atk": 12, "max_hp": 20, "max_mana": 50},
                           skills=["mage_fireball", "mage_ice", "mage_lightning",
                                   "mage_heal", "mage_mana_flow", "mage_arcane"],
                           passive_effects={"skill_damage_mult": 1.40, "elemental_mastery": True,
                                            "mana_regen_mult": 2.5},
                           growth_stats={"atk": 5, "max_hp": 6, "max_mana": 10}),

            # S级 - 神话职业
            ProfessionClass("god_of_war", "战神", "🔥", "战争之神的化身",
                           "S", "warrior",
                           base_stats={"atk": 25, "defense": 15, "max_hp": 60},
                           skills=["warrior_slash", "warrior_shield", "warrior_fury",
                                   "warrior_cleave", "warrior_toughness", "warrior_berserk"],
                           passive_effects={"atk_mult": 1.50, "def_mult": 1.30,
                                            "berserker_atk_per_10hp": 0.15,
                                            "lifesteal": 0.15, "crit_chance": 0.20},
                           growth_stats={"atk": 7, "defense": 3, "max_hp": 20}),

            ProfessionClass("arcane_lord", "奥术之主", "✨", "超越凡人理解的魔法存在",
                           "S", "mage",
                           base_stats={"atk": 20, "max_hp": 30, "max_mana": 80},
                           skills=["mage_fireball", "mage_ice", "mage_lightning",
                                   "mage_heal", "mage_mana_flow", "mage_arcane"],
                           passive_effects={"skill_damage_mult": 1.60, "no_cooldown_chance": 0.15,
                                            "mana_shield": True, "elemental_mastery": True},
                           growth_stats={"atk": 6, "max_hp": 8, "max_mana": 15}),
        ]

        for prof in all_professions:
            self.professions[prof.id] = prof

    def get_profession_drop_from_chest(self, chest_tier: str) -> Optional[ProfessionClass]:
        """从宝箱中获取职业（按小说爆率）"""
        # 职业爆率（参考小说设定）
        tier_profession_rates = {
            "white":   {},  # 白箱不出职业
            "green":   {},  # 绿箱不出职业
            "blue":    {"F": 0.15},  # 蓝箱15%出F级职业
            "silver":  {"F": 0.30, "D": 0.10},  # 银箱30%F级，10%D级
            "gold":    {"D": 0.25, "C": 0.08},  # 金箱25%D级，8%C级
            "rainbow": {"C": 0.20, "B": 0.08, "A": 0.03},  # 彩箱
            "black":   {"B": 0.15, "A": 0.10, "S": 0.03},  # 黑箱
        }

        rates = tier_profession_rates.get(chest_tier, {})
        if not rates:
            return None

        # 按概率依次判定
        for grade, rate in rates.items():
            if random.random() < rate:
                # 从该等级中随机选一个职业
                candidates = [p for p in self.professions.values() if p.grade == grade]
                if candidates:
                    return random.choice(candidates)

        return None

    def get_skill_book_from_chest(self, chest_tier: str) -> Optional[Skill]:
        """从宝箱中获取技能书"""
        tier_skill_rates = {
            "white":   {},
            "green":   {"F": 0.08},
            "blue":    {"F": 0.15, "E": 0.05},
            "silver":  {"E": 0.15, "D": 0.08},
            "gold":    {"D": 0.20, "C": 0.10},
            "rainbow": {"C": 0.20, "B": 0.10, "A": 0.05},
            "black":   {"B": 0.20, "A": 0.15, "S": 0.05},
        }

        rates = tier_skill_rates.get(chest_tier, {})
        if not rates:
            return None

        for grade, rate in rates.items():
            if random.random() < rate:
                # 根据等级选择技能
                grade_to_level = {"F": 1, "E": 5, "D": 10, "C": 15, "B": 25, "A": 35, "S": 40}
                min_level = grade_to_level.get(grade, 1)
                candidates = [s for s in self.skills.values()
                             if s.level_required <= min_level + 10 and s.level_required >= max(1, min_level - 5)]
                if candidates:
                    return random.choice(candidates)

        return None

    def learn_profession(self, profession: ProfessionClass, player_stats) -> bool:
        """学习职业"""
        # 转职时重置等级和经验
        player_stats.reset_for_profession()
        self.player_profession = profession
        self.profession_level = 1
        self.profession_exp = 0
        self.profession_exp_to_next = 100

        # 应用基础属性加成
        for stat, value in profession.base_stats.items():
            if stat == "atk":
                player_stats.atk += value
            elif stat == "defense":
                player_stats.defense += value
            elif stat == "max_hp":
                player_stats.max_hp += value
                player_stats.hp += value
            elif stat == "max_mana":
                player_stats.max_mana += value
                player_stats.mana += value
            elif stat == "crit_chance":
                player_stats.crit_chance += value

        # 学习第一个技能
        if profession.skills:
            first_skill_id = profession.skills[0]
            if first_skill_id in self.skills:
                self.player_skills[first_skill_id] = self.skills[first_skill_id]

        event_bus.emit(EVT.MESSAGE, {
            "text": f"🎓 转职成功！成为 {profession.icon} {profession.name}！"
        })
        event_bus.emit(EVT.MESSAGE, {
            "text": f"  {profession.desc}"
        })

        return True

    def learn_skill(self, skill_id: str) -> bool:
        """学习技能"""
        if skill_id not in self.skills:
            return False

        skill = self.skills[skill_id]

        # 检查职业要求
        if skill.profession_required and self.player_profession:
            if self.player_profession.category != skill.profession_required and \
               self.player_profession.id != skill.profession_required:
                event_bus.emit(EVT.MESSAGE, {
                    "text": f"需要{skill.profession_required}职业才能学习此技能"
                })
                return False

        # 检查等级要求
        if self.profession_level < skill.level_required:
            event_bus.emit(EVT.MESSAGE, {
                "text": f"需要职业等级{skill.level_required}（当前{self.profession_level}）"
            })
            return False

        self.player_skills[skill_id] = skill
        event_bus.emit(EVT.MESSAGE, {
            "text": f"📖 学会了新技能：{skill.icon} {skill.name}！"
        })
        return True

    def use_skill(self, skill_id: str, player_stats, enemies=None) -> Dict:
        """使用技能"""
        if skill_id not in self.player_skills:
            return {"success": False, "reason": "未学习此技能"}

        skill = self.player_skills[skill_id]

        # 检查冷却
        if skill_id in self.skill_cooldowns and self.skill_cooldowns[skill_id] > 0:
            return {"success": False, "reason": f"冷却中（{self.skill_cooldowns[skill_id]}回合）"}

        # 检查MP
        if skill.mana_cost > 0 and player_stats.mana < skill.mana_cost:
            return {"success": False, "reason": "MP不足"}

        # 消耗MP
        if skill.mana_cost > 0:
            player_stats.mana -= skill.mana_cost

        # 设置冷却
        if skill.cooldown > 0:
            self.skill_cooldowns[skill_id] = skill.cooldown

        result = {
            "success": True,
            "skill_name": skill.name,
            "skill_icon": skill.icon,
            "type": skill.skill_type,
        }

        # 处理技能效果
        if skill.damage > 0:
            result["damage_mult"] = skill.damage / 100.0
            result["effects"] = skill.effects

        if skill.heal > 0:
            result["heal_percent"] = skill.heal
            if skill.effects.get("heal_type") == "percent":
                heal_amount = int(player_stats.max_hp * skill.heal / 100)
                actual = player_stats.heal(heal_amount)
                result["heal_amount"] = actual
                event_bus.emit(EVT.MESSAGE, {
                    "text": f"{skill.icon} {skill.name}！恢复了{actual}点HP"
                })

        if skill.effects:
            result["effects"] = skill.effects

        return result

    def tick_cooldowns(self):
        """冷却减少"""
        expired = []
        for skill_id, cd in self.skill_cooldowns.items():
            self.skill_cooldowns[skill_id] = max(0, cd - 1)
            if self.skill_cooldowns[skill_id] <= 0:
                expired.append(skill_id)
        for sid in expired:
            del self.skill_cooldowns[sid]

    def add_profession_exp(self, amount: int, player_stats) -> bool:
        """增加职业经验"""
        self.profession_exp += amount
        if self.profession_exp >= self.profession_exp_to_next:
            self.profession_exp -= self.profession_exp_to_next
            self.profession_level += 1
            self.profession_exp_to_next = int(self.profession_exp_to_next * 1.3)

            # 应用成长属性
            if self.player_profession:
                for stat, value in self.player_profession.growth_stats.items():
                    if stat == "atk":
                        player_stats.atk += value
                    elif stat == "defense":
                        player_stats.defense += value
                    elif stat == "max_hp":
                        player_stats.max_hp += value
                        player_stats.hp += value
                    elif stat == "max_mana":
                        player_stats.max_mana += value
                        player_stats.mana += value

            # 检查解锁新技能
            self._check_skill_unlock()

            event_bus.emit(EVT.MESSAGE, {
                "text": f"🎓 职业升级！{self.player_profession.icon} {self.player_profession.name} Lv.{self.profession_level}"
            })
            return True
        return False

    def _check_skill_unlock(self):
        """检查是否解锁新技能"""
        if not self.player_profession:
            return

        for skill_id in self.player_profession.skills:
            if skill_id in self.player_skills:
                continue
            skill = self.skills.get(skill_id)
            if skill and self.profession_level >= skill.level_required:
                self.player_skills[skill_id] = skill
                event_bus.emit(EVT.MESSAGE, {
                    "text": f"  ✨ 解锁新技能：{skill.icon} {skill.name}！"
                })

    def get_available_skills(self) -> List[Dict]:
        """获取可用技能列表"""
        result = []
        for skill_id, skill in self.player_skills.items():
            cd = self.skill_cooldowns.get(skill_id, 0)
            result.append({
                "id": skill_id,
                "name": skill.name,
                "icon": skill.icon,
                "desc": skill.desc,
                "type": skill.skill_type,
                "mana_cost": skill.mana_cost,
                "cooldown": cd,
                "max_cooldown": skill.cooldown,
                "can_use": cd <= 0,
            })
        return result

    def get_profession_info(self) -> Dict:
        """获取职业信息"""
        if not self.player_profession:
            return {"has_profession": False}

        prof = self.player_profession
        return {
            "has_profession": True,
            "name": prof.name,
            "icon": prof.icon,
            "desc": prof.desc,
            "grade": prof.grade,
            "grade_label": prof.grade_label,
            "level": self.profession_level,
            "exp": self.profession_exp,
            "exp_to_next": self.profession_exp_to_next,
            "skill_count": len(self.player_skills),
            "passive_effects": prof.passive_effects,
        }

    def save_state(self) -> Dict:
        """保存状态"""
        return {
            "profession_id": self.player_profession.id if self.player_profession else None,
            "profession_level": self.profession_level,
            "profession_exp": self.profession_exp,
            "profession_exp_to_next": self.profession_exp_to_next,
            "learned_skills": list(self.player_skills.keys()),
            "cooldowns": dict(self.skill_cooldowns),
        }

    def load_state(self, data: Dict):
        """加载状态"""
        prof_id = data.get("profession_id")
        if prof_id and prof_id in self.professions:
            self.player_profession = self.professions[prof_id]

        self.profession_level = data.get("profession_level", 1)
        self.profession_exp = data.get("profession_exp", 0)
        self.profession_exp_to_next = data.get("profession_exp_to_next", 100)

        for skill_id in data.get("learned_skills", []):
            if skill_id in self.skills:
                self.player_skills[skill_id] = self.skills[skill_id]

        self.skill_cooldowns = data.get("cooldowns", {})
