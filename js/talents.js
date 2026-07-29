// talents.js - 天赋系统模块
import { G } from './state.js';

export const TALENT_GRADES = ['SSS','SS','S','A','B','C','D','E','F'];
export const TALENT_GRADE_WEIGHTS = { SSS:2, SS:4, S:8, A:15, B:25, C:35, D:45, E:50, F:60 };

export const START_TALENTS = [
  // === SSS级天赋（传说级，极稀有）===
  { id:'time_lord', name:'时间领主', icon:'⏳', grade:'SSS', desc:'所有操作不消耗时间，时间流速+50%', effects:{timeSave:1, timeSpeedMult:1.5} },
  { id:'void_sovereign', name:'虚空君主', icon:'🌀', grade:'SSS', desc:'虚空伤害+50%，虚空免疫，全属性+20%', effects:{voidDmgBonus:0.5,voidImmune:true,allStatsMult:1.2} },
  { id:'fate_weaver', name:'命运编织者', icon:'🎭', grade:'SSS', desc:'所有随机事件概率+30%，暴击+15%', effects:{randomEventBonus:0.3,critBonus:0.15} },
  { id:'immortal', name:'不朽之体', icon:'💀', grade:'SSS', desc:'HP不会降到0以下(10天CD)，全抗+30%', effects:{immortal:true,immortalCD:10,allResist:0.3} },
  { id:'chaos_lord', name:'混沌之主', icon:'🔥', grade:'SSS', desc:'攻击附带混沌伤害+40%，暴击时全体伤害', effects:{chaosDmg:0.4,critAoe:true} },
  { id:'star_forger', name:'星辉锻造师', icon:'⭐', grade:'SSS', desc:'制作品质+3阶，耐久+100%，材料消耗-30%', effects:{craftQualityUp:3,durabilityMult:2,materialSave:0.3} },
  { id:'world_tree', name:'世界树之子', icon:'🌳', grade:'SSS', desc:'植物生长+100%，每小时恢复全状态5%', effects:{growthSpeedMult:2,fullRegen:0.05} },
  { id:'abyss_walker', name:'深渊行者', icon:'🕳️', grade:'SSS', desc:'闪避+25%，暗影伤害+40%，夜间攻击+50%', effects:{dodgePct:0.25,shadowDmg:0.4,nightAtkMult:1.5} },

  // === SS级天赋（神话级）===
  { id:'dragon_blood', name:'龙血血脉', icon:'🐉', grade:'SS', desc:'HP上限+30%，攻击+20%，火抗+40%', effects:{maxHpMult:1.3,atkMult:1.2,fireResist:0.4} },
  { id:'phoenix_heart', name:'凤凰之心', icon:'🔥', grade:'SS', desc:'死亡时自动复活(50%HP,7天CD)，火伤+30%', effects:{autoRevive:0.5,reviveCD:7,fireDmg:0.3} },
  { id:'void_walker', name:'虚空行者', icon:'🌀', grade:'SS', desc:'虚空抗性+40%，探索效率+50%，闪避+15%', effects:{voidResist:0.4,exploreEffMult:1.5,dodgePct:0.15} },
  { id:'storm_caller', name:'风暴召唤者', icon:'⛈️', grade:'SS', desc:'暴风雨时攻击+40%，雷电伤害+35%', effects:{stormAtkMult:1.4,lightningDmg:0.35} },
  { id:'blood_emperor', name:'血之帝王', icon:'🩸', grade:'SS', desc:'吸血+20%，击杀回复15%HP，攻击+15%', effects:{lifesteal:0.2,killHealPct:0.15,atkMult:1.15} },
  { id:'crystal_sage', name:'水晶贤者', icon:'💎', grade:'SS', desc:'精神消耗-50%，MP恢复+100%，制作品质+2阶', effects:{mentalDecayMult:0.5,mpRegenMult:2,craftQualityUp:2} },
  { id:'shadow_monarch', name:'暗影君王', icon:'👤', grade:'SS', desc:'夜间攻击+40%，闪避+20%，暗抗+50%', effects:{nightAtkMult:1.4,dodgePct:0.2,darkResist:0.5} },
  { id:'earth_guardian', name:'大地守护者', icon:'🏔️', grade:'SS', desc:'防御+40%，建筑耐久+50%，采集+30%', effects:{defMult:1.4,buildDurMult:1.5,gatherMult:1.3} },

  // === S级天赋（传说级）===
  { id:'combat_legend', name:'战斗传说', icon:'⚔️', grade:'S', desc:'武器伤害+25%，暴击+12%，暴伤+30%', effects:{weaponDmgMult:1.25,critBonus:0.12,critDmgBonus:0.3} },
  { id:'survival_king', name:'生存之王', icon:'👑', grade:'S', desc:'饥饿/饮水消耗-40%，HP回复+40%，精力恢复+50%', effects:{hungerDecayMult:0.6,thirstDecayMult:0.6,hpRegenMult:1.4,energyRegenMult:1.5} },
  { id:'lucky_god', name:'幸运之神', icon:'🍀', grade:'S', desc:'全局幸运+25%，宝箱稀有+20%，暴击+10%', effects:{globalLuck:0.25,chestRareBonus:0.2,critBonus:0.1} },
  { id:'iron_body', name:'金刚不坏', icon:'🛡️', grade:'S', desc:'受到伤害-15%，防御+30%，HP上限+20%', effects:{dmgReduce:0.15,defMult:1.3,maxHpMult:1.2} },
  { id:'nature_king', name:'自然之王', icon:'🌿', grade:'S', desc:'植物生长+60%，草药+50%，采集暴击+20%', effects:{growthSpeedMult:1.6,herbGatherMult:1.5,gatherCrit:0.2} },
  { id:'smithing_god', name:'锻造之神', icon:'🔥', grade:'S', desc:'制作品质+2阶，耐久+60%，材料消耗-20%', effects:{craftQualityUp:2,durabilityMult:1.6,materialSave:0.2} },
  { id:'explorer_king', name:'探索之王', icon:'🗺️', grade:'S', desc:'探索效率+60%，稀有事件+25%，闪避+12%', effects:{exploreEffMult:1.6,rareEventBonus:0.25,dodgePct:0.12} },
  { id:'berserker_king', name:'狂战之王', icon:'😤', grade:'S', desc:'HP每损失10%攻击+8%，暴击+8%，吸血+10%', effects:{berserkerAtkPer10Pct:0.08,critBonus:0.08,lifesteal:0.1} },

  // === A级天赋（史诗级）===
  { id:'weapon_master', name:'武器大师', icon:'⚔️', grade:'A', desc:'武器伤害+20%，暴击+8%', effects:{weaponDmgMult:1.2,critBonus:0.08} },
  { id:'shield_master', name:'盾牌大师', icon:'🛡️', grade:'A', desc:'防御+25%，格挡率+12%', effects:{defMult:1.25,blockChance:0.12} },
  { id:'archer', name:'神射手', icon:'🏹', grade:'A', desc:'远程伤害+25%，暴击+10%', effects:{rangeDmgMult:1.25,critBonus:0.1} },
  { id:'healer', name:'治愈者', icon:'💚', grade:'A', desc:'HP回复+50%，治疗效果+30%', effects:{hpRegenMult:1.5,healBonus:0.3} },
  { id:'scout', name:'侦察兵', icon:'👁️', grade:'A', desc:'探索效率+40%，遇敌率-20%', effects:{exploreEffMult:1.4,encounterReduce:0.2} },
  { id:'blacksmith', name:'铁匠', icon:'🔨', grade:'A', desc:'制作品质+1阶，耐久+40%', effects:{craftQualityUp:1,durabilityMult:1.4} },
  { id:'farmer', name:'农夫', icon:'🌾', grade:'A', desc:'植物生长+40%，采集+25%', effects:{growthSpeedMult:1.4,gatherMult:1.25} },
  { id:'fisher', name:'渔夫', icon:'🎣', grade:'A', desc:'钓鱼成功率+30%，稀有鱼+20%', effects:{fishSuccessMult:1.3,rareFishBonus:0.2} },
  { id:'hunter', name:'猎人', icon:'🎯', grade:'A', desc:'对野兽伤害+30%，击杀经验+25%', effects:{beastDmgBonus:0.3,killExpMult:1.25} },
  { id:'miner', name:'矿工', icon:'⛏️', grade:'A', desc:'采矿产出+35%，稀有矿+15%', effects:{mineMult:1.35,rareOreBonus:0.15} },
  { id:'lumberjack', name:'伐木工', icon:'🪓', grade:'A', desc:'伐木产出+35%，稀有木+15%', effects:{woodMult:1.35,rareWoodBonus:0.15} },
  { id:'alchemist', name:'炼金术师', icon:'⚗️', grade:'A', desc:'药剂效果+30%，持续时间+50%', effects:{potionBonus:0.3,potionDurationMult:1.5} },
  { id:'enchanter', name:'附魔师', icon:'✨', grade:'A', desc:'附魔成功率+25%，附魔效果+20%', effects:{enchantSuccessBonus:0.25,enchantBonus:0.2} },
  { id:'necromancer', name:'死灵法师', icon:'💀', grade:'A', desc:'暗伤害+25%，击杀回复10%HP', effects:{darkDmg:0.25,killHealPct:0.1} },
  { id:'paladin', name:'圣骑士', icon:'⭐', grade:'A', desc:'光伤害+25%，防御+15%，HP回复+20%', effects:{lightDmg:0.25,defMult:1.15,hpRegenMult:1.2} },
  { id:'rogue', name:'潜行者', icon:'🗡️', grade:'A', desc:'暴击+12%，闪避+10%，先手+20%', effects:{critBonus:0.12,dodgePct:0.1,initiativeBonus:0.2} },
  { id:'elementalist', name:'元素使', icon:'🌈', grade:'A', desc:'元素伤害+20%，元素抗性+20%', effects:{elementDmg:0.2,elementResist:0.2} },

  // === B级天赋（稀有级）===
  { id:'tough', name:'坚韧', icon:'💪', grade:'B', desc:'HP上限+15%，防御+10%', effects:{maxHpMult:1.15,defMult:1.1} },
  { id:'quick', name:'迅捷', icon:'⚡', grade:'B', desc:'闪避+8%，先手+15%', effects:{dodgePct:0.08,initiativeBonus:0.15} },
  { id:'keen_eye', name:'鹰眼', icon:'🦅', grade:'B', desc:'暴击+8%，暴伤+20%', effects:{critBonus:0.08,critDmgBonus:0.2} },
  { id:'thick_skin', name:'厚皮', icon:'🦏', grade:'B', desc:'受到伤害-8%', effects:{dmgReduce:0.08} },
  { id:'iron_will', name:'钢铁意志', icon:'🧠', grade:'B', desc:'精神消耗-40%', effects:{mentalDecayMult:0.6} },
  { id:'treasure_hunter', name:'寻宝猎人', icon:'💰', grade:'B', desc:'宝箱掉落+20%，稀有+8%', effects:{chestDropBonus:0.2,rareDropBonus:0.08} },
  { id:'nature_affinity', name:'自然亲和', icon:'🌿', grade:'B', desc:'植物+30%，草药+40%', effects:{growthSpeedMult:1.3,herbGatherMult:1.4} },
  { id:'void_blood', name:'虚空血脉', icon:'🩸', grade:'B', desc:'虚空伤害-25%，虚空生物+15%', effects:{voidResist:0.25,voidDmgBonus:0.15} },
  { id:'smithing_genius', name:'锻造天才', icon:'🔥', grade:'B', desc:'制作品+1阶，耐久+30%', effects:{craftQualityUp:1,durabilityMult:1.3} },
  { id:'explorer_spirit', name:'探索精神', icon:'🗺️', grade:'B', desc:'探索+35%，稀有事件+15%', effects:{exploreEffMult:1.35,rareEventBonus:0.15} },
  { id:'survivalist', name:'生存专家', icon:'🏕️', grade:'B', desc:'饥渴-25%，HP回复+20%', effects:{hungerDecayMult:0.75,thirstDecayMult:0.75,hpRegenMult:1.2} },
  { id:'lucky_star', name:'福星高照', icon:'⭐', grade:'B', desc:'全局幸运+15%，暴击+5%', effects:{globalLuck:0.15,critBonus:0.05} },
  { id:'bloodlust', name:'嗜血', icon:'🩸', grade:'B', desc:'击杀回复8%HP，攻击+5%', effects:{killHealPct:0.08,atkMult:1.05} },
  { id:'guardian_angel', name:'守护天使', icon:'😇', grade:'B', desc:'致命时30%存活(10天CD)', effects:{deathSaveChance:0.3,deathSaveCD:10} },
  { id:'berserker_blood', name:'狂战士之血', icon:'😤', grade:'B', desc:'HP每损10%攻击+6%', effects:{berserkerAtkPer10Pct:0.06} },
  { id:'fire_resist', name:'火焰抗性', icon:'🔥', grade:'B', desc:'火伤-30%，火伤+15%', effects:{fireResist:0.3,fireDmg:0.15} },
  { id:'ice_resist', name:'寒冰抗性', icon:'❄️', grade:'B', desc:'冰伤-30%，冰伤+15%', effects:{iceResist:0.3,iceDmg:0.15} },
  { id:'poison_resist', name:'毒素抗性', icon:'☠️', grade:'B', desc:'中毒免疫，毒素伤害+20%', effects:{poisonImmune:true,poisonDmg:0.2} },

  // === C级天赋（精良级）===
  { id:'gathering_plus', name:'采集精通', icon:'🌾', grade:'C', desc:'采集产出+20%', effects:{gatherMult:1.2} },
  { id:'crafting_plus', name:'制作精通', icon:'🔨', grade:'C', desc:'制作消耗-15%', effects:{materialSave:0.15} },
  { id:'combat_plus', name:'战斗精通', icon:'⚔️', grade:'C', desc:'攻击+10%', effects:{atkMult:1.1} },
  { id:'defense_plus', name:'防御精通', icon:'🛡️', grade:'C', desc:'防御+15%', effects:{defMult:1.15} },
  { id:'speed_plus', name:'速度精通', icon:'⚡', grade:'C', desc:'闪避+6%', effects:{dodgePct:0.06} },
  { id:'hp_plus', name:'生命精通', icon:'❤️', grade:'C', desc:'HP上限+12%', effects:{maxHpMult:1.12} },
  { id:'hunger_slow', name:'饱腹', icon:'🍖', grade:'C', desc:'饥饿消耗-20%', effects:{hungerDecayMult:0.8} },
  { id:'water_slow', name:'节水', icon:'💧', grade:'C', desc:'饮水消耗-20%', effects:{thirstDecayMult:0.8} },
  { id:'mental_shield', name:'精神屏障', icon:'🧠', grade:'C', desc:'精神消耗-25%', effects:{mentalDecayMult:0.75} },
  { id:'fish_plus', name:'垂钓精通', icon:'🎣', grade:'C', desc:'钓鱼成功率+20%', effects:{fishSuccessMult:1.2} },
  { id:'mine_plus', name:'采矿精通', icon:'⛏️', grade:'C', desc:'采矿产出+20%', effects:{mineMult:1.2} },
  { id:'wood_plus', name:'伐木精通', icon:'🪓', grade:'C', desc:'伐木产出+20%', effects:{woodMult:1.2} },
  { id:'herb_plus', name:'草药精通', icon:'🌿', grade:'C', desc:'草药采集+25%', effects:{herbGatherMult:1.25} },
  { id:'explore_plus', name:'探索精通', icon:'🗺️', grade:'C', desc:'探索效率+25%', effects:{exploreEffMult:1.25} },
  { id:'crit_plus', name:'暴击精通', icon:'💥', grade:'C', desc:'暴击+5%', effects:{critBonus:0.05} },
  { id:'lifesteal_plus', name:'吸血', icon:'🧛', grade:'C', desc:'吸血+5%', effects:{lifesteal:0.05} },
  { id:'potion_plus', name:'药剂精通', icon:'🧪', grade:'C', desc:'药剂效果+20%', effects:{potionBonus:0.2} },

  // === D级天赋（普通级）===
  { id:'minor_str', name:'微力', icon:'💪', grade:'D', desc:'攻击+5%', effects:{atkMult:1.05} },
  { id:'minor_def', name:'微盾', icon:'🛡️', grade:'D', desc:'防御+5%', effects:{defMult:1.05} },
  { id:'minor_hp', name:'微生', icon:'❤️', grade:'D', desc:'HP上限+5%', effects:{maxHpMult:1.05} },
  { id:'minor_dodge', name:'微闪', icon:'💨', grade:'D', desc:'闪避+3%', effects:{dodgePct:0.03} },
  { id:'minor_crit', name:'微击', icon:'💥', grade:'D', desc:'暴击+3%', effects:{critBonus:0.03} },
  { id:'minor_gather', name:'微采', icon:'🌾', grade:'D', desc:'采集+10%', effects:{gatherMult:1.1} },
  { id:'minor_fish', name:'微钓', icon:'🎣', grade:'D', desc:'钓鱼+10%', effects:{fishSuccessMult:1.1} },
  { id:'minor_craft', name:'微制', icon:'🔨', grade:'D', desc:'制作消耗-8%', effects:{materialSave:0.08} },
  { id:'minor_explore', name:'微探', icon:'🗺️', grade:'D', desc:'探索+10%', effects:{exploreEffMult:1.1} },
  { id:'minor_hunger', name:'微饱', icon:'🍖', grade:'D', desc:'饥饿-10%', effects:{hungerDecayMult:0.9} },
  { id:'minor_water', name:'微饮', icon:'💧', grade:'D', desc:'饮水-10%', effects:{thirstDecayMult:0.9} },
  { id:'minor_mental', name:'微智', icon:'🧠', grade:'D', desc:'精神-10%', effects:{mentalDecayMult:0.9} },

  // === E级天赋（粗糙级）===
  { id:'tiny_str', name:'微薄之力', icon:'💪', grade:'E', desc:'攻击+3%', effects:{atkMult:1.03} },
  { id:'tiny_def', name:'微薄之盾', icon:'🛡️', grade:'E', desc:'防御+3%', effects:{defMult:1.03} },
  { id:'tiny_hp', name:'微薄之血', icon:'❤️', grade:'E', desc:'HP+3%', effects:{maxHpMult:1.03} },
  { id:'tiny_gather', name:'微薄之采', icon:'🌾', grade:'E', desc:'采集+5%', effects:{gatherMult:1.05} },
  { id:'tiny_fish', name:'微薄之钓', icon:'🎣', grade:'E', desc:'钓鱼+5%', effects:{fishSuccessMult:1.05} },
  { id:'tiny_explore', name:'微薄之探', icon:'🗺️', grade:'E', desc:'探索+5%', effects:{exploreEffMult:1.05} },

  // === F级天赋（废物级，但有隐藏效果）===
  { id:'cursed', name:'被诅咒者', icon:'💀', grade:'F', desc:'全属性-5%，但暴击+10%', effects:{allStatsMult:0.95,critBonus:0.1} },
  { id:'clumsy', name:'笨拙', icon:'🤕', grade:'F', desc:'闪避-5%，但防御+10%', effects:{dodgePct:-0.05,defMult:1.1} },
  { id:'sickly', name:'病弱', icon:'🤒', grade:'F', desc:'HP-10%，但精神+20%', effects:{maxHpMult:0.9,mentalMult:1.2} },
  { id:'unlucky', name:'倒霉蛋', icon:'🍀', grade:'F', desc:'幸运-15%，但经验+25%', effects:{globalLuck:-0.15,expMult:1.25} },
  { id:'hungry', name:'饥饿体质', icon:'🍖', grade:'F', desc:'饥饿+30%，但攻击+15%', effects:{hungerDecayMult:1.3,atkMult:1.15} },
  { id:'thirsty', name:'干渴体质', icon:'💧', grade:'F', desc:'饮水+30%，但采集+20%', effects:{thirstDecayMult:1.3,gatherMult:1.2} },
  { id:'fragile', name:'脆弱', icon:'💔', grade:'F', desc:'防御-10%，但暴伤+40%', effects:{defMult:0.9,critDmgBonus:0.4} },
  { id:'slow', name:'迟钝', icon:'🐌', grade:'F', desc:'速度-10%，但HP回复+30%', effects:{speedMult:0.9,hpRegenMult:1.3} },
];

// 按等级权重随机选择3个天赋
export function getRandomTalents(count=3) {
  const weighted = [];
  for (const t of START_TALENTS) {
    const w = TALENT_GRADE_WEIGHTS[t.grade] || 50;
    for (let i = 0; i < w; i++) weighted.push(t);
  }
  const chosen = [];
  const usedIds = new Set();
  while (chosen.length < count && chosen.length < START_TALENTS.length) {
    const t = weighted[Math.floor(Math.random() * weighted.length)];
    if (!usedIds.has(t.id)) { usedIds.add(t.id); chosen.push(t); }
  }
  return chosen;
}

// 应用天赋效果
export function applyTalentEffects() {
  if (!G) return;
  G._talentEffects = {};
  if (G.chosenTalent) {
    const t = START_TALENTS.find(x=>x.id===G.chosenTalent);
    if (t) G._talentEffects = {...t.effects};
  }
}

// 获取天赋效果值
export function getTalentEffect(key, def=0) {
  return G?._talentEffects ? (G._talentEffects[key]||def) : def;
}

// 获取天赋倍率
export function getTalentMult(key, def=1) {
  return G?._talentEffects ? (G._talentEffects[key]||def) : def;
}
