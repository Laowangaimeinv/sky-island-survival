"""时间系统 - 详细的游戏时间管理

时间单位：
- 1游戏小时 = 1回合
- 1天 = 24小时（24回合）
- 1月 = 30天
- 1年 = 12月

时段划分：
- 凌晨 (0-4): 夜间，危险
- 清晨 (5-7): 资源刷新
- 上午 (8-11): 正常活动
- 正午 (12-13): 休息加成
- 下午 (14-17): 正常活动
- 傍晚 (18-19): 资源刷新
- 夜晚 (20-23): 夜间，危险
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
import random

from core.events import event_bus, EVT


# 时段定义
TIME_PERIODS = {
    "dawn":     {"name": "🌅 凌晨", "hours": (0, 4),   "effects": {"encounter_mult": 1.5, "gather_mult": 0.5, "danger": True}},
    "morning":  {"name": "🌄 清晨", "hours": (5, 7),   "effects": {"encounter_mult": 0.8, "gather_mult": 1.3, "refresh": True}},
    "forenoon": {"name": "☀️ 上午", "hours": (8, 11),  "effects": {"encounter_mult": 1.0, "gather_mult": 1.0}},
    "noon":     {"name": "🔆 正午", "hours": (12, 13), "effects": {"encounter_mult": 0.9, "gather_mult": 1.0, "rest_bonus": True}},
    "afternoon":{"name": "🌤️ 下午", "hours": (14, 17), "effects": {"encounter_mult": 1.0, "gather_mult": 1.0}},
    "dusk":     {"name": "🌅 傍晚", "hours": (18, 19), "effects": {"encounter_mult": 1.2, "gather_mult": 1.2, "refresh": True}},
    "night":    {"name": "🌙 夜晚", "hours": (20, 23), "effects": {"encounter_mult": 1.8, "gather_mult": 0.3, "danger": True}},
}

# 季节定义
SEASONS = {
    "spring": {"name": "🌸 春", "effects": {"growth_mult": 1.5, "herb_mult": 1.3, "gather_mult": 1.1}},
    "summer": {"name": "☀️ 夏", "effects": {"growth_mult": 1.0, "hunger_mult": 1.2, "encounter_mult": 1.1}},
    "autumn": {"name": "🍂 秋", "effects": {"growth_mult": 0.8, "food_mult": 1.5, "gather_mult": 1.2}},
    "winter": {"name": "❄️ 冬", "effects": {"growth_mult": 0.3, "hunger_mult": 1.5, "cold_damage": 2}},
}

# 月份到季节映射
MONTH_SEASON = {
    1: "spring", 2: "spring", 3: "spring",
    4: "summer", 5: "summer", 6: "summer",
    7: "autumn", 8: "autumn", 9: "autumn",
    10: "winter", 11: "winter", 12: "winter",
}


@dataclass
class GameTime:
    """游戏时间"""
    hour: int = 6       # 0-23
    day: int = 1        # 1-30
    month: int = 1      # 1-12
    year: int = 1       # 1+
    total_turns: int = 0  # 总回合数

    @property
    def period(self) -> str:
        """当前时段"""
        for pid, p in TIME_PERIODS.items():
            if p["hours"][0] <= self.hour <= p["hours"][1]:
                return pid
        return "dawn"

    @property
    def period_info(self) -> Dict:
        return TIME_PERIODS[self.period]

    @property
    def season(self) -> str:
        return MONTH_SEASON.get(self.month, "spring")

    @property
    def season_info(self) -> Dict:
        return SEASONS[self.season]

    @property
    def time_string(self) -> str:
        """格式化时间字符串"""
        return f"{self.year}年{self.month}月{self.day}日 {self.hour:02d}:00"

    @property
    def is_night(self) -> bool:
        return self.period in ("dawn", "night")

    @property
    def is_dangerous(self) -> bool:
        return TIME_PERIODS[self.period]["effects"].get("danger", False)

    @property
    def is_refresh(self) -> bool:
        return TIME_PERIODS[self.period]["effects"].get("refresh", False)


class TimeSystem:
    """时间系统管理器"""

    def __init__(self):
        self.time = GameTime()
        self.fishing_progress: Optional[Dict] = None  # 垂钓进度
        self.farming_plots: list = []  # 农田列表
        self.active_timers: list = []  # 活跃的定时器

    def advance_minutes(self, minutes: int = 10):
        """推进时间（分钟级）"""
        self.time.minute = getattr(self.time, 'minute', 0) + minutes
        while self.time.minute >= 60:
            self.time.minute -= 60
            self.advance_hour(1)

    def advance_hour(self, hours: int = 1):
        """推进时间"""
        for _ in range(hours):
            self.time.hour += 1
            self.time.total_turns += 1

            if self.time.hour >= 24:
                self.time.hour = 0
                self.time.day += 1

                # 日出事件
                self._on_sunrise()

            if self.time.day > 30:
                self.time.day = 1
                self.time.month += 1

                # 月变更事件
                self._on_month_change()

            if self.time.month > 12:
                self.time.month = 1
                self.time.year += 1

            # 每小时更新
            self._on_hour_tick()

        # 时段变化事件
        period_info = self.time.period_info
        event_bus.emit(EVT.TIME_CHANGED, {
            "hour": self.time.hour,
            "day": self.time.day,
            "month": self.time.month,
            "year": self.time.year,
            "period": period_info["name"],
            "season": self.time.season_info["name"]
        })

    def _on_hour_tick(self):
        """每小时回调"""
        # 更新垂钓进度
        if self.fishing_progress:
            self.fishing_progress["remaining"] -= 1
            if self.fishing_progress["remaining"] <= 0:
                self._complete_fishing()

        # 更新农田
        for plot in self.farming_plots:
            if plot["stage"] < plot["max_stage"]:
                plot["timer"] -= 1
                if plot["timer"] <= 0:
                    plot["stage"] += 1
                    if plot["stage"] < plot["max_stage"]:
                        plot["timer"] = plot["stage_time"]
                    event_bus.emit(EVT.MESSAGE, {
                        "text": f"🌱 {plot['name']}生长到了第{plot['stage']}阶段"
                    })

        # 更新定时器
        expired = []
        for timer in self.active_timers:
            timer["remaining"] -= 1
            if timer["remaining"] <= 0:
                expired.append(timer)
                if timer.get("callback"):
                    timer["callback"]()
        for t in expired:
            self.active_timers.remove(t)

        # 季节效果
        season_effects = self.time.season_info["effects"]
        if "cold_damage" in season_effects:
            # 冬季每小时寒冷伤害
            if random.random() < 0.1:  # 10%概率
                event_bus.emit(EVT.MESSAGE, {"text": "❄️ 寒风刺骨，你感到身体有些僵硬..."})

    def _on_sunrise(self):
        """日出事件"""
        event_bus.emit(EVT.MESSAGE, {
            "text": f"🌅 第{self.time.day}天来临了。"
        })

        # 每日资源刷新
        event_bus.emit(EVT.DAY_CHANGED, {
            "day": self.time.day,
            "month": self.time.month,
            "season": self.time.season
        })

    def _on_month_change(self):
        """月变更事件"""
        season_name = self.time.season_info["name"]
        event_bus.emit(EVT.MESSAGE, {
            "text": f"📅 新的一月到来，当前季节：{season_name}"
        })

    def start_fishing(self, rod_durability: int = -1, bait_bonus: int = 0) -> Dict:
        """开始垂钓（需要时间）"""
        base_time = 2  # 基础2小时
        # 钓饵减少时间
        time_reduction = min(bait_bonus, 1)
        fishing_time = max(1, base_time - time_reduction)

        self.fishing_progress = {
            "total_time": fishing_time,
            "remaining": fishing_time,
            "rod_durability": rod_durability,
            "bait_bonus": bait_bonus,
            "started_hour": self.time.hour,
        }

        event_bus.emit(EVT.MESSAGE, {
            "text": f"🎣 甩出钓竿...预计需要{fishing_time}小时"
        })

        return self.fishing_progress

    def _complete_fishing(self):
        """垂钓完成"""
        event_bus.emit(EVT.MESSAGE, {
            "text": "🎣 鱼竿有动静了！"
        })
        self.fishing_progress = None

    def is_fishing_complete(self) -> bool:
        """检查垂钓是否完成"""
        return self.fishing_progress is None or self.fishing_progress["remaining"] <= 0

    def get_fishing_progress(self) -> Optional[Dict]:
        """获取垂钓进度"""
        return self.fishing_progress

    def add_farming_plot(self, crop_id: str, crop_name: str, growth_time: int, stages: int):
        """添加农田"""
        stage_time = max(1, growth_time // stages)
        plot = {
            "crop_id": crop_id,
            "name": crop_name,
            "stage": 0,
            "max_stage": stages,
            "stage_time": stage_time,
            "timer": stage_time,
            "total_time": growth_time,
        }
        self.farming_plots.append(plot)
        event_bus.emit(EVT.MESSAGE, {
            "text": f"🌱 种下了{crop_name}，预计{growth_time}小时后成熟"
        })
        return plot

    def harvest_crop(self, plot_index: int) -> Optional[Dict]:
        """收获作物"""
        if plot_index < 0 or plot_index >= len(self.farming_plots):
            return None

        plot = self.farming_plots[plot_index]
        if plot["stage"] < plot["max_stage"]:
            event_bus.emit(EVT.MESSAGE, {
                "text": f"{plot['name']}还未成熟（{plot['stage']}/{plot['max_stage']}）"
            })
            return None

        # 计算产量（季节加成）
        season_effects = self.time.season_info["effects"]
        growth_mult = season_effects.get("growth_mult", 1.0)
        base_yield = random.randint(2, 5)
        yield_amount = max(1, int(base_yield * growth_mult))

        result = {
            "crop_id": plot["crop_id"],
            "name": plot["name"],
            "yield": yield_amount,
        }

        self.farming_plots.pop(plot_index)
        event_bus.emit(EVT.MESSAGE, {
            "text": f"🌾 收获了{plot['name']} ×{yield_amount}"
        })

        return result

    def get_time_info(self) -> Dict:
        minute = getattr(self.time, 'minute', 0)
        """获取完整时间信息"""
        period = self.time.period_info
        season = self.time.season_info

        result = {
            "time_string": self.time.time_string,
            "hour": self.time.hour,
            "day": self.time.day,
            "month": self.time.month,
            "year": self.time.year,
            "period_name": period["name"],
            "period_effects": period["effects"],
            "season_name": season["name"],
            "season_effects": season["effects"],
            "is_night": self.time.is_night,
            "is_dangerous": self.time.is_dangerous,
            "farming_count": len(self.farming_plots),
            "is_fishing": self.fishing_progress is not None,
        }

        if self.fishing_progress:
            result["fishing_remaining"] = self.fishing_progress["remaining"]
            result["fishing_total"] = self.fishing_progress["total_time"]

        return result

    def save_state(self) -> Dict:
        """保存时间状态"""
        return {
            "hour": self.time.hour,
            "day": self.time.day,
            "month": self.time.month,
            "year": self.time.year,
            "total_turns": self.time.total_turns,
            "farming_plots": self.farming_plots,
        }

    def load_state(self, data: Dict):
        """加载时间状态"""
        self.time.hour = data.get("hour", 6)
        self.time.day = data.get("day", 1)
        self.time.month = data.get("month", 1)
        self.time.year = data.get("year", 1)
        self.time.total_turns = data.get("total_turns", 0)
        self.farming_plots = data.get("farming_plots", [])
