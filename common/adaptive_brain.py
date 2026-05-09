import json
import os
import time


ADAPTIVE_STATE_PATH = "cfg/adaptive_state.json"

DEFAULTS = {
    "safe_range_multiplier": 1.0,
    "strafe_blend": 0.35,
    "strafe_interval": 1.6,
    "attack_cooldown": 0.16,
}

LIMITS = {
    "safe_range_multiplier": (0.85, 1.25),
    "strafe_blend": (0.15, 0.65),
    "strafe_interval": (1.0, 2.3),
    "attack_cooldown": (0.12, 0.22),
}

STEP = {
    "safe_range_multiplier": 0.03,
    "strafe_blend": 0.03,
    "strafe_interval": 0.08,
    "attack_cooldown": 0.005,
}


class AdaptiveBrain:
    def __init__(self, enabled=True, state_path=ADAPTIVE_STATE_PATH, window_size=20):
        self.enabled = enabled
        self.state_path = state_path
        self.window_size = max(5, int(window_size))
        self.state = self._load()

    @property
    def params(self):
        return self.state["params"]

    def record_result(self, result):
        if not self.enabled:
            return
        bucket = self._result_to_bucket(result)
        self.state["history"].append({"bucket": bucket, "time": time.time()})
        self.state["history"] = self.state["history"][-self.window_size:]
        win_rate = self.win_rate()
        self._adjust(win_rate)
        self.state["last_win_rate"] = round(win_rate, 3)
        self.state["total_matches"] = int(self.state.get("total_matches", 0)) + 1
        self._save()
        print(
            "Adaptive brain:",
            f"result={result}",
            f"win_rate={win_rate:.1%}",
            f"safe_mult={self.params['safe_range_multiplier']:.2f}",
            f"strafe={self.params['strafe_blend']:.2f}",
        )

    def apply_to_play(self, play_instance):
        params = self.params if self.enabled else DEFAULTS
        play_instance.adaptive_safe_range_multiplier = params["safe_range_multiplier"]
        play_instance.strafe_blend = params["strafe_blend"]
        play_instance.strafe_interval = params["strafe_interval"]
        play_instance.attack_cooldown = params["attack_cooldown"]

    def win_rate(self):
        history = self.state.get("history", [])
        wins = sum(1 for item in history if item.get("bucket") == "win")
        losses = sum(1 for item in history if item.get("bucket") == "loss")
        total = wins + losses
        return 0.5 if total <= 0 else wins / total

    def summary(self):
        return (
            f"Adaptive brain: enabled={self.enabled}, matches={self.state.get('total_matches', 0)}, "
            f"win_rate={self.state.get('last_win_rate', 'n/a')}, params={self.params}"
        )

    @staticmethod
    def _result_to_bucket(result):
        normalized = str(result).lower().strip()
        if normalized in ("1st", "2nd", "victory"):
            return "win"
        if normalized in ("4th", "defeat"):
            return "loss"
        return "draw"

    @staticmethod
    def _clamp(key, value):
        low, high = LIMITS[key]
        return max(low, min(high, value))

    def _adjust(self, win_rate):
        params = self.state["params"]
        if win_rate > 0.62:
            params["safe_range_multiplier"] = self._clamp("safe_range_multiplier", params["safe_range_multiplier"] - STEP["safe_range_multiplier"])
            params["strafe_blend"] = self._clamp("strafe_blend", params["strafe_blend"] + STEP["strafe_blend"])
            params["strafe_interval"] = self._clamp("strafe_interval", params["strafe_interval"] - STEP["strafe_interval"])
            params["attack_cooldown"] = self._clamp("attack_cooldown", params["attack_cooldown"] - STEP["attack_cooldown"])
        elif win_rate < 0.35:
            params["safe_range_multiplier"] = self._clamp("safe_range_multiplier", params["safe_range_multiplier"] + STEP["safe_range_multiplier"])
            params["strafe_blend"] = self._clamp("strafe_blend", params["strafe_blend"] - STEP["strafe_blend"])
            params["strafe_interval"] = self._clamp("strafe_interval", params["strafe_interval"] + STEP["strafe_interval"])
            params["attack_cooldown"] = self._clamp("attack_cooldown", params["attack_cooldown"] + STEP["attack_cooldown"])

    def _load(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data.setdefault("history", [])
                data.setdefault("total_matches", 0)
                data.setdefault("last_win_rate", None)
                params = data.setdefault("params", {})
                for key, value in DEFAULTS.items():
                    params.setdefault(key, value)
                    params[key] = self._clamp(key, float(params[key]))
                return data
            except Exception as e:
                print(f"Adaptive brain: could not load state ({e}), starting fresh.")
        return {"params": dict(DEFAULTS), "history": [], "total_matches": 0, "last_win_rate": None}

    def _save(self):
        try:
            folder = os.path.dirname(self.state_path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Adaptive brain: could not save state: {e}")
