# 空岛求生 - 项目进度文档

> 用于跨对话续接开发，最后更新：2026-07-29

---

## 一、项目定位

**文字选项驱动 + 图形装饰展示 + 多人共享世界**

- 核心是文字MUD/RPG，玩家点击选项执行操作
- 图形只是"插图"：点钓鱼→播放钓鱼动画→显示结果文字
- 不需要玩家操控角色、不需要实时操作
- 多人是"共享文字世界"，玩家在同一座岛上协作/竞争

---

## 二、当前代码结构

```
sky-island-survival/
├── main.py              # 文字UI入口（TextUI类，1000行，未改动）
├── core/
│   ├── entities.py      # [已重构] Player实体、Stats、Equipment、Inventory、Creature
│   ├── events.py        # [已重构] EventBus、InputAction/ActionType、DisplayEvent
│   ├── world.py         # [已更新] GameState，集成Player实体
│   ├── engine.py        # [新增] GameEngine引擎层，接收InputAction分发给系统
│   └── network.py       # [新增] 确定性随机、输入验证、状态快照、消息协议
├── systems/
│   ├── combat.py        # [已更新] 改用装备槽位接口
│   ├── survival.py      # 生存系统（未改动）
│   ├── explore.py       # 探索系统（未改动）
│   ├── craft.py         # 制作系统（未改动）
│   ├── fishing.py       # 垂钓系统（未改动）
│   ├── disaster.py      # 灾厄系统（未改动）
│   ├── weather.py       # 天气系统（未改动）
│   ├── achievements.py  # 成就系统（未改动）
│   ├── talent.py        # 天赋系统（未改动）
│   ├── profession.py    # 职业系统（未改动）
│   └── time_system.py   # 时间系统（未改动）
├── data/                # JSON数据文件（只读，未改动）
│   ├── items.json       # 物品定义
│   ├── recipes.json     # 配方定义
│   ├── creatures.json   # 生物定义
│   ├── islands.json     # 岛屿定义
│   ├── events.json      # 事件定义
│   ├── gameplay.json    # 玩法参数
│   └── talents.json     # 天赋定义
├── DESIGN.md            # [已更新] 架构设计文档
├── DESIGN_GAMEPLAY.md   # 玩法设计文档（未改动）
└── REFACTOR_PLAN.md     # [新增] 架构优化方案
```

---

## 三、已完成的架构改动

### 3.1 Player 实体化（core/entities.py）

将分散的 Stats/Inventory 合并为统一的 Player 实体：

```python
@dataclass
class Player:
    id: str                    # 唯一ID（多人区分）
    name: str
    stats: Stats               # 属性（HP/饥饿/攻击/防御/暴击等）
    inventory: Inventory       # 背包
    equipment: Equipment       # 装备槽位（weapon/head/body/accessory）
    position: IslandPosition   # 当前岛屿位置
    talent_id: str             # 天赋ID引用
    profession_id: str         # 职业ID引用
    profession_level: int
    profession_exp: int

    # 计算属性
    total_atk  # = 基础 + 武器
    total_def  # = 基础 + 装备
    crit_chance
    crit_damage_mult
```

**装备槽位系统**（替代旧的背包扫描方式）：
```python
class Equipment:
    slots: {WEAPON, HEAD, BODY, ACCESSORY}
    equip(item, slot) -> old_item
    unequip(slot) -> item
    get_weapon() / get_armor() / get_helmet()
    get_total_def() / get_total_atk()
    consume_weapon_durability() / consume_armor_durability()
```

**向后兼容**：world.py 中保留了 `state.player_stats` 和 `state.inventory` 引用指向 `player.stats` 和 `player.inventory`，旧代码无需修改。

### 3.2 InputAction 统一操作（core/events.py）

所有玩家操作封装为可序列化的 InputAction：

```python
class ActionType(Enum):
    FISH = "fish"           # 垂钓
    GATHER = "gather"       # 采集
    CRAFT = "craft"         # 制作
    BUILD = "build"         # 建造
    EXPLORE = "explore"     # 探索
    TRAVEL = "travel"       # 旅行
    ATTACK = "attack"       # 攻击
    DEFEND = "defend"       # 防御
    USE_SKILL = "use_skill" # 使用技能
    FLEE = "flee"           # 逃跑
    EQUIP = "equip"         # 装备
    PLANT = "plant"         # 种植
    HARVEST = "harvest"     # 收获
    # ... 共20种

@dataclass
class InputAction:
    player_id: str
    action_type: ActionType
    params: dict
    # 支持 to_dict() / from_dict() 序列化
```

### 3.3 展示事件（core/events.py）

图形层订阅的事件，文字版可忽略：

```python
class DisplayEventType(Enum):
    PLAY_ANIM = "display.play_anim"     # 播放动画
    SHOW_IMAGE = "display.show_image"   # 显示图片
    PLAY_SFX = "display.play_sfx"       # 播放音效
    PLAY_BGM = "display.play_bgm"       # 播放背景音乐
    SHOW_DIALOG = "display.show_dialog" # 显示对话框
    SHAKE = "display.shake"             # 屏幕震动
    TRANSITION = "display.transition"   # 场景切换
    # ...

# 快捷构造
Display.fishing_anim(2.0)   # 垂钓动画
Display.combat_anim("slash") # 斩击动画
Display.island_image("starter_island") # 岛屿图片
Display.hit_sfx()           # 命中音效
Display.screen_shake(0.3)   # 屏幕震动
```

### 3.4 GameEngine 引擎层（core/engine.py）

位于 UI 和系统之间：

```python
class GameEngine:
    def submit_action(action: InputAction) -> List[Event]
    def get_player_status() -> Dict
    def get_display_events() -> List[DisplayEvent]
    def get_save_data() -> Dict
    def load_save_data(data: Dict)
```

### 3.5 网络基础设施（core/network.py）

```python
class DeterministicRandom:  # 可同步的随机数生成器
class InputValidator:       # 输入验证（防作弊）
class StateSnapshot:        # 状态快照（完整/增量）
class GameRoom:             # 游戏房间
class NetworkMessage:       # 网络消息协议
```

### 3.6 HTML版同步（index.html）

HTML版已同步Python架构重构：

```javascript
// 新增类
const EquipSlot = { WEAPON, HEAD, BODY, ACCESSORY, ROD, BAIT, TOOL }
class EquipItem       // 物品包装，含耐久管理
class Equipment       // 装备槽位系统（getWeapon/getArmor/getTotalDef/consumeWeaponDurability）
class Player          // 封装stats+equipment（totalAtk/totalDef/critChance）
function migrateToV2  // 存档迁移（旧格式→Equipment类）

// 已重构函数
calcPlayerAtk()       → 使用Equipment.getWeapon()
calcPlayerDef()       → 使用Equipment.getTotalDef()
playerAttack()        → 使用Equipment.consumeWeaponDurability()
enemyTurn()           → 使用Equipment.consumeArmorDurability() + dodge
useItem()             → 使用Equipment.equip()（所有装备类型）
unequipItem()         → 使用Equipment.unequip()
gatherResource()      → 使用Equipment.getTool()
startFishing()        → 使用Equipment.getRod()/getBait()
saveGame()/loadGame() → 兼容新旧存档格式
renderStatusBar()     → 显示Equipment数据
renderInventory()     → 装备栏显示耐久

// 保持向后兼容
- Legacy字段(G.equippedWeapon等)通过syncToLegacy()保持同步
- 旧存档自动通过migrateToV2()迁移
- 所有函数保留legacy fallback路径
```

---

## 四、未完成 / 下一步

### 4.1 短期（让 GameEngine 真正可用）
- [ ] 将 main.py 中 TextUI 的游戏流程逻辑迁移到 GameEngine
- [ ] 让 TextUI 调用 `engine.submit_action()` 而非直接调用系统
- [ ] 在操作触发时 emit DisplayEvent（文字版忽略，图形版使用）

### 4.2 中期（多人基础）
- [ ] 实现简单的多人房间（基于 network.py 的 GameRoom）
- [ ] 玩家加入/离开房间
- [ ] InputAction 广播给房间内所有玩家
- [ ] 状态快照同步

### 4.3 长期（图形化）
- [ ] 选择图形引擎（推荐 Godot 4.x，适合2D+文字游戏）
- [ ] 实现 AnimUI 层，订阅 DisplayEvent 播放动画
- [ ] 岛屿场景图、角色立绘、战斗动画
- [ ] 音效和BGM系统

### 4.4 系统层待优化
- [ ] 所有系统增加 `process_action(InputAction)` 统一接口
- [ ] 用 DeterministicRandom 替代 random 模块调用
- [ ] CombatSystem 解耦（当前内部 new SurvivalSystem）
- [ ] 种植系统完善（plant_crop 方法需确认）

---

## 五、关键设计决策记录

| 编号 | 决策 | 原因 |
|------|------|------|
| ADR-001 | Player实体化 | 多人需要唯一ID和完整状态 |
| ADR-002 | 装备槽位替代背包扫描 | 旧方式是hack，新方式清晰且支持装备对比 |
| ADR-003 | InputAction统一操作 | 网络同步只需发送操作（几十字节），不需同步整个状态 |
| ADR-004 | DisplayEvent分离展示 | 图形是装饰，不参与逻辑；文字版可忽略 |
| ADR-005 | 确定性随机 | 多人同步需要相同种子产生相同结果 |
| ADR-006 | 向后兼容 | main.py TextUI 未改动，通过player_stats/inventory引用保持兼容 |

---

## 六、验证状态

- ✅ Player 实体创建和序列化
- ✅ Equipment 装备槽位
- ✅ InputAction / ActionType
- ✅ DisplayEvent / Display
- ✅ DeterministicRandom 确定性
- ✅ GameState 向后兼容（player_stats/player 引用）
- ✅ 所有系统正常导入
- ✅ GameEngine 创建和查询
- ✅ 游戏正常启动运行

---

## 七、续接开发时的提示

当你在新对话中继续这个项目时，可以这样开头：

> 我在开发一个叫"空岛求生"的文字生存游戏，定位是"文字选项驱动+图形装饰展示+多人共享世界"。
> 已经完成了架构重构：Player实体化、InputAction统一操作、DisplayEvent展示事件分离、GameEngine引擎层、网络基础设施。
> 请先阅读 `游戏/sky-island-survival/` 目录下的 REFACTOR_PLAN.md 和本进度文档，然后继续 [具体任务]。

或者直接把本文档内容发给我即可。
