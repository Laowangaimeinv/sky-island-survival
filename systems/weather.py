"""天气与环境系统"""

import random
from typing import Dict, Optional
from pathlib import Path
import json

from core.events import event_bus, EVT


DATA_DIR = Path(__file__).parent.parent / "data"


def load_gameplay():
    with open(DATA_DIR / "gameplay.json", "r", encoding="utf-8") as f:
        return json.load(f)


class WeatherSystem:
    """天气系统"""

    def __init__(self, state):
        self.state = state
        self.data = load_gameplay()
        self.weather_types = self.data["weather_types"]
        self.current_weather = "sunny"
        self.weather_duration = 0
        self.day_night = "day"  # day/dusk/night
        self.turn_of_day = 0

    def update(self):
        """每回合更新天气"""
        self.turn_of_day = self.state.turn % 10

        # 昼夜循环（每10回合为一天）
        if self.turn_of_day < 6:
            self.day_night = "day"
        elif self.turn_of_day < 8:
            self.day_night = "dusk"
        else:
            self.day_night = "night"

        # 天气更新
        self.weather_duration -= 1
        if self.weather_duration <= 0:
            self._change_weather()

    def _change_weather(self):
        """切换天气"""
        weights = {
            "sunny": 40,
            "rainy": 25,
            "foggy": 15,
            "stormy": 10,
            "cold": 8,
            "void_storm": 2
        }

        # 虚空风暴只在特定天数后出现
        if self.state.day < 30:
            weights["void_storm"] = 0

        # 高级岛屿更容易遇到恶劣天气
        island_level = self.state.current_island.level
        if island_level >= 3:
            weights["stormy"] += 5
            weights["cold"] += 5
            weights["void_storm"] += 1

        types = list(weights.keys())
        w = list(weights.values())
        self.current_weather = random.choices(types, weights=w, k=1)[0]

        weather = self.weather_types[self.current_weather]
        duration_range = weather["duration"]
        self.weather_duration = random.randint(duration_range[0], duration_range[1])

        # 显示天气变化
        event_bus.emit(EVT.MESSAGE, {
            "text": f"  天气变化：{weather['name']}"
        })

        # 特殊天气效果
        if self.current_weather == "void_storm":
            event_bus.emit(EVT.MESSAGE, {
                "text": "  ⚠️ 虚空风暴来袭！岛屿正在缩小！快使用空岛水晶维持！"
            })

    def get_gather_modifier(self) -> float:
        """获取采集效率修正"""
        weather = self.weather_types[self.current_weather]
        effects = weather.get("effects", {})

        base = effects.get("gather_bonus", 0)
        mult = effects.get("gather_mult", 1.0)

        # 夜间惩罚
        if self.day_night == "night":
            # 有夜视天赋则免疫
            talent = self.state.talent_system.get_passive_effects()
            if not talent.get("night_penalty_immune"):
                mult *= 0.5

        return (1.0 + base) * mult

    def get_encounter_modifier(self) -> float:
        """获取遭遇率修正"""
        weather = self.weather_types[self.current_weather]
        effects = weather.get("effects", {})
        bonus = effects.get("encounter_bonus", 0)

        # 夜间遭遇率更高
        if self.day_night == "night":
            bonus += 0.20

        return 1.0 + bonus

    def get_hunger_modifier(self) -> float:
        """获取饥饿消耗修正"""
        weather = self.weather_types[self.current_weather]
        effects = weather.get("effects", {})
        return effects.get("hunger_decay_mult", 1.0)

    def get_weather_info(self) -> Dict:
        """获取当前天气信息"""
        weather = self.weather_types[self.current_weather]
        time_names = {"day": "☀️ 白天", "dusk": "🌅 黄昏", "night": "🌙 夜晚"}
        return {
            "weather": weather["name"],
            "time": time_names[self.day_night],
            "duration": self.weather_duration,
            "gather_mod": self.get_gather_modifier(),
            "encounter_mod": self.get_encounter_modifier()
        }
