// combat.js - 战斗系统模块
import { G } from './state.js';
import { getTalentEffect, getTalentMult } from './talents.js';
import { unequipBrokenItems } from './equipment.js';

let combatState = null;

export function getCombatState() { return combatState; }
export function setCombatState(val) { combatState = val; }

// 计算玩家攻击力
export function calcPlayerAtk() {
  let atk = G.stats.atk || 5;
  const weapon = G.player ? G.player.equipment.getWeapon() : null;
  if (weapon && !weapon.isBroken) {
    atk += weapon.atk;
    const wb = getAffixBonuses(weapon.itemId);
    atk += wb.atk || 0;
    atk += wb.fireDmg || 0;
    atk += wb.iceDmg || 0;
    atk += wb.voidDmg || 0;
    atk += wb.armorPen || 0;
  } else if (G.equippedWeapon) {
    const wdef = getItemDef(G.equippedWeapon);
    if (wdef) atk += wdef.atk || 0;
    const wb = getAffixBonuses(G.equippedWeapon);
    atk += wb.atk || 0;
    atk += wb.fireDmg || 0;
    atk += wb.iceDmg || 0;
    atk += wb.voidDmg || 0;
    atk += wb.armorPen || 0;
  }
  atk += getEffectiveAttr('str') * 2;
  atk *= getTalentMult('allStatsMult', 1);
  atk *= getTalentMult('atkMult', 1);
  atk *= getTalentMult('weapon_dmg_mult', 1);
  atk += getTalentEffect('fireDmg', 0);
  atk += getTalentEffect('iceDmg', 0);
  atk += getTalentEffect('voidDmgBonus', 0);
  atk += getTalentEffect('darkDmg', 0);
  atk += getTalentEffect('lightDmg', 0);
  atk += getTalentEffect('lightningDmg', 0);
  atk += getTalentEffect('chaosDmg', 0);
  atk += getTalentEffect('shadowDmg', 0);
  if (!isDaytime()) atk *= (1 + getTalentEffect('nightAtkMult', 0));
  if (G.weather === 'stormy') atk *= (1 + getTalentEffect('stormAtkMult', 0));
  if (hasProfession('hunter')) atk *= 1.2;
  return Math.floor(atk);
}

// 计算暴击率
export function getPlayerCritChance() {
  let cc = 0.05;
  cc += getEffectiveAttr('dex') * 0.01;
  cc += getTalentEffect('critBonus', 0);
  const weaponId = G.player ? (G.player.equipment.getWeapon()?.itemId) : G.equippedWeapon;
  if (weaponId) {
    const wb = getAffixBonuses(weaponId);
    cc += (wb.critPct || 0) / 100;
  }
  return Math.min(0.8, cc);
}

// 计算暴击伤害
export function getPlayerCritDmg() {
  let cd = 1.8;
  cd += getTalentEffect('critDmgBonus', 0);
  const weaponId = G.player ? (G.player.equipment.getWeapon()?.itemId) : G.equippedWeapon;
  if (weaponId) {
    const wb = getAffixBonuses(weaponId);
    cd += (wb.critDmg || 0) / 100;
  }
  return cd;
}

// 计算吸血
export function getPlayerLifesteal() {
  let ls = 0;
  ls += getTalentEffect('lifesteal', 0);
  const weaponId = G.player ? (G.player.equipment.getWeapon()?.itemId) : G.equippedWeapon;
  if (weaponId) {
    const wb = getAffixBonuses(weaponId);
    ls += (wb.lifesteal || 0) / 100;
  }
  return ls;
}

// 计算闪避
export function getPlayerDodgeBonus() {
  let dodge = 0;
  dodge += getTalentEffect('dodgePct', 0);
  const armorId = G.player ? (G.player.equipment.getArmor()?.itemId) : G.equippedArmor;
  const headId = G.player ? (G.player.equipment.getHelmet()?.itemId) : G.equippedHead;
  if (armorId) { const ab = getAffixBonuses(armorId); dodge += (ab.dodgePct || 0) / 100; }
  if (headId) { const hb = getAffixBonuses(headId); dodge += (hb.dodgePct || 0) / 100; }
  return dodge;
}

// 计算防御
export function calcPlayerDef() {
  let def = 0;
  if (G.player) {
    def = G.player.equipment.getTotalDef();
  } else {
    if (G.equippedArmor) {
      const adef = getItemDef(G.equippedArmor);
      if (adef) def += adef.def || 0;
      const ab = getAffixBonuses(G.equippedArmor);
      def += ab.def || 0;
      def += ab.dmgReduce || 0;
      def += ab.buildDef || 0;
    }
    if (G.equippedHead) {
      const hdef = getItemDef(G.equippedHead);
      if (hdef) def += hdef.def || 0;
      const hb = getAffixBonuses(G.equippedHead);
      def += hb.def || 0;
      def += hb.dmgReduce || 0;
    }
  }
  if (G.player) {
    const armor = G.player.equipment.getArmor();
    const helmet = G.player.equipment.getHelmet();
    if (armor && !armor.isBroken) {
      const ab = getAffixBonuses(armor.itemId);
      def += ab.dmgReduce || 0;
      def += ab.buildDef || 0;
    }
    if (helmet && !helmet.isBroken) {
      const hb = getAffixBonuses(helmet.itemId);
      def += hb.dmgReduce || 0;
    }
  }
  def += getTalentEffect('defense', 0);
  def *= getTalentMult('defMult', 1);
  def += Math.floor(def * getTalentEffect('dmgReduce', 0));
  def += Math.floor(def * getTalentEffect('allResist', 0));
  if (hasProfession('guardian')) def *= 1.25;
  if (combatState) def *= combatState.tempDefMult || 1;
  return Math.floor(def);
}

// 玩家攻击
export function playerAttack(targetIndex) {
  if (!combatState || !combatState.playerTurn) return;
  const target = combatState.enemies[targetIndex];
  if (!target || target.currentHp <= 0) return;

  unequipBrokenItems();
  if (G.player) {
    const weapon = G.player.equipment.getWeapon();
    if (weapon && weapon.isBroken) {
      addLog('❌ 武器已损坏！', 'warning');
      return;
    }
  }

  combatState.turn++;
  let atk = calcPlayerAtk();
  let critChance = getPlayerCritChance() + (combatState.guaranteedCrit ? 0.9 : 0);
  let isCrit = Math.random() < critChance;
  let critMult = getPlayerCritDmg();
  if (isCrit) atk = Math.floor(atk * critMult);

  let missChance = G.stats.mental <= 0 ? 0.4 : (G.stats.mental < 20 ? 0.15 : 0);
  if (Math.random() < missChance) {
    combatState.log.push(`你因精神恍惚，攻击落空了！`);
    addLog('🌀 攻击落空！（精神过低）', 'combat');
  } else {
    const def = target.def || 0;
    let dmg = Math.max(1, atk - def);
    if (hasProfession('guardian')) dmg = Math.floor(dmg * 1.18);
    target.currentHp -= dmg;
    const critText = isCrit ? ' 💥暴击！' : '';
    combatState.log.push(`你攻击${target.name}，造成${dmg}点伤害！${critText}`);
    addLog(`⚔️ 攻击${target.name}，${dmg}伤害${critText}`, 'combat');

    let lifesteal = getPlayerLifesteal();
    if (hasSkill('lifesteal')) lifesteal += 0.15;
    if (lifesteal > 0) {
      const heal = Math.floor(dmg * lifesteal);
      G.stats.hp = Math.min(G.stats.maxHp, G.stats.hp + heal);
      if (heal > 0) combatState.log.push(`吸取${heal}点生命！`);
    }

    if (G.player) {
      const broken = G.player.equipment.consumeWeaponDurability(1);
      if (broken) {
        const weapon = G.player.equipment.getWeapon();
        addLog(`💔 ${weapon ? weapon.name : '武器'}损坏了！`, 'warning');
        unequipBrokenItems();
      }
    } else if (G.equippedWeapon && G.toolDurability[G.equippedWeapon] != null) {
      G.toolDurability[G.equippedWeapon]--;
      if (G.toolDurability[G.equippedWeapon] <= 0) {
        addLog(`💔 ${getItemName(G.equippedWeapon)}损坏了！`, 'warning');
        G.equippedWeapon = null;
      }
    }
  }

  combatState.guaranteedCrit = false;
  if (target.currentHp <= 0) {
    combatState.log.push(`${target.name}被击败了！`);
    addLog(`💀 ${target.name}被击败！`, 'good');
    G.killCount++;
    const enemyExp = Math.max(5, Math.floor((target.maxHp || 10) * 0.5 + (target.atk || 3) * 2 + (target.reward_exp || 10)));
    addExp(enemyExp);
  }

  checkCombatEvent();
  combatState.playerTurn = false;
  setTimeout(() => enemyTurn(), 500);
  renderCombat();
}

// 敌人回合
export function enemyTurn() {
  if (!combatState) return;
  const alive = combatState.enemies.filter(e => e.currentHp > 0);
  if (alive.length === 0) {
    combatVictory();
    return;
  }

  const berserkerBonus = getTalentEffect('berserkerAtkPer10Pct', 0);
  if (berserkerBonus > 0) {
    const hpLostPct = 1 - (G.stats.hp / (G.stats.maxHp || 100));
    combatState.berserkerAtkBoost = 1 + Math.floor(hpLostPct * 10) * berserkerBonus;
  }

  for (const enemy of alive) {
    if (enemy.stunned) { enemy.stunned = false; continue; }

    let atk = enemy.atk || 5;
    if (hasProfession('guardian')) atk = Math.floor(atk * 0.82);
    if (combatState.tauntActive) atk = Math.floor(atk * 0.7);

    let def = calcPlayerDef();
    let dmg = Math.max(1, atk - def);

    const blockChance = getTalentEffect('blockChance', 0);
    if (blockChance > 0 && Math.random() < blockChance) {
      dmg = Math.floor(dmg * 0.5);
      combatState.log.push(`你格挡了${enemy.name}的攻击，伤害减半！`);
      addLog(`🛡️ 格挡！伤害减半`, 'good');
    }

    let dodgeChance = combatState.dodgeBonus || 0;
    dodgeChance += getPlayerDodgeBonus();
    if (Math.random() < dodgeChance) {
      combatState.log.push(`${enemy.name}攻击你，但你闪避了！`);
      addLog(`💨 闪避了${enemy.name}的攻击！`, 'good');
      continue;
    }

    if (enemy.name.includes('虚空')) {
      dmg = Math.floor(dmg * (1 - getTalentEffect('void_resist', 0)));
      if (hasProfession('skywalker')) dmg = Math.floor(dmg * 0.5);
    }
    if (enemy.name.includes('火')) dmg = Math.floor(dmg * (1 - getTalentEffect('fireResist', 0)));
    if (enemy.name.includes('冰')) dmg = Math.floor(dmg * (1 - getTalentEffect('iceResist', 0)));
    if (enemy.name.includes('暗')) dmg = Math.floor(dmg * (1 - getTalentEffect('darkResist', 0)));
    dmg = Math.floor(dmg * (1 - getTalentEffect('elementResist', 0)));
    dmg = Math.floor(dmg * (1 - getTalentEffect('allResist', 0)));
    dmg = Math.floor(dmg * (1 - getTalentEffect('dmgReduce', 0)));

    G.stats.hp -= dmg;
    combatState.log.push(`${enemy.name}攻击你，造成${dmg}点伤害！`);
    addLog(`🩸 ${enemy.name}对你造成${dmg}伤害`, 'combat');

    if (G.player) {
      const broken = G.player.equipment.consumeArmorDurability(1);
      if (broken) {
        const armor = G.player.equipment.getArmor();
        addLog(`💔 ${armor ? armor.name : '护甲'}损坏了！`, 'warning');
        unequipBrokenItems();
      }
    } else if (G.equippedArmor && G.toolDurability[G.equippedArmor] != null) {
      G.toolDurability[G.equippedArmor]--;
      if (G.toolDurability[G.equippedArmor] <= 0) {
        addLog(`💔 ${getItemName(G.equippedArmor)}损坏了！`, 'warning');
        G.equippedArmor = null;
      }
    }

    if (getTalentEffect('poison_on_hit_chance', 0) > 0 && Math.random() < 0.3) {
      enemy.poisoned = true;
      enemy.poisonTurns = 3;
      combatState.log.push(`毒素感染了${enemy.name}！`);
    }

    if (getTalentEffect('counter_chance', 0) > 0 && Math.random() < 0.4) {
      const counterDmg = Math.floor(calcPlayerAtk() * 0.8);
      enemy.currentHp -= counterDmg;
      combatState.log.push(`反击！对${enemy.name}造成${counterDmg}伤害！`);
    }
  }

  for (const enemy of alive) {
    if (enemy.poisoned && enemy.poisonTurns > 0) {
      const poisonDmg = Math.floor(enemy.maxHp * 0.05);
      enemy.currentHp -= poisonDmg;
      enemy.poisonTurns--;
      if (enemy.poisonTurns <= 0) enemy.poisoned = false;
      combatState.log.push(`${enemy.name}受到${poisonDmg}毒素伤害`);
    }
  }

  if (combatState.tauntActive) {
    combatState.tauntTurns--;
    if (combatState.tauntTurns <= 0) combatState.tauntActive = false;
  }

  combatState.tempDefMult = 1;

  for (const sid in G.skillCooldowns) {
    if (G.skillCooldowns[sid] > 0) G.skillCooldowns[sid]--;
  }

  if (G.stats.hp <= 0) {
    gameOver();
    return;
  }

  const stillAlive = combatState.enemies.filter(e => e.currentHp > 0);
  if (stillAlive.length === 0) {
    combatVictory();
    return;
  }

  combatState.playerTurn = true;
  renderCombat();
}

// 战斗胜利
export function combatVictory() {
  if (!combatState) return;
  let exp = 0;
  let lootText = [];

  const killHealPct = getTalentEffect('killHealPct', 0);
  if (killHealPct > 0) {
    const heal = Math.floor((G.stats.maxHp || 100) * killHealPct);
    G.stats.hp = Math.min(G.stats.maxHp || 100, G.stats.hp + heal);
    addLog(`💚 击杀回复${heal}HP`, 'good');
  }

  for (const enemy of combatState.enemies) {
    exp += enemy.reward_exp || 10;
    const drops = generateCombatLoot(enemy);
    for (const [itemId, count] of drops) {
      addInventoryItem(itemId, count);
      lootText.push(`${getItemName(itemId)} x${count}`);
    }
  }

  addLog(`🏆 战斗胜利！获得：${lootText.join(', ')}（+${exp}EXP）`, 'loot');
  addExp(exp);

  if (Math.random() < 0.2) {
    const chestTier = rollChestTier();
    openChest(chestTier);
  }

  combatState = null;
  hideCombat();
  checkAchievements();
  renderAll();
}

// 需要从外部注入的函数
let getItemDef, getAffixBonuses, getEffectiveAttr, isDaytime, hasProfession, hasSkill;
let addLog, addExp, addInventoryItem, getItemName, rollChestTier, openChest;
let checkCombatEvent, checkAchievements, gameOver, hideCombat, renderCombat, renderAll;

export function injectCombatDeps(deps) {
  getItemDef = deps.getItemDef;
  getAffixBonuses = deps.getAffixBonuses;
  getEffectiveAttr = deps.getEffectiveAttr;
  isDaytime = deps.isDaytime;
  hasProfession = deps.hasProfession;
  hasSkill = deps.hasSkill;
  addLog = deps.addLog;
  addExp = deps.addExp;
  addInventoryItem = deps.addInventoryItem;
  getItemName = deps.getItemName;
  rollChestTier = deps.rollChestTier;
  openChest = deps.openChest;
  checkCombatEvent = deps.checkCombatEvent;
  checkAchievements = deps.checkAchievements;
  gameOver = deps.gameOver;
  hideCombat = deps.hideCombat;
  renderCombat = deps.renderCombat;
  renderAll = deps.renderAll;
}
