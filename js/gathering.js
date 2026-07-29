// gathering.js - 采集系统模块
import { G } from './state.js';
import { getTalentEffect, getTalentMult } from './talents.js';
import { unequipBrokenItems } from './equipment.js';

// 检查是否有指定类型工具
export function hasTool(toolType) {
  if (G.player) {
    const tool = G.player.equipment.getTool();
    if (tool && !tool.isBroken && tool.itemData.tool_type === toolType) return true;
  } else if (G.equippedTool) {
    const def = getItemDef(G.equippedTool);
    if (def && def.tool_type === toolType) return true;
  }
  for (const [id, count] of Object.entries(G.inventory)) {
    if (count > 0) {
      const def = getItemDef(id);
      if (def && def.tool_type === toolType && def.type === 'tool') return true;
    }
  }
  return false;
}

// 采集资源
export function gatherResource(type) {
  if ((G.stats.energy || 0) < 4) {
    addLog('❌ 精力不足！（需要4精力）', 'warning');
    return;
  }
  G.stats.energy -= 4;
  renderStatusBar();

  const gatherMult = getTalentMult('gather_mult', 1) * (hasProfession('pioneer') ? 1.2 : 1);
  const harvestBonus = combatState && combatState.doubleHarvest ? 2 : 1;

  let weatherMult = 1;
  let weatherNote = '';
  if (G.weather === 'rainy') { weatherMult = 1.2; weatherNote = '（雨天+20%）'; }
  if (G.weather === 'stormy') { weatherMult = 0.5; weatherNote = '（暴风雨-50%）'; }
  if (G.weather === 'foggy') { weatherMult = 0.9; weatherNote = '（雾天）'; }

  let toolBonus = 0;
  if (G.player) {
    const tool = G.player.equipment.getTool();
    if (tool && !tool.isBroken) {
      toolBonus = tool.itemData.power || 1;
      tool.consumeDurability(1);
      if (tool.isBroken) {
        addLog(`💔 ${tool.name}损坏了！`, 'warning');
        unequipBrokenItems();
      }
      G.player.equipment.syncToLegacy();
    }
  } else if (G.equippedTool && G.toolDurability[G.equippedTool] > 0) {
    const toolDef = getItemDef(G.equippedTool);
    if (toolDef) {
      toolBonus = toolDef.power || 1;
      G.toolDurability[G.equippedTool]--;
      if (G.toolDurability[G.equippedTool] <= 0) {
        addLog(`💔 ${toolDef.name}损坏了！`, 'warning');
        delete G.toolDurability[G.equippedTool];
        G.equippedTool = null;
      }
    }
  }

  G.currentActivity = 'gathering';

  if (type === 'water') {
    const hasContainer = hasItem('water_skin') || hasItem('water_bucket') || G.equippedRod;
    if (!hasContainer) {
      addLog('❌ 需要水袋或水桶来装水！', 'warning');
      return;
    }
    const restore = hasItem('water_bucket') ? 35 : 20;
    G.stats.water = Math.min(100, G.stats.water + restore);
    addInventoryItem('freshwater', 1);
    addLog(`💧 取水成功！饮水+${restore}，获得淡水x1${weatherNote}`, 'good');
    return;
  }

  const woodMult = 1 + getTalentEffect('woodMult', 0);
  const mineMult = 1 + getTalentEffect('mineMult', 0);
  const herbMult = 1 + getTalentEffect('herbGatherMult', 0);

  let items = [];
  switch(type) {
    case 'wood':
      if (!hasTool('axe')) {
        addLog('❌ 没有斧头无法砍树！请先制作一把斧头。', 'warning');
        return;
      }
      items = [{id:'wood', min:2, max:Math.floor((5+toolBonus)*woodMult)}];
      if (Math.random() < 0.2) items.push({id:'fine_wood', min:1, max:1});
      break;
    case 'stone':
      if (!hasTool('pickaxe')) {
        addLog('❌ 没有镐无法采矿！请先制作一把镐。', 'warning');
        return;
      }
      items = [{id:'stone', min:2, max:Math.floor((4+toolBonus)*mineMult)}];
      if (Math.random() < 0.15) items.push({id:'iron_ore', min:1, max:2});
      if (Math.random() < 0.08) items.push({id:'copper_ore', min:1, max:1});
      break;
    case 'herb':
      items = [{id:'herb', min:1, max:Math.floor(3*herbMult)}];
      if (hasProfession('healer')) items[0].max += 2;
      if (Math.random() < 0.1) items.push({id:'herb_seed', min:1, max:1});
      break;
    case 'fiber':
      items = [{id:'fiber', min:2, max:4}];
      break;
    case 'explore':
      exploreIsland();
      return;
  }

  let results = [];
  for (const item of items) {
    let count = Math.floor((item.min + Math.random()*(item.max-item.min+1)) * gatherMult * harvestBonus * weatherMult);
    count = Math.max(1, count);
    addInventoryItem(item.id, count);
    results.push(`${getItemName(item.id)} x${count}`);
  }

  if (hasProfession('pioneer') && Math.random() < 0.2) {
    const rare = ['crystal','iron_ore','herb'];
    const rId = rare[Math.floor(Math.random()*rare.length)];
    addInventoryItem(rId, 1);
    results.push(`${getItemName(rId)} x1（稀有发现！）`);
  }

  if (getTalentEffect('gather_crit',0) > 0 && Math.random() < getTalentEffect('gather_crit',0)) {
    const bonusId = items[0].id;
    addInventoryItem(bonusId, 2);
    results.push(`${getItemName(bonusId)} x2（暴击采集！）`);
  }

  addLog(`⛏️ 采集获得：${results.join(', ')}${weatherNote}`, 'loot');
  if (combatState) combatState.doubleHarvest = false;
}

// 探索岛屿
export function exploreIsland() {
  if ((G.stats.energy || 0) < 5) {
    addLog('❌ 精力不足！（需要5精力）', 'warning');
    return;
  }
  G.stats.energy -= 5;
  renderStatusBar();

  const exploreMult = 1 + getTalentEffect('exploreEffMult', 0);
  const rareEventBonus = getTalentEffect('rareEventBonus', 0);

  const events = GAME_DATA.events.exploration_events;
  if (!events || events.length === 0) {
    addLog('🔍 探索了一番，没有发现什么特别的。', 'system');
    addExp(Math.floor((5 + Math.floor(Math.random()*5)) * exploreMult));
    return;
  }

  const evt = events[Math.floor(Math.random()*events.length)];

  if (evt.type === 'loot') {
    const loot = [];
    if (evt.rewards) {
      for (const [itemId, range] of Object.entries(evt.rewards)) {
        const count = Math.floor((range[0] + Math.floor(Math.random()*(range[1]-range[0]+1))) * exploreMult);
        addInventoryItem(itemId, count);
        loot.push(`${getItemName(itemId)} x${count}`);
      }
    }
    addLog(`🔍 ${evt.name}：获得 ${loot.join(', ')}`, 'loot');
  } else if (evt.type === 'combat') {
    addLog(`⚔️ ${evt.name}`, 'combat');
    const enemies = [];
    if (evt.enemies) {
      for (const e of evt.enemies) {
        const cdef = getCreatureDef(e.id);
        if (cdef) {
          const cnt = e.count[0] + Math.floor(Math.random()*(e.count[1]-e.count[0]+1));
          for (let i=0; i<cnt; i++) enemies.push({...cdef});
        }
      }
    }
    if (enemies.length > 0) startCombat(enemies);
  } else if (evt.type === 'choice') {
    showChoiceEvent(evt);
  }
}

// 需要从外部注入的函数
let getItemDef, hasItem, hasProfession, getCreatureDef, startCombat, showChoiceEvent;
let addLog, addExp, addInventoryItem, getItemName, renderStatusBar, combatState;

export function injectGatheringDeps(deps) {
  getItemDef = deps.getItemDef;
  hasItem = deps.hasItem;
  hasProfession = deps.hasProfession;
  getCreatureDef = deps.getCreatureDef;
  startCombat = deps.startCombat;
  showChoiceEvent = deps.showChoiceEvent;
  addLog = deps.addLog;
  addExp = deps.addExp;
  addInventoryItem = deps.addInventoryItem;
  getItemName = deps.getItemName;
  renderStatusBar = deps.renderStatusBar;
  combatState = deps.combatState;
}
