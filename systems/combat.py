"""战斗系统 - 回合制战斗

特性：
- 回合制战斗，每回合可选择攻击/防御/技能/物品/逃跑
- 战斗中随机事件触发
- 职业技能系统集成
- 武器/护甲耐久消耗
- 暴击/闪避系统
"""

import random
from typing import List, Optional, Dict

from core.events import event_bus, EVT
from core.world import GameState
from core.entities import Creature, GRADE_CONFIG


class CombatSystem:
    """回合制战斗系统"""

    def __init__(self, state: GameState):
        self.state = state
        self.in_combat = False
        self.enemies: List[Creature] = []
        self.can_flee = True
        self.combat_round = 0
        self.random_events = state.gameplay_data.get("combat_random_events", [])
        self.temp_buffs = {}  # 临时增益 {buff_id: {"effect": ..., "remaining": ...}}
        self.revive_used_this_battle = False

    def start_combat(self, enemies: List[Creature], can_flee: bool = True):
        """开始战斗"""
        self.in_combat = True
        self.enemies = enemies
        self.can_flee = can_flee
        self.combat_round = 0
        self.temp_buffs = {}
        self.revive_used_this_battle = False

        names = "、".join(e.name for e in enemies)
        event_bus.emit(EVT.COMBAT_START, {
            "enemies": [{"name": e.name, "hp": e.hp, "max_hp": e.max_hp} for e in enemies],
            "can_flee": can_flee
        })
        event_bus.emit(EVT.MESSAGE, {"text": f"⚠️ 遭遇了 {names}！"})

    def player_attack(self, target_index: int = 0) -> dict:
        """玩家攻击"""
        if not self.in_combat or target_index >= len(self.enemies):
            return {"type": "error"}

        stats = self.state.player_stats
        enemy = self.enemies[target_index]

        # 计算伤害（v2: 使用装备槽位）
        weapon = self.state.player.equipment.get_weapon()
        weapon_atk = weapon.item_data.get("atk", 0) if weapon and not weapon.is_broken else 0
        total_atk = stats.atk + weapon_atk

        # 职业被动加成
        prof_effects = {}
        if self.state.profession_system.player_profession:
            prof_effects = self.state.profession_system.player_profession.passive_effects

        if "weapon_atk_mult" in prof_effects:
            total_atk = int(total_atk * prof_effects["weapon_atk_mult"])
        if "atk_mult" in prof_effects:
            total_atk = int(total_atk * prof_effects["atk_mult"])

        # 狂战士被动：HP每损失10%，攻击力+X%
        berserker_bonus = prof_effects.get("berserker_atk_per_10hp", 0)
        if berserker_bonus > 0:
            hp_lost_percent = 1.0 - (stats.hp / stats.max_hp)
            atk_boost = 1.0 + int(hp_lost_percent * 10) * berserker_bonus
            total_atk = int(total_atk * atk_boost)

        # 临时增益
        for buff_id, buff in list(self.temp_buffs.items()):
            if "atk_mult" in buff.get("effects", {}):
                total_atk = int(total_atk * buff["effects"]["atk_mult"])

        # 暴击判定
        crit_chance = self.state.player.crit_chance
        if weapon and not weapon.is_broken:
            crit_chance += weapon.item_data.get("crit_chance", 0)
        if "crit_chance" in prof_effects:
            crit_chance += prof_effects["crit_chance"]

        crit = random.random() < crit_chance
        crit_mult = self.state.player.crit_damage_mult
        if weapon and not weapon.is_broken:
            crit_mult = max(crit_mult, weapon.item_data.get("crit_damage_mult", crit_mult))
        if "crit_damage_mult" in prof_effects:
            crit_mult = prof_effects["crit_damage_mult"]

        damage = int(total_atk * crit_mult) if crit else total_atk

        actual = enemy.take_damage(damage)

        result = {
            "type": "attack",
            "target": enemy.name,
            "damage": actual,
            "crit": crit,
            "target_hp": enemy.hp,
            "target_max_hp": enemy.max_hp,
            "killed": not enemy.is_alive()
        }

        if crit:
            event_bus.emit(EVT.MESSAGE, {"text": f"💥 暴击！对{enemy.name}造成了{actual}点伤害！"})
        else:
            event_bus.emit(EVT.MESSAGE, {"text": f"⚔️ 攻击{enemy.name}，造成{actual}点伤害。（{enemy.hp}/{enemy.max_hp}）"})

        # 吸血效果
        lifesteal = prof_effects.get("lifesteal", 0)
        if lifesteal > 0:
            heal_amount = int(actual * lifesteal)
            healed = stats.heal(heal_amount)
            if healed > 0:
                event_bus.emit(EVT.MESSAGE, {"text": f"🧛 吸取了{healed}点生命"})

        # 武器耐久消耗（v2: 使用装备槽位）
        if weapon and weapon.durability > 0:
            broken = self.state.player.equipment.consume_weapon_durability(1)
            if broken:
                event_bus.emit(EVT.MESSAGE, {"text": f"你的{weapon.name}损坏了！"})

        # 检查敌人是否死亡
        if not enemy.is_alive():
            event_bus.emit(EVT.MESSAGE, {"text": f"✅ {enemy.name}被击败了！"})
            self._handle_enemy_death(enemy)
            self.enemies.remove(enemy)

        # 触发战斗随机事件
        if self.in_combat and self.enemies:
            self._trigger_random_event()

        # 敌人回合
        if self.in_combat and self.enemies:
            self._enemy_turn()

        # 更新增益持续时间
        self._tick_buffs()

        # 职业技能冷却减少
        self.state.profession_system.tick_cooldowns()

        # 检查战斗结束
        if not self.enemies:
            self._end_combat("victory")

        self.combat_round += 1
        return result

    def player_skill_attack(self, skill_id: str, target_index: int = 0) -> dict:
        """使用技能攻击"""
        if not self.in_combat:
            return {"type": "error", "reason": "不在战斗中"}

        stats = self.state.player_stats
        result = self.state.profession_system.use_skill(skill_id, stats, self.enemies)

        if not result["success"]:
            event_bus.emit(EVT.MESSAGE, {"text": f"无法使用技能：{result['reason']}"})
            return result

        skill = self.state.profession_system.player_skills[skill_id]

        # 处理伤害
        if result.get("damage_mult"):
            enemy = self.enemies[min(target_index, len(self.enemies) - 1)]
            base_atk = stats.atk
            weapon = self.state.inventory.get_equipped_weapon()
            if weapon:
                base_atk += weapon.item_data.get("atk", 0)

            damage = int(base_atk * result["damage_mult"])

            # 职业技能伤害加成
            prof_effects = self.state.profession_system.player_profession.passive_effects if self.state.profession_system.player_profession else {}
            if "skill_damage_mult" in prof_effects:
                damage = int(damage * prof_effects["skill_damage_mult"])

            # 全体攻击
            if result.get("effects", {}).get("target") == "all":
                for e in list(self.enemies):
                    actual = e.take_damage(damage)
                    event_bus.emit(EVT.MESSAGE, {"text": f"{skill.icon} {skill.icon} 对{e.name}造成{actual}点伤害"})
                    if not e.is_alive():
                        self._handle_enemy_death(e)
                        self.enemies.remove(e)
            else:
                actual = enemy.take_damage(damage)
                event_bus.emit(EVT.MESSAGE, {"text": f"{skill.icon} {skill.name}！对{enemy.name}造成{actual}点伤害"})
                if not enemy.is_alive():
                    self._handle_enemy_death(enemy)
                    self.enemies.remove(enemy)

        # 处理治疗
        if result.get("heal_amount"):
            event_bus.emit(EVT.MESSAGE, {"text": f"{skill.icon} {skill.name}！恢复了{result['heal_amount']}点HP"})

        # 处理增益效果
        if result.get("effects"):
            effects = result["effects"]
            if "def_mult" in effects or "atk_mult" in effects or "all_stats_mult" in effects:
                self.temp_buffs[skill_id] = {
                    "effects": effects,
                    "remaining": skill.duration or 1,
                    "name": skill.name
                }
                event_bus.emit(EVT.MESSAGE, {"text": f"{skill.icon} {skill.name}效果持续{skill.duration}回合"})

            # 冰冻效果
            if "freeze" in effects:
                self.temp_buffs[f"freeze_{skill_id}"] = {
                    "effects": {"frozen": True},
                    "remaining": effects["freeze"],
                    "name": "冰冻"
                }
                event_bus.emit(EVT.MESSAGE, {"text": "❄️ 敌人被冻结了！"})

            # 陷阱效果
            if "trap_damage_percent" in effects:
                trap_dmg = int(self.enemies[0].max_hp * effects["trap_damage_percent"]) if self.enemies else 0
                if self.enemies:
                    self.enemies[0].take_damage(trap_dmg)
                    event_bus.emit(EVT.MESSAGE, {"text": f"🪤 陷阱触发！造成{trap_dmg}点伤害"})

        # 触发随机事件
        if self.in_combat and self.enemies:
            self._trigger_random_event()

        # 敌人回合
        if self.in_combat and self.enemies:
            self._enemy_turn()

        self._tick_buffs()
        self.state.profession_system.tick_cooldowns()

        if not self.enemies:
            self._end_combat("victory")

        self.combat_round += 1
        return result

    def player_defend(self) -> dict:
        """玩家防御（本回合防御翻倍）"""
        armor = self.state.player.equipment.get_armor()
        armor_def = armor.item_data.get("def", 0) if armor and not armor.is_broken else 0
        head = self.state.player.equipment.get_helmet()
        head_def = head.item_data.get("def", 0) if head and not head.is_broken else 0
        base_def = self.state.player_stats.defense + armor_def + head_def

        # 职业防御加成
        prof_effects = {}
        if self.state.profession_system.player_profession:
            prof_effects = self.state.profession_system.player_profession.passive_effects
        if "def_mult" in prof_effects:
            base_def = int(base_def * prof_effects["def_mult"])

        self.state.player_stats.defense += base_def

        event_bus.emit(EVT.MESSAGE, {"text": "🛡️ 你举起防御姿态！"})

        # 触发随机事件
        if self.enemies:
            self._trigger_random_event()

        result = self._enemy_turn()

        self.state.player_stats.defense -= base_def
        self._tick_buffs()
        self.state.profession_system.tick_cooldowns()

        if not self.enemies:
            self._end_combat("victory")

        self.combat_round += 1
        return {"type": "defend", "enemy_actions": result}

    def player_flee(self) -> bool:
        """尝试逃跑"""
        if not self.can_flee:
            event_bus.emit(EVT.MESSAGE, {"text": "无法逃跑！"})
            return False

        # 逃跑概率加成
        flee_chance = 0.5
        prof_effects = {}
        if self.state.profession_system.player_profession:
            prof_effects = self.state.profession_system.player_profession.passive_effects
        talent_effects = self.state.talent_system.get_passive_effects()

        if "flee_bonus" in talent_effects:
            flee_chance += talent_effects["flee_bonus"]

        if random.random() < flee_chance:
            event_bus.emit(EVT.MESSAGE, {"text": "🏃 你成功逃离了战斗！"})
            self._end_combat("flee")
            return True
        else:
            event_bus.emit(EVT.MESSAGE, {"text": "逃跑失败！"})
            self._trigger_random_event()
            self._enemy_turn()
            if not self.state.player_stats.is_alive():
                self._end_combat("defeat")
            self.combat_round += 1
            return False

    def use_item_in_combat(self, item_id: str) -> bool:
        """在战斗中使用物品"""
        from systems.survival import SurvivalSystem
        survival = SurvivalSystem(self.state)
        result = survival.use_item(item_id)
        if result:
            # 触发随机事件
            if self.enemies:
                self._trigger_random_event()
            self._enemy_turn()
            self._tick_buffs()
            if not self.enemies:
                self._end_combat("victory")
            self.combat_round += 1
        return result

    def _trigger_random_event(self):
        """触发战斗随机事件"""
        if not self.random_events:
            return

        for event in self.random_events:
            if random.random() < event["chance"]:
                event_bus.emit(EVT.MESSAGE, {"text": f"\n  ⚡ {event['name']}！{event['desc']}"})
                self._apply_random_event(event)
                return  # 每回合最多一个事件

    def _apply_random_event(self, event: Dict):
        """应用随机事件效果"""
        effect = event["effect"]

        if effect == "spawn_extra":
            # 额外敌人
            count = random.randint(*event["extra_count"])
            island = self.state.current_island
            if island.creature_ids:
                for _ in range(count):
                    cid = random.choice(island.creature_ids)
                    creature = self.state.create_creature(cid)
                    if creature:
                        self.enemies.append(creature)
                        event_bus.emit(EVT.MESSAGE, {"text": f"  {creature.name}加入了战斗！"})

        elif effect == "bonus_damage":
            # 额外伤害
            if self.enemies:
                enemy = self.enemies[0]
                bonus_dmg = int(self.state.player_stats.atk * event["damage_mult"])
                actual = enemy.take_damage(bonus_dmg)
                event_bus.emit(EVT.MESSAGE, {"text": f"  对{enemy.name}造成额外{actual}点伤害！"})
                if not enemy.is_alive():
                    self._handle_enemy_death(enemy)
                    self.enemies.remove(enemy)

        elif effect == "drop_chest":
            # 掉落宝箱
            tier = event.get("chest_tier", "green")
            chest = self.state.gameplay_data["chest_tiers"].get(tier)
            if chest:
                event_bus.emit(EVT.MESSAGE, {"text": f"  📦 获得了{chest['icon']} {chest['name']}！"})

        elif effect == "heal":
            # 恢复HP
            heal_amount = int(self.state.player_stats.max_hp * event["heal_percent"])
            actual = self.state.player_stats.heal(heal_amount)
            event_bus.emit(EVT.MESSAGE, {"text": f"  恢复了{actual}点HP"})

        elif effect == "enemy_flee":
            # 敌人逃跑
            flee_count = max(1, int(len(self.enemies) * event["flee_percent"]))
            for _ in range(flee_count):
                if self.enemies:
                    fled = self.enemies.pop()
                    event_bus.emit(EVT.MESSAGE, {"text": f"  {fled.name}逃跑了！"})

        elif effect == "atk_boost":
            # 攻击力提升
            self.temp_buffs["random_atk_boost"] = {
                "effects": {"atk_mult": event["atk_mult"]},
                "remaining": event.get("duration", 2),
                "name": "力量爆发"
            }
            event_bus.emit(EVT.MESSAGE, {"text": f"  攻击力提升{int((event['atk_mult']-1)*100)}%，持续{event.get('duration', 2)}回合"})

        elif effect == "player_damage":
            # 玩家受伤
            dmg = random.randint(*event["damage"])
            actual = self.state.player_stats.take_damage(dmg)
            event_bus.emit(EVT.MESSAGE, {"text": f"  你受到了{actual}点伤害！"})

        elif effect == "random_buff":
            # 随机增益
            buff = random.choice(event["buff_options"])
            if buff == "atk_up":
                self.temp_buffs["random_atk"] = {
                    "effects": {"atk_mult": 1.3},
                    "remaining": 3,
                    "name": "力量提升"
                }
                event_bus.emit(EVT.MESSAGE, {"text": "  攻击力提升30%，持续3回合！"})
            elif buff == "def_up":
                self.temp_buffs["random_def"] = {
                    "effects": {"def_mult": 1.5},
                    "remaining": 3,
                    "name": "防御提升"
                }
                event_bus.emit(EVT.MESSAGE, {"text": "  防御力提升50%，持续3回合！"})
            elif buff == "heal_full":
                self.state.player_stats.hp = self.state.player_stats.max_hp
                event_bus.emit(EVT.MESSAGE, {"text": "  HP完全恢复！"})

        elif effect == "all_damage":
            # 全体受伤
            player_dmg = random.randint(*event["player_damage"])
            enemy_dmg = random.randint(*event["enemy_damage"])
            self.state.player_stats.take_damage(player_dmg)
            for e in self.enemies:
                e.take_damage(enemy_dmg)
            event_bus.emit(EVT.MESSAGE, {"text": f"  你受到{player_dmg}点伤害，敌人受到{enemy_dmg}点伤害"})

    def _tick_buffs(self):
        """更新增益持续时间"""
        expired = []
        for buff_id, buff in self.temp_buffs.items():
            buff["remaining"] -= 1
            if buff["remaining"] <= 0:
                expired.append(buff_id)
        for bid in expired:
            del self.temp_buffs[bid]

    def _enemy_turn(self) -> list:
        """敌人回合"""
        actions = []
        # v2: 使用装备槽位获取防御
        armor = self.state.player.equipment.get_armor()
        armor_def = armor.item_data.get("def", 0) if armor and not armor.is_broken else 0
        head = self.state.player.equipment.get_helmet()
        head_def = head.item_data.get("def", 0) if head and not head.is_broken else 0
        base_defense = self.state.player_stats.defense + armor_def + head_def

        # 职业防御加成
        prof_effects = {}
        if self.state.profession_system.player_profession:
            prof_effects = self.state.profession_system.player_profession.passive_effects
        if "def_mult" in prof_effects:
            base_defense = int(base_defense * prof_effects["def_mult"])

        # 临时增益
        for buff_id, buff in self.temp_buffs.items():
            if "def_mult" in buff.get("effects", {}):
                base_defense = int(base_defense * buff["effects"]["def_mult"])

        for enemy in self.enemies:
            if not enemy.is_alive():
                continue

            # 检查冰冻
            frozen = False
            for buff_id, buff in self.temp_buffs.items():
                if buff.get("effects", {}).get("frozen"):
                    frozen = True
                    break
            if frozen:
                event_bus.emit(EVT.MESSAGE, {"text": f"❄️ {enemy.name}被冻结，无法行动！"})
                continue

            # 敌人攻击
            damage = max(1, enemy.atk - base_defense)
            damage = int(damage * random.uniform(0.8, 1.2))
            damage = max(1, damage)

            # 闪避判定
            dodge_chance = self.state.player_stats.dodge_chance
            if "dodge_chance" in prof_effects:
                dodge_chance += prof_effects["dodge_chance"]
            for buff_id, buff in self.temp_buffs.items():
                if "dodge_mult" in buff.get("effects", {}):
                    dodge_chance += buff["effects"]["dodge_mult"]

            if random.random() < dodge_chance:
                event_bus.emit(EVT.MESSAGE, {"text": f"💨 你闪避了{enemy.name}的攻击！"})
                continue

            actual = self.state.player_stats.take_damage(damage)

            actions.append({
                "enemy": enemy.name,
                "damage": actual,
                "player_hp": self.state.player_stats.hp
            })

            event_bus.emit(EVT.COMBAT_HIT, {
                "source": enemy.name,
                "target": "player",
                "damage": actual,
                "hp": self.state.player_stats.hp
            })
            event_bus.emit(EVT.MESSAGE, {"text": f"🔴 {enemy.name}攻击了你，造成{actual}点伤害。（{self.state.player_stats.hp}/{self.state.player_stats.max_hp}）"})

            # 护甲耐久消耗（v2: 使用装备槽位）
            if armor and armor.durability > 0:
                broken = self.state.player.equipment.consume_armor_durability(1)
                if broken:
                    event_bus.emit(EVT.MESSAGE, {"text": f"你的{armor.name}损坏了！"})

            # 反甲/毒体等被动
            if "poison_on_hit_chance" in prof_effects:
                if random.random() < prof_effects["poison_on_hit_chance"]:
                    poison_dmg = int(enemy.max_hp * prof_effects.get("poison_damage_percent", 0.05))
                    enemy.take_damage(poison_dmg)
                    event_bus.emit(EVT.MESSAGE, {"text": f"☠️ {enemy.name}中毒了！受到{poison_dmg}点毒素伤害"})
                    if not enemy.is_alive():
                        self._handle_enemy_death(enemy)
                        self.enemies.remove(enemy)

            if not self.state.player_stats.is_alive():
                break

        # 检查玩家死亡 - 复活机制
        if not self.state.player_stats.is_alive():
            # 检查职业复活被动
            if not self.revive_used_this_battle:
                revive_percent = prof_effects.get("revive_percent", 0)
                if revive_percent > 0:
                    revive_hp = int(self.state.player_stats.max_hp * revive_percent)
                    self.state.player_stats.hp = revive_hp
                    self.revive_used_this_battle = True
                    event_bus.emit(EVT.MESSAGE, {"text": f"✨ 复活之光！恢复了{revive_hp}点HP！"})
                else:
                    event_bus.emit(EVT.PLAYER_DIED, {})
                    self._end_combat("defeat")
            else:
                event_bus.emit(EVT.PLAYER_DIED, {})
                self._end_combat("defeat")

        return actions

    def _handle_enemy_death(self, enemy: Creature):
        """处理敌人死亡"""
        # 经验
        exp = enemy.exp
        prof_effects = {}
        if self.state.profession_system.player_profession:
            prof_effects = self.state.profession_system.player_profession.passive_effects

        leveled = self.state.player_stats.add_exp(exp)
        event_bus.emit(EVT.MESSAGE, {"text": f"获得{exp}点经验！"})

        # 职业经验
        self.state.profession_system.add_profession_exp(exp // 2, self.state.player_stats)

        if leveled:
            event_bus.emit(EVT.LEVEL_UP, {"level": self.state.player_stats.level})

        # 掉落
        drops = enemy.roll_drops()
        if drops:
            loot_text = []
            for item_id, amount in drops.items():
                item_data = self.state.get_item_data(item_id)
                if item_data:
                    self.state.inventory.add_item(item_id, item_data, amount)
                    loot_text.append(f"{item_data['name']}×{amount}")
            event_bus.emit(EVT.LOOT_OBTAINED, {"rewards": drops})
            event_bus.emit(EVT.MESSAGE, {"text": f"掉落：{', '.join(loot_text)}"})

        # 检查是否是守护者
        island = self.state.current_island
        if enemy.id == island.guardian_id:
            island.guardian_defeated = True
            event_bus.emit(EVT.MESSAGE, {"text": f"🎉 你击败了{island.name}的守护者！现在可以前往其他空岛了！"})

    def _end_combat(self, result: str):
        """结束战斗"""
        self.in_combat = False
        self.enemies = []
        self.temp_buffs = {}
        self.combat_round = 0

        if result == "victory":
            event_bus.emit(EVT.COMBAT_VICTORY, {})
        elif result == "defeat":
            event_bus.emit(EVT.COMBAT_DEFEAT, {})
        elif result == "flee":
            event_bus.emit(EVT.COMBAT_FLEE, {})
