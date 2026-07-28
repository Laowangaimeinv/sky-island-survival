"""事件总线 - 解耦游戏逻辑与表现层的核心机制

v2: 新增展示事件（图形层订阅）、网络事件、操作事件
所有游戏事件通过此总线广播，UI层只需订阅感兴趣的事件。
"""

from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


@dataclass
class GameEvent:
    """游戏事件"""
    type: str
    data: Dict[str, Any] = field(default_factory=dict)


class EventBus:
    """全局事件总线"""

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._history: List[GameEvent] = []  # 事件历史（用于网络同步回放）

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        if event_type in self._listeners:
            self._listeners[event_type].remove(callback)

    def emit(self, event_type: str, data: Dict[str, Any] = None):
        event = GameEvent(type=event_type, data=data or {})
        self._history.append(event)
        if event_type in self._listeners:
            for callback in self._listeners[event_type]:
                callback(event)

    def get_history(self, since: int = 0) -> List[GameEvent]:
        """获取事件历史（用于网络同步）"""
        return self._history[since:]

    def history_index(self) -> int:
        return len(self._history)

    def clear(self):
        self._listeners.clear()
        self._history.clear()


# 全局事件总线实例
event_bus = EventBus()


# ============================================================
# 玩家操作（InputAction） - 网络同步的基础
# ============================================================

class ActionType(Enum):
    """所有玩家操作类型 - 统一入口，支持序列化"""
    # 生存
    FISH = "fish"                    # 垂钓
    GATHER = "gather"                # 采集资源
    USE_ITEM = "use_item"            # 使用物品
    REST = "rest"                    # 休息

    # 制作
    CRAFT = "craft"                  # 制作物品
    BUILD = "build"                  # 建造设施

    # 种植
    PLANT = "plant"                  # 种植
    HARVEST = "harvest"              # 收获

    # 探索
    EXPLORE = "explore"              # 探索当前岛屿
    TRAVEL = "travel"                # 前往其他岛屿

    # 战斗
    ATTACK = "attack"                # 攻击
    DEFEND = "defend"                # 防御
    USE_SKILL = "use_skill"          # 使用技能
    FLEE = "flee"                    # 逃跑
    USE_ITEM_COMBAT = "use_item_combat"  # 战斗中使用物品

    # 角色
    EQUIP = "equip"                  # 装备物品
    UNEQUIP = "unequip"             # 卸下装备
    LEARN_PROFESSION = "learn_profession"  # 学习职业

    # 系统
    SAVE = "save"                    # 保存
    ADVANCE_TIME = "advance_time"    # 推进时间


@dataclass
class InputAction:
    """玩家操作 - 可序列化，用于网络同步

    所有玩家操作都封装为 InputAction，引擎接收后分发给对应系统处理。
    多人模式下，客户端只需要发送 InputAction（几十字节），不需要发送整个状态。
    """
    player_id: str
    action_type: ActionType
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "player_id": self.player_id,
            "action": self.action_type.value,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "InputAction":
        return cls(
            player_id=d["player_id"],
            action_type=ActionType(d["action"]),
            params=d.get("params", {}),
        )


# ============================================================
# 事件类型常量
# ============================================================

class EVT:
    """所有游戏事件类型"""

    # === 生存 ===
    PLAYER_DAMAGED = "player_damaged"
    PLAYER_HEALED = "player_healed"
    HUNGER_CHANGED = "hunger_changed"
    PLAYER_DIED = "player_died"
    LEVEL_UP = "level_up"

    # === 探索 ===
    RESOURCE_GATHERED = "resource_gathered"
    ISLAND_EXPLORED = "island_explored"
    EVENT_TRIGGERED = "event_triggered"
    ISLAND_CHANGED = "island_changed"

    # === 制作 ===
    ITEM_CRAFTED = "item_crafted"
    CRAFT_FAILED = "craft_failed"
    BUILDING_BUILT = "building_built"

    # === 战斗 ===
    COMBAT_START = "combat_start"
    COMBAT_ROUND = "combat_round"
    COMBAT_HIT = "combat_hit"
    COMBAT_VICTORY = "combat_victory"
    COMBAT_DEFEAT = "combat_defeat"
    COMBAT_FLEE = "combat_flee"
    LOOT_OBTAINED = "loot_obtained"

    # === 物品 ===
    ITEM_USED = "item_used"
    ITEM_EQUIPPED = "item_equipped"
    ITEM_UNEQUIPPED = "item_unequipped"
    INVENTORY_FULL = "inventory_full"

    # === 天赋 ===
    TALENT_APPLIED = "talent_applied"
    TALENT_DRAWN = "talent_drawn"

    # === 时间 ===
    TIME_CHANGED = "time_changed"
    DAY_CHANGED = "day_changed"
    HOUR_TICK = "hour_tick"
    SEASON_CHANGED = "season_changed"

    # === 职业 ===
    PROFESSION_LEARNED = "profession_learned"
    SKILL_LEARNED = "skill_learned"
    SKILL_USED = "skill_used"

    # === 种植 ===
    CROP_PLANTED = "crop_planted"
    CROP_GROWN = "crop_grown"
    CROP_HARVESTED = "crop_harvested"

    # === 操作处理 ===
    ACTION_SUBMITTED = "action_submitted"    # 操作已提交
    ACTION_PROCESSED = "action_processed"    # 操作已处理完成
    ACTION_REJECTED = "action_rejected"      # 操作被拒绝（非法操作）

    # === 系统 ===
    GAME_SAVE = "game_save"
    GAME_LOAD = "game_load"
    TURN_PASSED = "turn_passed"
    MESSAGE = "message"


# ============================================================
# 展示事件 - 图形/动画层订阅这些事件
# ============================================================

class DisplayEventType(Enum):
    """展示事件类型 - 图形层订阅，逻辑层触发

    这些事件不参与游戏逻辑，纯粹用于视觉/音效展示。
    文字版可以忽略这些事件，图形版订阅后播放对应动画。
    """
    # 动画
    PLAY_ANIM = "display.play_anim"          # 播放动画
    STOP_ANIM = "display.stop_anim"          # 停止动画

    # 图片
    SHOW_IMAGE = "display.show_image"        # 显示图片/插图
    HIDE_IMAGE = "display.hide_image"        # 隐藏图片

    # 音效
    PLAY_SFX = "display.play_sfx"            # 播放音效
    PLAY_BGM = "display.play_bgm"            # 播放背景音乐
    STOP_BGM = "display.stop_bgm"            # 停止背景音乐

    # 文字特效
    SHOW_DIALOG = "display.show_dialog"      # 显示对话框
    SHOW_TOAST = "display.show_toast"        # 显示提示条
    TYPEWRITER = "display.typewriter"        # 打字机效果

    # 场景
    TRANSITION = "display.transition"        # 场景切换动画
    SHAKE = "display.shake"                  # 屏幕震动
    FLASH = "display.flash"                  # 屏幕闪烁


@dataclass
class DisplayEvent:
    """展示事件数据"""
    event_type: DisplayEventType
    params: Dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0  # 持续时间（秒），0表示立即
    blocking: bool = False  # 是否阻塞（等待动画完成再继续）


# 预定义常用展示事件的快捷构造
class Display:
    """展示事件快捷构造器"""

    @staticmethod
    def fishing_anim(duration: float = 2.0) -> DisplayEvent:
        return DisplayEvent(
            event_type=DisplayEventType.PLAY_ANIM,
            params={"anim": "fishing"},
            duration=duration,
            blocking=True,
        )

    @staticmethod
    def combat_anim(attack_type: str = "slash") -> DisplayEvent:
        return DisplayEvent(
            event_type=DisplayEventType.PLAY_ANIM,
            params={"anim": f"combat_{attack_type}"},
            duration=0.8,
            blocking=True,
        )

    @staticmethod
    def island_image(island_id: str) -> DisplayEvent:
        return DisplayEvent(
            event_type=DisplayEventType.SHOW_IMAGE,
            params={"image": f"islands/{island_id}.png"},
        )

    @staticmethod
    def hit_sfx() -> DisplayEvent:
        return DisplayEvent(
            event_type=DisplayEventType.PLAY_SFX,
            params={"sfx": "hit"},
        )

    @staticmethod
    def screen_shake(intensity: float = 0.5) -> DisplayEvent:
        return DisplayEvent(
            event_type=DisplayEventType.SHAKE,
            params={"intensity": intensity},
            duration=0.3,
        )

    @staticmethod
    def transition_fade(duration: float = 1.0) -> DisplayEvent:
        return DisplayEvent(
            event_type=DisplayEventType.TRANSITION,
            params={"style": "fade"},
            duration=duration,
            blocking=True,
        )
