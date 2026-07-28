# 空岛求生 - 架构优化方案 v2

> 定位：文字选项驱动 + 图形装饰展示 + 多人共享世界

## 核心设计理念

```
玩家点击选项 → 引擎执行逻辑 → 播放动画/显示图片 → 返回文字结果
```

图形是"插图"，不是"操作界面"。类似：
- 互动小说（Lifeline、Reigns）
- 文字MUD的图形化版本
- 放置类游戏的动画展示层

## 当前架构问题

### 1. 玩家不是实体（多人必须修复）
- Stats 是裸数据类，没有 Player ID
- 装备是"背包里扫描 type"的 hack
- 无法区分多个玩家

### 2. 操作没有标准化（网络同步必须修复）
- 每个操作是直接调用系统方法，没有统一的操作对象
- 网络同步需要发送"操作"而非"整个状态"
- 需要 InputAction 统一所有玩家操作

### 3. 没有图形展示层接口（图形化必须修复）
- 动画/图片的触发散落在各处
- 需要统一的"展示事件"：播放动画、显示图片、播放音效

### 4. TextUI 职责过重（代码质量）
- main.py 1000+ 行，混合显示和逻辑
- 战斗流程在 UI 层控制

## 优化方案

### 新架构

```
┌─────────────────────────────────────────────────────┐
│              展示层 (Presentation)                    │
│  TextUI ←→ AnimUI(未来) ←→ WebUI(未来)              │
│  职责：文字显示 / 动画播放 / 图片展示 / 音效播放      │
│  订阅 EventBus，只做展示，不做逻辑判断                │
├─────────────────────────────────────────────────────┤
│              引擎层 (Engine)                          │
│  GameEngine: 接收 InputAction → 分发给系统 → 收集事件  │
│  世界状态、玩家状态的唯一管理者                        │
├─────────────────────────────────────────────────────┤
│              系统层 (Systems)                         │
│  CombatSystem / FishingSystem / ...                  │
│  每个系统: process(action) → List[Event]              │
├─────────────────────────────────────────────────────┤
│              核心层 (Core)                            │
│  Player / Creature / Island / EventBus               │
│  DeterministicRandom / NetworkProtocol               │
├─────────────────────────────────────────────────────┤
│              数据层 (Data)                            │
│  items.json / recipes.json / ...（只读）              │
└─────────────────────────────────────────────────────┘
```

### 关键改动

#### 1. Player 实体化
```python
@dataclass
class Player:
    id: str                    # 唯一ID（多人区分）
    name: str                  # 显示名
    stats: Stats               # 属性
    inventory: Inventory       # 背包
    equipment: Equipment       # 装备槽位（从背包分离）
    position: IslandPosition   # 当前位置
    profession: Optional[Profession]
    talent: Optional[Talent]
```

#### 2. InputAction 统一操作
```python
@dataclass
class InputAction:
    player_id: str
    action_type: ActionType    # 枚举：FISH / GATHER / CRAFT / ATTACK / ...
    params: dict               # 操作参数
    timestamp: float           # 时间戳
```

#### 3. 展示事件
```python
# 图形层订阅这些事件来播放动画
class DisplayEvent:
    PLAY_ANIM = "display.play_anim"      # {"anim": "fishing", "duration": 2.0}
    SHOW_IMAGE = "display.show_image"    # {"image": "island_sunset.png"}
    PLAY_SFX = "display.play_sfx"        # {"sfx": "sword_hit.wav"}
    SHOW_TEXT = "display.show_text"      # {"text": "...", "style": "dialog"}
```

#### 4. GameEngine 层
```python
class GameEngine:
    def __init__(self):
        self.players = {}
        self.world = World()
        self.systems = []
    
    def submit_action(self, action: InputAction) -> List[Event]:
        """处理玩家操作，返回产生的事件列表"""
        ...
```

## 实施顺序

1. ✅ 方案文档
2. 🔄 Player 实体化（合并 Stats + Inventory + Equipment）
3. ⬜ InputAction + ActionType 枚举
4. ⬜ DisplayEvent 展示事件
5. ⬜ GameEngine 引擎层
6. ⬜ 各系统适配新接口
7. ⬜ TextUI 适配为展示层
8. ⬜ 验证兼容性
