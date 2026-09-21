import json
import math
import os
import random
import re
import time
import tkinter as tk

ANIM_INTERVAL_MS = 33  # 30fps
CONFIG_RECHECK_SECONDS = 2.0 

BG_COLOR = "#020509"
RING_COLOR = "#3fd0ff"
RING_DIM_COLOR = "#0f3a4a"
CORE_COLOR = "#00FFFF"
GLOW_COLOR = "#3fd0ff"
TICK_LIT_COLOR = "#bff3ff"
TICK_DIM_COLOR = "#123244"
GLITCH_COLOR = "#ff2b6b"
BLINK_COLOR = "#ffffff"
BLINK_DURATION = 0.9   
BLINK_HZ = 6.0          
ERROR_BLINK_COLOR = "#ff2b2b"
ERROR_BLINK_DURATION = 1.2   
SHAKE_DURATION = 0.9         
SHAKE_AMPLITUDE = 0.10       

THINK_TAG_RE = re.compile(r"<think>(.*?)</think>", re.IGNORECASE | re.DOTALL)
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_BLANK_LIKE = {"", "none", "null", "todo", "changeme", "your-api-key", "xxx"}
DEFAULT_CORE_COLOR = CORE_COLOR
DEFAULT_GLOW_COLOR = GLOW_COLOR


def _resolve_orb_colors(config):
    if not isinstance(config, dict):
        return DEFAULT_CORE_COLOR, DEFAULT_GLOW_COLOR

    raw_core = config.get("core_ai_color")
    core = raw_core.strip() if isinstance(raw_core, str) and HEX_COLOR_RE.match(raw_core.strip()) else DEFAULT_CORE_COLOR

    glow_default = core if core != DEFAULT_CORE_COLOR else DEFAULT_GLOW_COLOR
    raw_glow = config.get("orb_color")
    glow = raw_glow.strip() if isinstance(raw_glow, str) and HEX_COLOR_RE.match(raw_glow.strip()) else glow_default

    return core, glow

REQUIRED_CONFIG_FIELDS = ("model", "api_key", "api_base")


def validate_config(config):
    errors = {}

    if not isinstance(config, dict):
        return False, {"config": "config is not a JSON object"}

    for field in REQUIRED_CONFIG_FIELDS:
        value = config.get(field)
        if not isinstance(value, str) or value.strip().lower() in _BLANK_LIKE:
            errors[field] = "missing or empty"
            continue
        value = value.strip()

        if field == "api_base":
            if not (value.startswith("http://") or value.startswith("https://")):
                errors[field] = "not a valid URL"
        elif field == "api_key":
            if len(value) < 8 or any(c.isspace() for c in value):
                errors[field] = "looks malformed"

    return (len(errors) == 0), errors


def _default_config_path():
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    candidates = [
        os.path.join(here, "config.json"),
        os.path.join(parent, "config.json"),
        os.path.join(os.getcwd(), "config.json"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[1]


def load_and_validate_config(config_path):
    if not os.path.exists(config_path):
        return False, {"config": "file not found"}, None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return False, {"config": f"failed to load: {exc}"}, None

    ok, errors = validate_config(config)
    return ok, errors, config


def extract_reasoning(message, content):
    reasoning = ""
    if isinstance(message, dict):
        for key in ("reasoning_content", "reasoning", "thinking", "thought"):
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                reasoning = value.strip()
                break

    cleaned_content = content
    if isinstance(content, str) and "<think>" in content.lower():
        found = THINK_TAG_RE.findall(content)
        if found:
            if not reasoning:
                reasoning = "\n\n".join(part.strip() for part in found if part.strip())
            cleaned_content = THINK_TAG_RE.sub("", content).strip()

    return reasoning, cleaned_content


def _lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = round(r1 + (r2 - r1) * t)
    g = round(g1 + (g2 - g1) * t)
    b = round(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"

class ThoughtVisualizer:
    def __init__(self, root, get_theme, is_dark_mode, is_busy, config_path=None):
        self.root = root
        self._get_theme = get_theme         
        self._is_dark_mode = is_dark_mode    
        self._is_busy = is_busy
        self.window = None
        self.canvas = None
        self._anim_job = None
        self._start_time = time.time()
        self._angle_a = 0.0
        self._angle_b = 0.0
        self._angle_c = 0.0
        self._tick_offset = 0.0
        self._energy = 0.0  
        self._look_x = 0.0        
        self._look_y = 0.0
        self._look_target_x = 0.0   
        self._look_target_y = 0.0
        self._next_glance_time = 0.0
        self._following_cursor = False
        self.last_reasoning = ""
        self._topmost = False
        self._core_color = DEFAULT_CORE_COLOR
        self._glow_color = DEFAULT_GLOW_COLOR
        self._config_path = config_path or _default_config_path()
        self._config_error = False
        self._config_error_details = {}
        self._last_config_check = 0.0
        self._online = True          
        self._offline_factor = 0.0   
        self._glitch_active_until = 0.0
        self._glitch_next_check = 0.0
        self._glitch_angle_jitter = 0.0
        self._glitch_radius_scale = 1.0
        self._blink_until = 0.0
        self._error_blink_until = 0.0
        self._shake_until = 0.0
        self._refresh_config_error()

    def set_online(self, online):
        self._online = online

    def _refresh_config_error(self):
        ok, errors, config = load_and_validate_config(self._config_path)
        self._config_error = not ok
        self._config_error_details = errors
        self._last_config_check = time.time()
        self._core_color, self._glow_color = _resolve_orb_colors(config)

    def set_config_error(self, has_error, details=None):
        self._config_error = bool(has_error)
        self._config_error_details = details or {}
        if self.is_open():
            self._draw()

    def check_config(self, config_path):
        ok, errors, _ = load_and_validate_config(config_path)
        self.set_config_error(not ok, errors)
        return ok, errors

    def is_open(self):
        return self.window is not None and self.window.winfo_exists()

    def open(self):
        if self.is_open():
            self.window.deiconify()
            if self._topmost:
                self._apply_topmost()
            else:
                self.window.lift()
            self.window.focus_force()
            return

        win = tk.Toplevel(self.root)
        win.title("Phoebe")
        win.geometry("420x420")
        win.minsize(240, 240)
        win.configure(bg=BG_COLOR)
        win.protocol("WM_DELETE_WINDOW", self.close)
        self.window = win

        canvas = tk.Canvas(win, bg=BG_COLOR, highlightthickness=0, bd=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas = canvas
        canvas.bind("<Configure>", lambda e: self._draw())

        self._apply_topmost()
        self._start_animation()

    def close(self):
        self._stop_animation()
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
        self.window = None
        self.canvas = None

    def destroy(self):
        self.close()

    def set_busy(self, busy):
        if self.is_open() and self._anim_job is None:
            self._start_animation()

    def push_reasoning(self, reasoning):
        self.last_reasoning = reasoning or ""

    def shake(self):
        now = time.time()
        self._shake_until = now + SHAKE_DURATION
        self._blink_until = now + BLINK_DURATION
        if self.is_open():
            self._draw()

    def flash_error(self):
        self._error_blink_until = time.time() + ERROR_BLINK_DURATION
        if self.is_open():
            self._draw()

    def apply_theme(self):
        return

    def set_topmost(self, enabled):
        self._topmost = bool(enabled)
        if self.is_open():
            self._apply_topmost()

    def _apply_topmost(self):
        if not self.is_open():
            return
        try:
            self.window.attributes("-topmost", self._topmost)
            if self._topmost:
                self.window.lower(self.root)
        except tk.TclError:
            pass

    def _start_animation(self):
        self._stop_animation()
        self._animate()

    def _stop_animation(self):
        if self._anim_job is not None:
            try:
                self.root.after_cancel(self._anim_job)
            except Exception:
                pass
            self._anim_job = None

    def _animate(self):
        if not self.is_open():
            self._anim_job = None
            return

        if time.time() - self._last_config_check >= CONFIG_RECHECK_SECONDS:
            self._refresh_config_error()

        if self._config_error:
            self._draw()
            self._anim_job = self.root.after(ANIM_INTERVAL_MS, self._animate)
            return

        busy = self._is_busy()
        target_energy = 1.0 if busy else 0.0
        self._energy += (target_energy - self._energy) * 0.15
        speed = 1.0 + self._energy * 5.5
        self._angle_a = (self._angle_a + 1.6 * speed) % 360
        self._angle_b = (self._angle_b - 1.1 * speed) % 360
        self._angle_c = (self._angle_c + 2.6 * speed) % 360
        self._tick_offset = (self._tick_offset + 2.2 * speed) % 360

        target_offline = 1.0 if self._online is False else 0.0
        self._offline_factor += (target_offline - self._offline_factor) * 0.08

        now = time.time()
        if self._offline_factor > 0.05:
            if now >= self._glitch_next_check:
                if random.random() < 0.35:
                    burst = 0.05 + 0.18 * random.random()
                    self._glitch_active_until = now + burst
                    self._glitch_angle_jitter = random.uniform(-24, 24) * self._offline_factor
                    self._glitch_radius_scale = 1.0 + random.uniform(-0.12, 0.12) * self._offline_factor
                self._glitch_next_check = now + random.uniform(0.12, 0.45)
        else:
            self._glitch_active_until = 0.0

        self._draw()
        self._anim_job = self.root.after(ANIM_INTERVAL_MS, self._animate)


    def _update_gaze(self, cx, cy, width, height):
        now = time.time()
        pointer_over = False

        try:
            px = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
            py = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
            if 0 <= px <= width and 0 <= py <= height:
                pointer_over = True
        except tk.TclError:
            pointer_over = False

        if pointer_over:
            dx, dy = px - cx, py - cy
            dist = math.hypot(dx, dy)
            if dist > 1e-6:
                norm = min(dist / (max(width, height) * 0.5), 1.0)
                norm = math.sqrt(norm) * 0.7
                self._look_target_x = (dx / dist) * norm
                self._look_target_y = (dy / dist) * norm
            self._following_cursor = True
            self._next_glance_time = now + random.uniform(0.8, 1.6)
        else:
            self._following_cursor = False
            if now >= self._next_glance_time:
                angle = random.uniform(0, 2 * math.pi)
                radius = random.uniform(0.15, 0.75)
                self._look_target_x = math.cos(angle) * radius
                self._look_target_y = math.sin(angle) * radius
                if random.random() < 0.25:
                    self._look_target_x = 0.0
                    self._look_target_y = 0.0
                self._next_glance_time = now + random.uniform(1.6, 4.2)
        wobble_x = 0.05 * math.sin(now * 0.6) + 0.03 * math.sin(now * 1.7 + 1.3)
        wobble_y = 0.05 * math.cos(now * 0.5 + 0.7) + 0.03 * math.sin(now * 1.3 + 2.1)
        target_x = self._look_target_x + wobble_x
        target_y = self._look_target_y + wobble_y
        ease = 0.045 if self._following_cursor else 0.03
        self._look_x += (target_x - self._look_x) * ease
        self._look_y += (target_y - self._look_y) * ease



    def _draw(self):
        canvas = self.canvas
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        width = canvas.winfo_width() or 420
        height = canvas.winfo_height() or 420
        if width <= 1 or height <= 1:
            return
        cx, cy = width / 2, height / 2
        max_r = min(width, height) * 0.46
        energy = self._energy
        t = time.time() - self._start_time
        self._update_gaze(cx, cy, width, height)
        gaze_reach = max_r * (0.30 + 0.12 * energy)
        gaze_x = cx + self._look_x * gaze_reach
        gaze_y = cy + self._look_y * gaze_reach
        shake_now = time.time()
        if shake_now < self._shake_until:
            shake_mag = max_r * SHAKE_AMPLITUDE * (self._shake_until - shake_now) / SHAKE_DURATION
            gaze_x += random.uniform(-1.0, 1.0) * shake_mag
            gaze_y += random.uniform(-1.0, 1.0) * shake_mag
        pulse_speed = 1.4 + energy * 9.0
        pulse = 0.5 + 0.5 * math.sin(t * pulse_speed)
        pulse_amplitude = 0.15 + energy * 0.35

        outer_r = max_r
        now_t = time.time()
        if now_t < self._error_blink_until:
            error_elapsed = ERROR_BLINK_DURATION - (self._error_blink_until - now_t)
            lit = (error_elapsed * BLINK_HZ) % 1.0 < 0.5
            outer_color = ERROR_BLINK_COLOR if lit else RING_DIM_COLOR
            outer_width = 3.0 if lit else 1.0
        elif time.time() < self._blink_until:
            blink_elapsed = BLINK_DURATION - (self._blink_until - time.time())
            lit = (blink_elapsed * BLINK_HZ) % 1.0 < 0.5
            outer_color = BLINK_COLOR if lit else RING_DIM_COLOR
            outer_width = 3.0 if lit else 1.0
        else:
            outer_color = _lerp_color(RING_DIM_COLOR, RING_COLOR, 0.3 + 0.2 * energy)
            outer_width = 1.5
        canvas.create_oval(
            cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r,
            outline=outer_color,
            width=outer_width,
        )


        if not self._config_error:
            tick_r_out = max_r
            tick_r_in = max_r * 0.92
            tick_count = 60
            lit_span = 10 + int(energy * 20)
            for i in range(tick_count):
                base_angle = (360 / tick_count) * i
                rel = (base_angle - self._tick_offset) % 360
                lit = rel < lit_span
                color = TICK_LIT_COLOR if lit else TICK_DIM_COLOR
                a = math.radians(base_angle)
                x0 = cx + tick_r_in * math.cos(a)
                y0 = cy + tick_r_in * math.sin(a)
                x1 = cx + tick_r_out * math.cos(a)
                y1 = cy + tick_r_out * math.sin(a)
                canvas.create_line(x0, y0, x1, y1, fill=color, width=1.4 if lit else 1.0)

            offline_factor = self._offline_factor
            glitch_active = offline_factor > 0.05 and time.time() < self._glitch_active_until

            ring_a_r, ring_a_angle, ring_a_color, ring_a_skip = self._offline_glitch(
                max_r * 0.78, self._angle_a,
                _lerp_color(RING_COLOR, CORE_COLOR, energy * 0.5),
                t, offline_factor, glitch_active, phase=0.0,
            )
            if not ring_a_skip:
                self._draw_dashed_ring(
                    canvas, cx, cy, ring_a_r, ring_a_angle,
                    segments=18, coverage=0.55,
                    color=ring_a_color,
                    width=2.2,
                )

            ring_b_r, ring_b_angle, ring_b_color, ring_b_skip = self._offline_glitch(
                max_r * 0.62, self._angle_b,
                _lerp_color(RING_DIM_COLOR, RING_COLOR, 0.4 + 0.6 * energy),
                t, offline_factor, glitch_active, phase=2.1,
            )
            if not ring_b_skip:
                self._draw_dashed_ring(
                    canvas, cx, cy, ring_b_r, ring_b_angle,
                    segments=10, coverage=0.4,
                    color=ring_b_color,
                    width=1.6,
                )

            marker_r, marker_angle_offset, marker_color, marker_skip = self._offline_glitch(
                max_r * 0.5, 0.0,
                _lerp_color(RING_COLOR, CORE_COLOR, 0.3 + 0.5 * energy),
                t, offline_factor, glitch_active, phase=4.2,
            )
            if not marker_skip:
                for k in range(3):
                    angle = self._angle_c + marker_angle_offset + k * 120
                    a0 = math.radians(angle)
                    a1 = math.radians(angle + 26)
                    self._draw_arc_segment(
                        canvas, cx, cy, marker_r, a0, a1,
                        color=marker_color,
                        width=2.4,
                    )


            core_max = max_r * (0.16 + 0.05 * energy) * (1.0 - pulse_amplitude / 2 + pulse_amplitude * pulse)
            layers = 6
            for i in range(layers, 0, -1):
                frac = i / layers
                r = core_max * frac
                color = _lerp_color(BG_COLOR, self._glow_color, (1 - frac) * (0.5 + 0.5 * energy))
                lag = 0.35 + 0.65 * frac
                lx = cx + (gaze_x - cx) * lag
                ly = cy + (gaze_y - cy) * lag
                canvas.create_oval(lx - r, ly - r, lx + r, ly + r, fill=color, outline="")

            core_r = core_max * 0.34
            canvas.create_oval(
                gaze_x - core_r, gaze_y - core_r, gaze_x + core_r, gaze_y + core_r,
                fill=_lerp_color(self._core_color, CORE_COLOR, energy * 0.4), outline="",
            )

    def _offline_glitch(self, r, angle, base_color, t, offline_factor, glitch_active, phase=0.0):
        if offline_factor <= 0.01:
            return r, angle, base_color, False

        if glitch_active:
            r = r * self._glitch_radius_scale
            angle = angle + self._glitch_angle_jitter

        flicker = 0.5 + 0.5 * math.sin(t * 9.0 + phase) + 0.5 * math.sin(t * 23.0 + 1.7 + phase)
        flicker = max(0.0, min(1.0, flicker / 1.5))
        fade_amount = offline_factor * (0.3 + 0.55 * flicker)
        color = _lerp_color(base_color, BG_COLOR, fade_amount)
        if glitch_active:
            color = _lerp_color(color, GLITCH_COLOR, 0.45 * offline_factor)

        skip = glitch_active and random.random() < 0.35 * offline_factor
        return r, angle, color, skip

    @staticmethod
    def _draw_dashed_ring(canvas, cx, cy, r, start_angle, segments, coverage, color, width):
        step = 360 / segments
        dash_len = step * coverage
        for i in range(segments):
            a0 = math.radians(start_angle + i * step)
            a1 = math.radians(start_angle + i * step + dash_len)
            ThoughtVisualizer._draw_arc_segment(canvas, cx, cy, r, a0, a1, color, width)

    @staticmethod
    def _draw_arc_segment(canvas, cx, cy, r, a0, a1, color, width, steps=6):
        points = []
        for s in range(steps + 1):
            a = a0 + (a1 - a0) * (s / steps)
            points.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            canvas.create_line(x0, y0, x1, y1, fill=color, width=width, capstyle=tk.ROUND)