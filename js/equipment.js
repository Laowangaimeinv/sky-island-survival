// equipment.js - 装备系统模块
import { G } from './state.js';

export const EquipSlot = {
  WEAPON:'weapon', HEAD:'head', BODY:'body', ACCESSORY:'accessory',
  ROD:'rod', BAIT:'bait', TOOL:'tool'
};

export class EquipItem {
  constructor(itemId, itemData, grade, durability) {
    this.itemId = itemId;
    this.itemData = itemData || {};
    this.grade = grade || (itemData && itemData.grade) || 'F';
    this.durability = durability != null ? durability : (itemData && itemData.durability) || -1;
    this.maxDurability = (itemData && itemData.durability) || -1;
  }
  get name() { return this.itemData.name || this.itemId; }
  get isBroken() { return this.durability === 0; }
  get atk() { return this.itemData.atk || 0; }
  get def() { return this.itemData.def || 0; }
  consumeDurability(amount) {
    if (this.durability < 0) return false;
    this.durability = Math.max(0, this.durability - (amount || 1));
    return this.durability <= 0;
  }
  toDict() {
    return { itemId: this.itemId, grade: this.grade, durability: this.durability };
  }
  static fromDict(d, getItemDef) {
    const def = getItemDef(d.itemId);
    if (!def) return null;
    return new EquipItem(d.itemId, def, d.grade, d.durability);
  }
}

export class Equipment {
  constructor() {
    this.slots = {
      [EquipSlot.WEAPON]: null, [EquipSlot.HEAD]: null,
      [EquipSlot.BODY]: null, [EquipSlot.ACCESSORY]: null,
      [EquipSlot.ROD]: null, [EquipSlot.BAIT]: null, [EquipSlot.TOOL]: null,
    };
  }
  getWeapon() { return this.slots[EquipSlot.WEAPON]; }
  getArmor() { return this.slots[EquipSlot.BODY]; }
  getHelmet() { return this.slots[EquipSlot.HEAD]; }
  getAccessory() { return this.slots[EquipSlot.ACCESSORY]; }
  getRod() { return this.slots[EquipSlot.ROD]; }
  getBait() { return this.slots[EquipSlot.BAIT]; }
  getTool() { return this.slots[EquipSlot.TOOL]; }

  equip(item, slot) {
    const old = this.slots[slot];
    this.slots[slot] = item;
    return old;
  }
  unequip(slot) {
    const item = this.slots[slot];
    this.slots[slot] = null;
    return item;
  }

  getTotalDef() {
    let total = 0;
    for (const item of Object.values(this.slots)) {
      if (item && !item.isBroken) total += item.def;
    }
    return total;
  }
  getTotalAtk() {
    const weapon = this.getWeapon();
    return (weapon && !weapon.isBroken) ? weapon.atk : 0;
  }
  consumeWeaponDurability(amount) {
    const weapon = this.getWeapon();
    if (!weapon) return false;
    return weapon.consumeDurability(amount || 1);
  }
  consumeArmorDurability(amount) {
    const armor = this.getArmor();
    if (!armor) return false;
    return armor.consumeDurability(amount || 1);
  }

  toDict() {
    const d = {};
    for (const [slot, item] of Object.entries(this.slots)) {
      d[slot] = item ? item.toDict() : null;
    }
    return d;
  }
  static fromDict(d, getItemDef) {
    const eq = new Equipment();
    if (!d) return eq;
    for (const [slot, itemData] of Object.entries(d)) {
      if (itemData && itemData.itemId) {
        eq.slots[slot] = EquipItem.fromDict(itemData, getItemDef);
      }
    }
    return eq;
  }

  syncToLegacy() {
    if (!G) return;
    G.equippedWeapon = this.getWeapon() ? this.getWeapon().itemId : null;
    G.equippedArmor = this.getArmor() ? this.getArmor().itemId : null;
    G.equippedHead = this.getHelmet() ? this.getHelmet().itemId : null;
    G.equippedRod = this.getRod() ? this.getRod().itemId : null;
    G.equippedBait = this.getBait() ? this.getBait().itemId : null;
    G.equippedTool = this.getTool() ? this.getTool().itemId : null;
  }

  syncFromLegacy(getItemDef) {
    if (!G) return;
    const tryEquip = (itemId, slot) => {
      if (itemId) {
        const def = getItemDef(itemId);
        if (def) {
          const dur = G.toolDurability ? (G.toolDurability[itemId] != null ? G.toolDurability[itemId] : def.durability) : def.durability;
          this.slots[slot] = new EquipItem(itemId, def, def.grade, dur);
        }
      }
    };
    tryEquip(G.equippedWeapon, EquipSlot.WEAPON);
    tryEquip(G.equippedArmor, EquipSlot.BODY);
    tryEquip(G.equippedHead, EquipSlot.HEAD);
    tryEquip(G.equippedRod, EquipSlot.ROD);
    tryEquip(G.equippedBait, EquipSlot.BAIT);
    tryEquip(G.equippedTool, EquipSlot.TOOL);
  }
}

export class Player {
  constructor(stats, equipment) {
    this.stats = stats || {};
    this.equipment = equipment || new Equipment();
  }
  get totalAtk() { return (this.stats.atk || 5) + this.equipment.getTotalAtk(); }
  get totalDef() { return (this.stats.defense || 0) + this.equipment.getTotalDef(); }
  toDict() {
    return { stats: { ...this.stats }, equipment: this.equipment.toDict() };
  }
  static fromDict(d, getItemDef) {
    const stats = d.stats || {};
    const equipment = Equipment.fromDict(d.equipment, getItemDef);
    return new Player(stats, equipment);
  }
}

// 自动卸下损坏装备
export function unequipBrokenItems() {
  if (!G?.player) return;
  const eq = G.player.equipment;
  const slots = [
    {slot: EquipSlot.WEAPON, name: 'weapon'},
    {slot: EquipSlot.BODY, name: 'armor'},
    {slot: EquipSlot.HEAD, name: 'head'},
    {slot: EquipSlot.TOOL, name: 'tool'},
    {slot: EquipSlot.ROD, name: 'rod'},
  ];
  for (const s of slots) {
    const item = eq.slots[s.slot];
    if (item && item.isBroken) {
      eq.unequip(s.slot);
      eq.syncToLegacy();
      if (G.addLog) G.addLog(`💔 ${item.name}已损坏，自动卸下`, 'warning');
    }
  }
}

// 存档迁移
export function migrateToV2(data, getItemDef) {
  if (!data) return data;
  if (data.equipment && data.equipment.weapon && data.equipment.weapon.itemId) return data;
  const tryMigrate = (itemId) => {
    if (!itemId) return null;
    const def = getItemDef(itemId);
    if (!def) return null;
    const dur = data.toolDurability ? (data.toolDurability[itemId] != null ? data.toolDurability[itemId] : def.durability) : def.durability;
    return { itemId, grade: def.grade || 'F', durability: dur != null ? dur : (def.durability || -1) };
  };
  data.equipment = {
    weapon: tryMigrate(data.equippedWeapon),
    body: tryMigrate(data.equippedArmor),
    head: tryMigrate(data.equippedHead),
    accessory: null,
    rod: tryMigrate(data.equippedRod),
    bait: tryMigrate(data.equippedBait),
    tool: tryMigrate(data.equippedTool),
  };
  return data;
}
