"""网络模块 - 多人游戏基础设施

提供多人游戏所需的网络协议框架：
- 消息类型定义
- 状态快照与同步
- 输入验证
- 确定性随机数

当前为框架代码，具体网络实现（WebSocket/UDP）在接入图形版时补充。
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

from core.events import InputAction, ActionType


# ============================================================
# 网络消息类型
# ============================================================

class MsgType(Enum):
    """网络消息类型"""
    # 连接管理
    CONNECT = "connect"              # 客户端连接
    DISCONNECT = "disconnect"        # 客户端断开
    JOIN = "join"                    # 加入游戏
    LEAVE = "leave"                  # 离开游戏

    # 状态同步
    STATE_SNAPSHOT = "state_snapshot"  # 完整状态快照
    STATE_DELTA = "state_delta"        # 增量状态更新

    # 操作同步
    ACTION = "action"                # 玩家操作
    ACTION_BATCH = "action_batch"    # 批量操作

    # 游戏流程
    GAME_START = "game_start"        # 游戏开始
    GAME_PAUSE = "game_pause"        # 游戏暂停
    GAME_RESUME = "game_resume"      # 游戏恢复

    # 聊天
    CHAT = "chat"                    # 聊天消息


@dataclass
class NetworkMessage:
    """网络消息 - 所有网络通信的统一格式"""
    msg_type: MsgType
    sender_id: str = ""
    timestamp: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> Dict:
        return {
            "type": self.msg_type.value,
            "sender": self.sender_id,
            "ts": self.timestamp,
            "data": self.data,
        }

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: Dict) -> "NetworkMessage":
        return cls(
            msg_type=MsgType(d["type"]),
            sender_id=d.get("sender", ""),
            timestamp=d.get("ts", 0),
            data=d.get("data", {}),
        )


# ============================================================
# 确定性随机数生成器
# ============================================================

class DeterministicRandom:
    """确定性随机数生成器

    多人游戏同步的关键：所有客户端使用相同种子，
    产生完全相同的随机数序列，确保状态一致。

    使用 Xorshift32 算法，周期 2^32-1。
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.state = seed & 0xFFFFFFFF

    def next_int(self) -> int:
        """返回 0 到 2^32-1 之间的整数"""
        self.state ^= (self.state << 13) & 0xFFFFFFFF
        self.state ^= (self.state >> 17)
        self.state ^= (self.state << 5) & 0xFFFFFFFF
        return self.state

    def next_float(self) -> float:
        """返回 0.0 到 1.0 之间的浮点数"""
        return self.next_int() / 0xFFFFFFFF

    def range_int(self, min_val: int, max_val: int) -> int:
        """返回 min_val 到 max_val 之间的整数（含两端）"""
        if min_val > max_val:
            min_val, max_val = max_val, min_val
        return min_val + self.next_int() % (max_val - min_val + 1)

    def range_float(self, min_val: float, max_val: float) -> float:
        """返回 min_val 到 max_val 之间的浮点数"""
        return min_val + self.next_float() * (max_val - min_val)

    def choice(self, items: list):
        """从列表中随机选择一个元素"""
        if not items:
            return None
        idx = self.next_int() % len(items)
        return items[idx]

    def chance(self, probability: float) -> bool:
        """以指定概率返回 True"""
        return self.next_float() < probability

    def get_state(self) -> Dict:
        return {"seed": self.seed, "state": self.state}

    def set_state(self, state: Dict):
        self.seed = state["seed"]
        self.state = state["state"]


# ============================================================
# 输入验证器
# ============================================================

class InputValidator:
    """输入验证器 - 防止作弊

    在服务器端验证客户端发送的 InputAction 是否合法。
    """

    def __init__(self):
        self.rules: Dict[ActionType, callable] = {}

    def register_rule(self, action_type: ActionType, rule: callable):
        """注册验证规则"""
        self.rules[action_type] = rule

    def validate(self, action: InputAction, game_state) -> tuple:
        """验证操作是否合法

        Returns:
            (is_valid: bool, reason: str)
        """
        # 基础检查
        if not action.player_id:
            return False, "缺少玩家ID"

        if action.action_type not in ActionType:
            return False, f"无效操作类型: {action.action_type}"

        # 自定义规则检查
        rule = self.rules.get(action.action_type)
        if rule:
            return rule(action, game_state)

        return True, ""

    @staticmethod
    def validate_fish(action: InputAction, game_state) -> tuple:
        """验证垂钓操作"""
        # 检查是否已在垂钓
        if game_state.time_system.fishing_progress:
            fishing = game_state.time_system.get_fishing_progress()
            if fishing and fishing["remaining"] > 0:
                return False, "正在垂钓中"
        # 检查饱食度
        if game_state.player_stats.hunger <= 0:
            return False, "饥饿值为0，无法垂钓"
        return True, ""

    @staticmethod
    def validate_combat_action(action: InputAction, game_state) -> tuple:
        """验证战斗操作"""
        # 检查是否在战斗中
        # （这里需要从 engine 获取战斗状态）
        return True, ""


# ============================================================
# 状态快照
# ============================================================

class StateSnapshot:
    """世界状态快照 - 用于网络同步

    包含所有需要同步的状态数据，支持：
    - 完整快照（新玩家加入时）
    - 增量快照（只包含变化部分）
    """

    @staticmethod
    def full_snapshot(engine) -> Dict:
        """生成完整状态快照"""
        return {
            "type": "full",
            "timestamp": time.time(),
            "world": {
                "turn": engine.world.turn,
                "day": engine.world.day,
                "islands": {
                    iid: {
                        "explored": isl.explored,
                        "guardian_defeated": isl.guardian_defeated,
                    }
                    for iid, isl in engine.world.islands.items()
                },
            },
            "players": {
                pid: player.to_dict()
                for pid, player in engine.players.items()
            },
        }

    @staticmethod
    def delta_snapshot(engine, last_snapshot_ts: float) -> Dict:
        """生成增量快照（只包含变化）"""
        # 实际实现需要追踪脏数据
        # 这里返回完整快照作为简化版
        return StateSnapshot.full_snapshot(engine)


# ============================================================
# 游戏房间
# ============================================================

@dataclass
class GameRoom:
    """游戏房间 - 多人游戏的基本单位"""
    room_id: str
    host_id: str
    players: List[str] = field(default_factory=list)
    max_players: int = 4
    state: str = "waiting"  # waiting / playing / paused
    created_at: float = field(default_factory=time.time)

    def is_full(self) -> bool:
        return len(self.players) >= self.max_players

    def add_player(self, player_id: str) -> bool:
        if self.is_full():
            return False
        if player_id not in self.players:
            self.players.append(player_id)
        return True

    def remove_player(self, player_id: str):
        if player_id in self.players:
            self.players.remove(player_id)

    def to_dict(self) -> Dict:
        return {
            "room_id": self.room_id,
            "host_id": self.host_id,
            "players": self.players,
            "max_players": self.max_players,
            "state": self.state,
        }
