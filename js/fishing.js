// fishing.js - 钓鱼系统模块
import { G } from './state.js';
import { getTalentEffect, getTalentMult } from './talents.js';
import { unequipBrokenItems } from './equipment.js';

// 开始钓鱼
export function startFishing() {
  if (G.fishingInProgress) { addLog('⏳ 正在钓鱼...', 'warning'); return; }
  const hasRod = G.equippedRod || hasItem('fishing_rod') || hasItem('wood_rod') || hasItem('iron_rod') || hasItem('crystal_rod');
  if (!hasRod) {
    addLog('❌ 需要钓竿才能钓鱼！', 'warning');
    return;
  }
  if ((G.stats.energy || 0) < 2) {
    addLog('❌ 精力不足！（需要2精力）', 'warning');
    return;
  }
  G.stats.energy -= 2;
  renderStatusBar();

  G.fishingInProgress = true;
  const fishTime = (1 + Math.floor(Math.random() * 30)) * 1000;
  addLog('🎣 开始钓鱼...', 'system');
  renderFishing();

  setTimeout(() => {
    G.fishingInProgress = false;
    G.fishingCount++;
    addExp(8 + Math.floor(Math.random()*5));
    G.currentActivity = 'fishing';

    // 钓竿耐久
    if (G.player) {
      const rod = G.player.equipment.getRod();
      if (rod) {
        rod.consumeDurability(1);
        if (rod.isBroken) addLog('💔 钓竿损坏了！', 'warning');
        G.player.equipment.syncToLegacy();
      }
    } else if (G.equippedRod) {
      const rodId = G.equippedRod;
      if (!G.toolDurability[rodId]) {
        const rodDef = getItemDef(rodId);
        G.toolDurability[rodId] = rodDef?.durability || 20;
      }
      G.toolDurability[rodId]--;
      if (G.toolDurability[rodId] <= 0) {
        addLog('💔 钓竿损坏了！', 'warning');
        delete G.toolDurability[rodId];
        G.equippedRod = null;
      }
    }

    // 钓到鱼
    const catch_ = determineFishCatch();
    addInventoryItem(catch_.id, catch_.count);
    addLog(`🎣 钓到了：${getItemName(catch_.id)} x${catch_.count}`, 'loot');

    // 消耗钓饵
    if (G.player) {
      const bait = G.player.equipment.getBait();
      if (bait) {
        G.player.equipment.unequip(EquipSlot.BAIT);
        G.player.equipment.syncToLegacy();
      }
    } else if (G.equippedBait && hasItem(G.equippedBait)) {
      removeInventoryItem(G.equippedBait);
      if (!hasItem(G.equippedBait)) G.equippedBait = null;
    }

    // 宝箱掉落
    let chestChance = 0.35 + getTalentEffect('chestDropBonus', 0) + getTalentEffect('globalLuck', 0);
    if (Math.random() < chestChance) {
      const tier = rollChestTier();
      openChest(tier);
    }

    // 职业书掉落
    if (Math.random() < 0.05) {
      const basicProf = ['profession_book_guardian','profession_book_pioneer','profession_book_smith','profession_book_hunter','profession_book_healer','profession_book_rogue','profession_book_priest','profession_book_alchemist','profession_book_berserker'];
      const advProf = ['profession_book_skywalker','profession_book_enchanter','profession_book_commander','profession_book_necromancer','profession_book_ranger'];
      const legendaryProf = ['profession_book_paladin','profession_book_shadow_king'];
      const mythicProf = ['profession_book_void_sovereign'];
      let pool;
      if (G.day >= 60 && Math.random() < 0.1) pool = [...mythicProf, ...legendaryProf];
      else if (G.day >= 40 && Math.random() < 0.2) pool = [...legendaryProf, ...advProf];
      else if (G.day >= 20) pool = [...basicProf, ...advProf];
      else pool = basicProf;
      const book = pool[Math.floor(Math.random()*pool.length)];
      addInventoryItem(book, 1);
      addLog(`📖 获得了${getItemName(book)}！`, 'loot');
    }

    renderFishing();
    renderAll();
  }, fishTime);
}

// 决定钓到什么鱼
export function determineFishCatch() {
  let qualityBonus = 0;
  if (G.equippedBait) {
    const baitDef = getItemDef(G.equippedBait);
    if (baitDef && baitDef.quality_bonus) qualityBonus = baitDef.quality_bonus;
  }

  const fishBonus = getTalentEffect('fishSuccessMult', 0);
  const rareFishBonus = getTalentEffect('rareFishBonus', 0);
  qualityBonus += fishBonus + rareFishBonus;

  const isNight = !isDaytime();
  let nightBonus = isNight ? 0.15 : 0;

  const day = G.day;
  let dayBonus = Math.min(0.1, day * 0.002);

  const r = Math.random();

  if (isNight && r < 0.08 + qualityBonus * 0.5) {
    const nightFish = ['moonfish', 'shadow_eel', 'starfish'];
    return {id: nightFish[Math.floor(Math.random()*nightFish.length)], count: 1};
  }

  if (G.weather === 'void_storm' && r < 0.15) {
    return {id:'void_fish', count: 1};
  }

  if (day >= 30 && r < 0.05 + dayBonus + qualityBonus * 0.3) {
    return {id:'legendary_fish', count: 1};
  }

  if (r < 0.15 + qualityBonus * 0.5 + nightBonus) {
    return {id:'rare_fish', count: 1 + Math.floor(Math.random()*2)};
  }

  if (r < 0.5 + qualityBonus * 0.2) {
    return {id:'common_fish', count: 1 + Math.floor(Math.random()*3)};
  }

  return {id:'raw_fish', count: 1 + Math.floor(Math.random()*2)};
}

// 需要从外部注入的函数
let getItemDef, hasItem, isDaytime, removeInventoryItem, EquipSlot;
let addLog, addExp, addInventoryItem, getItemName, rollChestTier, openChest;
let renderFishing, renderAll, renderStatusBar;

export function injectFishingDeps(deps) {
  getItemDef = deps.getItemDef;
  hasItem = deps.hasItem;
  isDaytime = deps.isDaytime;
  removeInventoryItem = deps.removeInventoryItem;
  EquipSlot = deps.EquipSlot;
  addLog = deps.addLog;
  addExp = deps.addExp;
  addInventoryItem = deps.addInventoryItem;
  getItemName = deps.getItemName;
  rollChestTier = deps.rollChestTier;
  openChest = deps.openChest;
  renderFishing = deps.renderFishing;
  renderAll = deps.renderAll;
  renderStatusBar = deps.renderStatusBar;
}
