#!/usr/bin/env python3
"""番茄钟 - 桌面番茄钟软件
   双击运行，或命令行: python pomodoro.py
"""

import tkinter as tk
import math
import time
import threading
import json
import os
import sys
from pathlib import Path

# ── 常量 ──────────────────────────────────────────────
WORK_SEC      = 25 * 60   # 专注 25 分钟
SHORT_BREAK   =  5 * 60   # 短休 5 分钟
LONG_BREAK    = 15 * 60   # 长休 15 分钟
LONG_EVERY    = 4         # 每 4 个番茄后长休
CIRCLE_R      = 100       # 进度环半径
LINE_W        = 8         # 环线宽

# 主题色 — 白底黑字
C_BG       = "#ffffff"
C_TOMATO   = "#e74c3c"
C_TOMATO_D = "#c0392b"
C_GREEN    = "#27ae60"
C_GREEN_D  = "#1e8449"
C_TEXT     = "#1a1a1a"
C_MUTED    = "#999999"
C_RING_BG  = "#e8e8e8"
C_BTN_BG   = "#f0f0f0"
C_BTN_HV   = "#e0e0e0"
C_DOT_OFF  = "#e0e0e0"
C_TAB_BG   = "#f0f0f0"


# ── 持久化数据 ────────────────────────────────────────
DATA_FILE = Path(__file__).parent / ".pomodoro_data.json"


def load_data():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "total_sessions": 0, "today": "", "today_sessions": 0,
        "daily_log": {}  # {"2026-06-13": 3, ...}
    }


def save_data(d):
    DATA_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                         encoding="utf-8")


# ── 工具函数 ──────────────────────────────────────────
def fmt_time(sec):
    """秒数 -> MM:SS"""
    m, s = divmod(sec, 60)
    return f"{m:02d}:{s:02d}"


def play_beep():
    """Windows 系统提示音"""
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        pass


def show_toast(title, body):
    """Windows 10/11 Toast 通知"""
    try:
        from win10toast import ToastNotifier
        ToastNotifier().show_toast(title, body, duration=5, threaded=True)
    except ImportError:
        pass  # win10toast 可选


# ── 鼠标悬停提示 ──────────────────────────────────────
class ToolTip:
    """鼠标放上按钮时显示提示文字"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None):
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() - 8
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.tip, text=self.text,
            font=("Segoe UI", 9), bg="#333333", fg="#ffffff",
            padx=8, pady=3, relief=tk.FLAT, bd=0
        ).pack()
        self.tip.lift()

    def _hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ── 主应用 ────────────────────────────────────────────
class PomodoroApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("番茄钟")
        self.root.configure(bg=C_BG)
        self.root.resizable(True, True)
        self.root.minsize(260, 340)

        # 窗口置顶
        self.root.attributes("-topmost", True)
        self.always_on_top = True

        # 窗口居中
        w, h = 330, 400
        sx = (self.root.winfo_screenwidth() - w) // 2
        sy = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{sx}+{sy}")

        # 无标题栏? 保留标题栏，但设小图标
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        # ── 状态 ──
        self.mode = "work"       # work | break | longBreak
        self.total_sec = WORK_SEC
        self.remaining = WORK_SEC
        self._timer_id = None
        self.sessions_today = 0
        self.total_sessions = 0
        self.is_break = False
        self._load()

        # ── 绑定事件 ──
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<KeyPress-space>", lambda e: self.toggle())
        self.root.bind("<KeyPress-Escape>", lambda e: self.reset())
        self.root.bind("<KeyPress-Right>", lambda e: self.skip())

        # ── 构建界面 ──
        self._build_ui()
        self._draw_ring(0)
        self._update_display()
        self._update_dots()
        self._set_window_title()

    # ── 持久化 ──────────────────────────────────────
    def _load(self):
        d = load_data()
        self.total_sessions = d.get("total_sessions", 0)
        self.daily_log = d.get("daily_log", {})
        today = time.strftime("%Y-%m-%d")
        if d.get("today") == today:
            self.sessions_today = d.get("today_sessions", 0)
        else:
            self.sessions_today = 0

    def _save(self):
        save_data({
            "total_sessions": self.total_sessions,
            "today": time.strftime("%Y-%m-%d"),
            "today_sessions": self.sessions_today,
            "daily_log": self.daily_log,
        })

    # ── 界面构建 ────────────────────────────────────
    def _build_ui(self):
        # 顶层操作栏
        topbar = tk.Frame(self.root, bg=C_BG)
        topbar.pack(fill=tk.X, padx=10, pady=(8, 0))

        self.btn_pin = tk.Button(
            topbar, text="📌" if self.always_on_top else "📍",
            font=("Segoe UI", 10), bg=C_BTN_BG, fg=C_TEXT,
            relief=tk.FLAT, bd=0, padx=6, pady=2,
            activebackground=C_BTN_HV, activeforeground=C_TEXT,
            cursor="hand2", command=self._toggle_pin)
        self.btn_pin.pack(side=tk.LEFT)

        tk.Label(topbar, text="番茄钟", font=("Segoe UI", 11, "bold"),
                 bg=C_BG, fg=C_TEXT).pack(side=tk.LEFT, padx=12)

        self.btn_stats = tk.Button(
            topbar, text="📊",
            font=("Segoe UI", 12), bg=C_BTN_BG, fg=C_TEXT,
            relief=tk.FLAT, bd=0, padx=6, pady=2,
            activebackground=C_BTN_HV, activeforeground=C_TEXT,
            cursor="hand2", command=self._show_stats)
        self.btn_stats.pack(side=tk.RIGHT, padx=(4, 0))
        ToolTip(self.btn_stats, "专注时长统计")

        self.lbl_count = tk.Label(
            topbar, text="", font=("Segoe UI", 9), bg=C_BG, fg=C_MUTED)
        self.lbl_count.pack(side=tk.RIGHT)

        # 模式切换
        tabs = tk.Frame(self.root, bg=C_BG)
        tabs.pack(pady=(12, 0))

        tab_frame = tk.Frame(tabs, bg=C_TAB_BG)
        tab_frame.pack()
        tab_frame.configure(borderwidth=0)

        self.tab_btns = {}
        for text, key in [("🍅 专注", "work"),
                          ("☕ 短休", "break"),
                          ("🌿 长休", "longBreak")]:
            btn = tk.Button(
                tab_frame, text=text, font=("Segoe UI", 10),
                bg=C_TAB_BG, fg=C_MUTED,
                relief=tk.FLAT, bd=0, padx=12, pady=6,
                activebackground=C_TOMATO, activeforeground="white",
                cursor="hand2",
                command=lambda k=key: self.set_mode(k))
            btn.pack(side=tk.LEFT)
            self.tab_btns[key] = btn
        self._highlight_tab()

        # 圆形进度条 Canvas
        canvas_size = (CIRCLE_R + LINE_W) * 2 + 20
        self.canvas = tk.Canvas(
            self.root, width=canvas_size, height=canvas_size,
            bg=C_BG, highlightthickness=0)
        self.canvas.pack(pady=(16, 4), expand=True)

        cx = cy = canvas_size // 2
        self._cx, self._cy = cx, cy

        # 背景圆环
        self.canvas.create_arc(
            cx - CIRCLE_R, cy - CIRCLE_R,
            cx + CIRCLE_R, cy + CIRCLE_R,
            outline=C_RING_BG, width=LINE_W, style=tk.ARC,
            start=0, extent=359.9)

        # 进度弧 (用 arc 方式: 画一个很短的弧逐步拉长)
        self.ring_arc = self.canvas.create_arc(
            cx - CIRCLE_R, cy - CIRCLE_R,
            cx + CIRCLE_R, cy + CIRCLE_R,
            outline=C_TOMATO, width=LINE_W,
            style=tk.ARC, start=90, extent=0)

        # 中心时间文字 — 画在 Canvas 上确保始终居中
        self.text_time = self.canvas.create_text(
            cx, cy - 12, text="25:00",
            font=("Consolas", 44, "bold"), fill=C_TEXT)
        self.text_state = self.canvas.create_text(
            cx, cy + 26, text="专注中",
            font=("Segoe UI", 10), fill=C_MUTED)

        # 番茄圆点
        dots_frame = tk.Frame(self.root, bg=C_BG)
        dots_frame.pack(pady=(4, 0))
        self.dot_labels = []
        for _ in range(8):
            lbl = tk.Label(dots_frame, text="●", font=("Segoe UI", 10),
                           bg=C_BG, fg=C_DOT_OFF)
            lbl.pack(side=tk.LEFT, padx=2)
            self.dot_labels.append(lbl)

        # 控制按钮
        ctrl = tk.Frame(self.root, bg=C_BG)
        ctrl.pack(pady=(12, 10))

        btn_side = dict(
            font=("Segoe UI", 16), relief=tk.FLAT, bd=0,
            activebackground=C_BTN_HV, activeforeground=C_TEXT,
            cursor="hand2", width=4, height=1)

        self.btn_reset = tk.Button(
            ctrl, text="↺", bg=C_BTN_BG, fg=C_TEXT,
            command=self.reset, **btn_side)
        self.btn_reset.pack(side=tk.LEFT, padx=8)
        ToolTip(self.btn_reset, "重置 (Esc)")

        self.btn_play = tk.Button(
            ctrl, text="▶", bg=C_TOMATO, fg="white",
            font=("Segoe UI", 18, "bold"), relief=tk.FLAT, bd=0,
            width=5, height=1, cursor="hand2",
            activebackground=C_TOMATO_D, activeforeground="white",
            command=self.toggle)
        self.btn_play.pack(side=tk.LEFT, padx=8)
        ToolTip(self.btn_play, "开始 / 暂停 (空格)")

        self.btn_skip = tk.Button(
            ctrl, text="⏭", bg=C_BTN_BG, fg=C_MUTED,
            command=self.skip, **btn_side)
        self.btn_skip.pack(side=tk.LEFT, padx=8)
        ToolTip(self.btn_skip, "跳过当前阶段 (→)")

        # 底部
        self.lbl_footer = tk.Label(
            self.root, text="", font=("Segoe UI", 8),
            bg=C_BG, fg=C_MUTED)
        self.lbl_footer.pack(side=tk.BOTTOM, pady=(0, 8))

        self._update_footer()

    # ── 进度环绘制 ──────────────────────────────────
    def _draw_ring(self, fraction):
        """fraction: 0.0 ~ 1.0, 已消耗比例"""
        # 使用 arc 的 extent 来表示进度
        # start=90 (12 点钟方向), extent 顺时针
        extent = -fraction * 359.9  # 负值 = 逆时针
        color = C_GREEN if self.is_break else C_TOMATO
        self.canvas.itemconfig(self.ring_arc,
                               extent=extent, outline=color)

    # ── 界面更新 ────────────────────────────────────
    def _update_display(self):
        self.canvas.itemconfig(self.text_time, text=fmt_time(self.remaining))
        state_text = {
            "work": "专注中", "break": "休息中", "longBreak": "长休息"
        }
        self.canvas.itemconfig(self.text_state,
                               text=state_text.get(self.mode, ""))
        self._draw_ring(1 - self.remaining / self.total_sec)

    def _update_dots(self):
        done = min(self.sessions_today, 8)
        for i, lbl in enumerate(self.dot_labels):
            if i < done:
                lbl.config(fg=C_TOMATO)
            else:
                lbl.config(fg=C_DOT_OFF)

    def _update_footer(self):
        self.lbl_footer.config(
            text=f"今日 {self.sessions_today} 个 · 累计 {self.total_sessions} 个番茄")

    def _set_window_title(self):
        self.root.title(f"{fmt_time(self.remaining)} · 番茄钟")

    def _highlight_tab(self):
        for key, btn in self.tab_btns.items():
            if key == self.mode:
                btn.config(bg=C_TOMATO, fg="white",
                           activebackground=C_TOMATO_D)
            else:
                btn.config(bg=C_TAB_BG, fg=C_MUTED,
                           activebackground=C_BTN_HV)

    # ── 统计窗口 ────────────────────────────────────
    def _show_stats(self):
        """打开统计二级页面"""
        win = tk.Toplevel(self.root)
        win.title("专注时长统计")
        win.configure(bg=C_BG)
        win.resizable(False, False)
        win.geometry("440x380")
        # 居中于主窗口
        win.transient(self.root)
        win.grab_set()
        win.focus_set()

        # 顶栏 — 图表切换
        bar = tk.Frame(win, bg=C_BG)
        bar.pack(fill=tk.X, padx=16, pady=(12, 0))

        tk.Label(bar, text="📊 专注统计", font=("Segoe UI", 12, "bold"),
                 bg=C_BG, fg=C_TEXT).pack(side=tk.LEFT)

        chart_var = tk.StringVar(value="bar")

        def switch_chart(v):
            chart_var.set(v)
            draw()

        btn_bar = tk.Button(
            bar, text="柱状图", font=("Segoe UI", 10),
            bg=C_TOMATO, fg="white", relief=tk.FLAT, bd=0, padx=10, pady=3,
            activebackground=C_TOMATO_D, activeforeground="white",
            cursor="hand2", command=lambda: switch_chart("bar"))
        btn_bar.pack(side=tk.RIGHT, padx=(0, 4))

        btn_pie = tk.Button(
            bar, text="扇形图", font=("Segoe UI", 10),
            bg=C_TAB_BG, fg=C_MUTED, relief=tk.FLAT, bd=0, padx=10, pady=3,
            activebackground=C_BTN_HV, activeforeground=C_TEXT,
            cursor="hand2", command=lambda: switch_chart("pie"))
        btn_pie.pack(side=tk.RIGHT, padx=4)

        # 更新按钮高亮
        def update_toggle():
            if chart_var.get() == "bar":
                btn_bar.config(bg=C_TOMATO, fg="white")
                btn_pie.config(bg=C_TAB_BG, fg=C_MUTED)
            else:
                btn_bar.config(bg=C_TAB_BG, fg=C_MUTED)
                btn_pie.config(bg=C_TOMATO, fg="white")

        # Canvas
        cw, ch = 408, 280
        canvas = tk.Canvas(win, width=cw, height=ch, bg=C_BG,
                           highlightthickness=0)
        canvas.pack(pady=12)

        # 底部汇总
        footer = tk.Label(win, text="", font=("Segoe UI", 9),
                          bg=C_BG, fg=C_MUTED)
        footer.pack(pady=(0, 8))

        # 颜色板
        BAR_COLORS = [
            "#e74c3c", "#e67e22", "#f1c40f", "#2ecc71",
            "#3498db", "#9b59b6", "#1abc9c"
        ]

        def draw():
            canvas.delete("all")
            update_toggle()

            # 整理最近 7 天数据
            days = []
            for i in range(6, -1, -1):
                d = time.strftime("%Y-%m-%d",
                                  time.localtime(time.time() - i * 86400))
                label = time.strftime("%m/%d",
                                      time.localtime(time.time() - i * 86400))
                count = self.daily_log.get(d, 0)
                mins = count * 25
                days.append((label, count, mins))

            total_mins = sum(d[2] for d in days)
            total_sessions = sum(d[1] for d in days)
            footer.config(
                text=f"近7天合计: {total_sessions} 个番茄 · "
                     f"{total_mins // 60} 小时 {total_mins % 60} 分钟")

            if chart_var.get() == "bar":
                self._draw_bar_chart(canvas, cw, ch, days, BAR_COLORS)
            else:
                self._draw_pie_chart(canvas, cw, ch, days, BAR_COLORS)

        draw()
        win.wait_window()

    @staticmethod
    def _draw_bar_chart(cv, cw, ch, days, colors):
        """绘制柱状图"""
        n = len(days)
        max_mins = max(d[2] for d in days) if any(d[2] for d in days) else 1
        # 图表区域
        ml, mr, mt, mb = 50, 20, 30, 45
        bw = (cw - ml - mr) // n  # 每柱宽度

        # 标题
        cv.create_text(cw // 2, 8, text="每日专注时长（分钟）",
                       font=("Segoe UI", 10, "bold"), fill=C_TEXT,
                       anchor=tk.CENTER)

        # Y 轴刻度
        for i in range(5):
            y = mt + (ch - mt - mb) * (4 - i) / 4
            val = int(max_mins * i / 4)
            cv.create_line(ml - 4, y, ml, y, fill=C_MUTED)
            cv.create_text(ml - 8, y, text=str(val),
                           font=("Segoe UI", 7), fill=C_MUTED,
                           anchor=tk.E)
            if i > 0:
                cv.create_line(ml, y, cw - mr, y, fill=C_RING_BG, dash=(2, 4))

        # 柱子和标签
        for i, (label, count, mins) in enumerate(days):
            x1 = ml + i * bw + 6
            x2 = ml + (i + 1) * bw - 6
            bar_h = (mins / max_mins) * (ch - mt - mb) if mins > 0 else 0
            y1 = mt + (ch - mt - mb) - bar_h
            y2 = mt + (ch - mt - mb)

            color = colors[i % len(colors)]
            cv.create_rectangle(x1, y1, x2, y2, fill=color,
                                outline="", width=0)
            # 数值标签
            if mins > 0:
                cv.create_text((x1 + x2) // 2, y1 - 10,
                               text=f"{mins}",
                               font=("Segoe UI", 8, "bold"),
                               fill=C_TEXT, anchor=tk.S)
            # 日期标签
            cv.create_text((x1 + x2) // 2, y2 + 12,
                           text=label,
                           font=("Segoe UI", 8), fill=C_MUTED,
                           anchor=tk.N)

    @staticmethod
    def _draw_pie_chart(cv, cw, ch, days, colors):
        """绘制扇形图"""
        cx, cy = cw // 2 - 15, ch // 2 + 10
        r = min(cx - 40, cy - 40)

        # 标题
        cv.create_text(cw // 2, 8, text="每日专注占比",
                       font=("Segoe UI", 10, "bold"), fill=C_TEXT,
                       anchor=tk.CENTER)

        total_mins = sum(d[2] for d in days)
        if total_mins == 0:
            cv.create_text(cx, cy, text="暂无数据",
                           font=("Segoe UI", 14), fill=C_MUTED,
                           anchor=tk.CENTER)
            return

        start_angle = 90
        for i, (label, count, mins) in enumerate(days):
            if mins == 0:
                continue
            extent = -(mins / total_mins) * 360
            color = colors[i % len(colors)]
            cv.create_arc(cx - r, cy - r, cx + r, cy + r,
                          start=start_angle, extent=extent,
                          fill=color, outline="white", width=2)
            start_angle += extent

        # 图例
        lx = cx + r + 20
        ly = cy - r + 10
        for i, (label, count, mins) in enumerate(days):
            if mins == 0:
                continue
            y = ly + i * 24
            color = colors[i % len(colors)]
            cv.create_rectangle(lx, y, lx + 12, y + 12,
                                fill=color, outline="")
            pct = mins / total_mins * 100
            cv.create_text(
                lx + 18, y + 6, anchor=tk.W,
                text=f"{label}  {mins}min ({pct:.0f}%)",
                font=("Segoe UI", 8), fill=C_TEXT)

    # ── 置顶切换 ────────────────────────────────────
    def _toggle_pin(self):
        self.always_on_top = not self.always_on_top
        self.root.attributes("-topmost", self.always_on_top)
        self.btn_pin.config(text="📌" if self.always_on_top else "📍")

    # ── 模式切换 ────────────────────────────────────
    def set_mode(self, mode):
        self._stop_timer()
        self.mode = mode
        if mode == "work":
            self.total_sec = WORK_SEC
            self.is_break = False
        elif mode == "break":
            self.total_sec = SHORT_BREAK
            self.is_break = True
        else:
            self.total_sec = LONG_BREAK
            self.is_break = True
        self.remaining = self.total_sec
        self._update_display()
        self._highlight_tab()
        self._set_window_title()
        self.btn_play.config(text="▶", bg=C_TOMATO, fg="white",
                             activebackground=C_TOMATO_D)

    # ── 计时逻辑 ────────────────────────────────────
    def _tick(self):
        if self.remaining <= 0:
            self._on_finish()
            return
        self.remaining -= 1
        self._update_display()
        self._set_window_title()
        self._timer_id = self.root.after(1000, self._tick)

    def _stop_timer(self):
        if self._timer_id:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None

    def toggle(self):
        if self._timer_id:
            self._stop_timer()
            self.btn_play.config(text="▶", bg=C_TOMATO, fg="white",
                                 activebackground=C_TOMATO_D)
        else:
            self._timer_id = self.root.after(1000, self._tick)
            self.btn_play.config(text="⏸", bg=C_GREEN, fg="white",
                                 activebackground=C_GREEN_D)

    def reset(self):
        self._stop_timer()
        self.remaining = self.total_sec
        self._update_display()
        self._set_window_title()
        self.btn_play.config(text="▶", bg=C_TOMATO, fg="white",
                             activebackground=C_TOMATO_D)

    def skip(self):
        self._stop_timer()
        self.remaining = 0
        self._on_finish()

    def _on_finish(self):
        """计时结束"""
        self._stop_timer()
        self.btn_play.config(text="▶", bg=C_TOMATO, fg="white",
                             activebackground=C_TOMATO_D)

        if self.is_break:
            # 休息结束 → 提示开始工作
            show_toast("休息结束", "该开始下一轮专注了 💪")
            play_beep()
            # 自动切换到工作模式
            self.mode = "work"
            self.total_sec = WORK_SEC
            self.remaining = self.total_sec
            self.is_break = False
            self._update_display()
            self._highlight_tab()
            self._set_window_title()
            # 自动开始
            self.toggle()
        else:
            # 工作完成 → 计数 & 休息
            self.sessions_today += 1
            self.total_sessions += 1
            today = time.strftime("%Y-%m-%d")
            self.daily_log[today] = self.daily_log.get(today, 0) + 1
            self._save()
            self._update_dots()
            self._update_footer()

            show_toast("番茄完成！🍅", "休息一下吧～")
            play_beep()

            # 判断短休还是长休
            if self.sessions_today % LONG_EVERY == 0:
                self.mode = "longBreak"
                self.total_sec = LONG_BREAK
            else:
                self.mode = "break"
                self.total_sec = SHORT_BREAK
            self.remaining = self.total_sec
            self.is_break = True
            self._update_display()
            self._highlight_tab()
            self._set_window_title()
            # 自动开始休息
            self.toggle()

            # 闪烁窗口提醒
            self._flash_window()

    def _flash_window(self):
        """短暂闪烁窗口"""
        for i in range(4):
            delay = i * 200
            self.root.after(delay + 0, lambda: self.root.attributes("-topmost", True))
            self.root.after(delay + 100, lambda: self.root.attributes(
                "-topmost", self.always_on_top))

    # ── 关闭 ────────────────────────────────────────
    def _on_close(self):
        self._stop_timer()
        self._save()
        self.root.destroy()

    # ── 运行 ────────────────────────────────────────
    def run(self):
        self.root.mainloop()


# ── 入口 ────────────────────────────────────────────────
if __name__ == "__main__":
    # 可选: 安装 win10toast 以获得桌面通知
    try:
        import win10toast  # noqa
    except ImportError:
        print("[提示] 安装桌面通知: pip install win10toast")
        print("[提示] 目前使用系统提示音代替\n")

    app = PomodoroApp()
    app.run()
