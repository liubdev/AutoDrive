"""
AutoDrive - Windows 应用自动化
"""
import sys, time, threading, subprocess, json, os
from pathlib import Path
from datetime import datetime
from tkinter import ttk, messagebox, font
import tkinter as tk

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from automation.apps.dts import DtsApp

# ── 颜色主题 ───────────────────────────────────

C = {
    "bg": "#F5F5F5",
    "card": "#FFFFFF",
    "primary": "#0078D4",
    "primary_hover": "#106EBE",
    "text": "#333333",
    "text_light": "#888888",
    "border": "#E0E0E0",
    "success": "#107C10",
    "error": "#D13438",
    "shadow": "#00000015",
}


# ── 设备定义 ───────────────────────────────────

DEVICES = [
    {
        "id": "dts",
        "name": "DTS 诊断仪",
        "desc": "DTS650 数据流读取 / 故障诊断",
        "icon": "🔧",
        "class": DtsApp,
    },
]

SCRIPTS_DIR = _HERE / "scripts"


# ── 主窗口 ────────────────────────────────────

class AutoDriveApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AutoDrive")
        self.root.configure(bg=C["bg"])
        self.root.geometry("780x620")
        self.root.minsize(700, 550)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Unmap>", self._on_minimize)

        # 悬浮球
        self._orb = None
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self._ox, self._oy = sw - 80, sh - 80

        self._build_ui()
        self._create_orb()

    # ── 构建界面 ──

    def _build_ui(self):
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(2, weight=0)
        self.root.grid_columnconfigure(0, weight=1)

        # ── 标题栏 ──
        header = tk.Frame(self.root, bg=C["primary"], height=48)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        tk.Label(header, text="AutoDrive", fg="white", bg=C["primary"],
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=20, pady=10)
        tk.Label(header, text="v1.0", fg="#D0D0D0", bg=C["primary"],
                 font=("Segoe UI", 9)).pack(side="left", pady=10)

        # ── 主内容 ──
        main = tk.Frame(self.root, bg=C["bg"])
        main.grid(row=1, column=0, sticky="nsew", padx=30, pady=20)
        main.grid_columnconfigure(0, weight=1)

        # 标题
        tk.Label(main, text="请选择要控制的设备", bg=C["bg"], fg=C["text"],
                 font=("Segoe UI", 16, "bold")).pack(pady=(0, 20))

        # 设备卡片
        cards = tk.Frame(main, bg=C["bg"])
        cards.pack(pady=10)
        for dev in DEVICES:
            self._create_device_card(cards, dev)

        # 日志区域
        tk.Frame(main, bg=C["border"], height=1).pack(fill="x", pady=(20, 10))
        tk.Label(main, text="操作日志", bg=C["bg"], fg=C["text_light"],
                 font=("Segoe UI", 10)).pack(anchor="w")

        log_frame = tk.Frame(main, bg=C["card"], bd=1, relief="solid",
                             highlightbackground=C["border"], highlightthickness=1)
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, height=8, bg=C["card"], fg=C["text"],
                           font=("Consolas", 9), bd=0, padx=10, pady=8,
                           state="disabled")
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)

        # ── 状态栏 ──
        status = tk.Frame(self.root, bg=C["border"], height=28)
        status.grid(row=2, column=0, sticky="ew")
        status.grid_propagate(False)
        self.status_label = tk.Label(status, text="就绪", bg=C["border"],
                                     fg=C["text_light"], font=("Segoe UI", 9),
                                     anchor="w")
        self.status_label.pack(side="left", padx=12)

    def _create_device_card(self, parent, dev):
        card = tk.Frame(parent, bg=C["card"], bd=1, relief="solid",
                        highlightbackground=C["border"], highlightthickness=1,
                        width=320, height=100, cursor="hand2")
        card.pack(pady=6)
        card.pack_propagate(False)

        # 悬停效果
        def on_enter(e): card.configure(highlightbackground=C["primary"])
        def on_leave(e): card.configure(highlightbackground=C["border"])
        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        tk.Label(card, text=dev["icon"], bg=C["card"],
                 font=("Segoe UI", 28)).place(x=16, y=28)
        tk.Label(card, text=dev["name"], bg=C["card"], fg=C["text"],
                 font=("Segoe UI", 13, "bold")).place(x=80, y=24)
        tk.Label(card, text=dev["desc"], bg=C["card"], fg=C["text_light"],
                 font=("Segoe UI", 9)).place(x=80, y=50)

        btn = tk.Button(card, text="▶ 执行", bg=C["primary"], fg="white",
                        bd=0, padx=12, pady=2, cursor="hand2",
                        activebackground=C["primary_hover"],
                        font=("Segoe UI", 9, "bold"),
                        command=lambda d=dev: self._run_device(d))
        btn.place(x=240, y=56)
        card.bind("<Button-1>", lambda e, d=dev: self._run_device(d))

    # ── 日志 ──

    def log_msg(self, msg, tag=""):
        self.log.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.insert("end", f"[{ts}] ", "time")
        self.log.insert("end", msg + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")
        self.root.update()

    def set_status(self, text):
        self.status_label.configure(text=text)

    # ── 设备执行 ──

    def _run_device(self, dev):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.log_msg(f"启动 {dev['name']}...")
        self.set_status(f"执行中: {dev['name']}")

        t = threading.Thread(target=self._do_run, args=(dev,), daemon=True)
        t.start()

    def _do_run(self, dev):
        try:
            app_class = dev["class"]
            app = app_class()
            app.ensure_running(timeout=30)
            self.log_msg("✓ 设备已连接")
            app.disconnect()
            self.log_msg("✓ 完成")
        except Exception as e:
            self.log_msg(f"✗ 失败: {e}")
        self.set_status("就绪")

    # ── 悬浮球 ──

    def _create_orb(self):
        self._orb = tk.Toplevel(self.root)
        self._orb.overrideredirect(True)
        self._orb.attributes("-topmost", True)
        self._orb.attributes("-transparentcolor", "white")
        self._orb.geometry(f"48x48+{self._ox}+{self._oy}")
        self._orb.withdraw()

        c = tk.Canvas(self._orb, width=48, height=48, highlightthickness=0, bg="white")
        c.pack()
        c.create_oval(2, 2, 46, 46, fill=C["primary"], outline="")
        c.create_text(24, 24, text="A", fill="white", font=("Arial", 16, "bold"))

        c.bind("<Button-1>", self._drag_start)
        c.bind("<B1-Motion>", self._drag_move)
        c.bind("<ButtonRelease-1>", self._drag_end)
        c.bind("<Double-Button-1>", lambda e: self._show_main())
        c.bind("<Button-3>", self._orb_menu)

    def _drag_start(self, e):
        self._dx = e.x_root - self._ox
        self._dy = e.y_root - self._oy

    def _drag_move(self, e):
        self._ox = e.x_root - self._dx
        self._oy = e.y_root - self._dy
        self._orb.geometry(f"+{self._ox}+{self._oy}")

    def _drag_end(self, e):
        self._ox = e.x_root - self._dx
        self._oy = e.y_root - self._dy

    def _orb_menu(self, e):
        m = tk.Menu(self._orb, tearoff=0)
        m.add_command(label="打开 AutoDrive", command=self._show_main)
        m.add_separator()
        m.add_command(label="退出", command=self._on_close)
        m.tk_popup(e.x_root, e.y_root)

    def _show_main(self):
        self.root.deiconify(); self.root.lift()
        self._orb.withdraw()

    def _on_minimize(self, e):
        if e.widget == self.root:
            self.root.withdraw(); self._orb.deiconify(); self._orb.lift()

    def _on_close(self):
        self._orb.destroy() if self._orb else None
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    AutoDriveApp().run()
