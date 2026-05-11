"""
SecureChat — Telegram-like desktop client
Python 3.10+ | Tkinter

Запуск: python client.py
"""

import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Optional

from api_client import SecureChatAPI, SecureChatWS, APIError
from encryption import E2EEncryption

# ─── Константы ──────────────────────────────────────────────────────────────
DEFAULT_SERVER = DEFAULT_SERVER = os.getenv("SECURECHAT_SERVER", "http://85.215.220.246:9812")
KEY_FILE = os.path.expanduser("~/.securechat_key.pem")
CONFIG_FILE = os.path.expanduser("~/.securechat_config.json")

# ─── Цветовая схема ──────────────────────────────────────────────────────────
DARK = {
    "bg":        "#17212b",
    "sidebar":   "#0e1621",
    "chat_bg":   "#17212b",
    "input_bg":  "#242f3d",
    "header":    "#232e3c",
    "accent":    "#2b5278",
    "accent2":   "#5288c1",
    "text":      "#f5f5f5",
    "text_dim":  "#708499",
    "text_muted":"#4a6278",
    "my_bubble": "#2b5278",
    "their_bubble": "#182533",
    "online":    "#4dcd5e",
    "offline":   "#6c7883",
    "danger":    "#e53935",
    "border":    "#0d1620",
}

FONT_MAIN   = ("Segoe UI", 10)
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_SMALL  = ("Segoe UI", 9)
FONT_TITLE  = ("Segoe UI", 12, "bold")
FONT_MONO   = ("Consolas", 9)


# ════════════════════════════════════════════════════════════════════════════
#  Auth Window
# ════════════════════════════════════════════════════════════════════════════
class AuthWindow:
    def __init__(self, master, on_success):
        self.master = master
        self.on_success = on_success
        self.api = None

        master.title("SecureChat — Вход")
        master.geometry("420x620")
        master.resizable(True, True)
        master.minsize(380, 500)
        master.configure(bg=DARK["bg"])
        center_window(master, 420, 620)

        self._build()

    def _build(self):
        # Кнопка submit внизу — всегда видна
        self.submit_btn = tk.Button(self.master, text="ВОЙТИ", font=FONT_BOLD,
            bg=DARK["accent2"], fg="white", bd=0, cursor="hand2",
            padx=20, pady=12,
            command=self._submit)
        self.submit_btn.pack(side="bottom", fill="x", padx=40, pady=12)

        self.status_var = tk.StringVar()
        tk.Label(self.master, textvariable=self.status_var, font=FONT_SMALL,
                 bg=DARK["bg"], fg=DARK["danger"], wraplength=340).pack(side="bottom")

        # Прокручиваемая область сверху
        canvas = tk.Canvas(self.master, bg=DARK["bg"], bd=0, highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        inner = tk.Frame(canvas, bg=DARK["bg"])
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(
            canvas.find_all()[0], width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(
            int(-1*(e.delta/120)), "units"))

        # Logo
        tk.Label(inner, text="🔐", font=("Segoe UI Emoji", 40),
                 bg=DARK["bg"], fg=DARK["accent2"]).pack(pady=(30, 6))
        tk.Label(inner, text="SecureChat", font=("Segoe UI", 20, "bold"),
                 bg=DARK["bg"], fg=DARK["text"]).pack()
        tk.Label(inner, text="Зашифрованный мессенджер",
                 font=FONT_SMALL, bg=DARK["bg"], fg=DARK["text_dim"]).pack(pady=(0, 20))

        # Server URL
        sv_frame = tk.Frame(inner, bg=DARK["bg"])
        sv_frame.pack(fill="x", padx=40, pady=(0, 6))
        tk.Label(sv_frame, text="Сервер", font=FONT_SMALL,
                 bg=DARK["bg"], fg=DARK["text_dim"]).pack(anchor="w")
        self.server_var = tk.StringVar(value=DEFAULT_SERVER)
        tk.Entry(sv_frame, textvariable=self.server_var, font=FONT_MAIN,
            bg=DARK["input_bg"], fg=DARK["text"],
            insertbackground=DARK["text"], bd=0, relief="flat").pack(
            fill="x", ipady=8, pady=(0, 4))

        # Tabs
        tab_frame = tk.Frame(inner, bg=DARK["bg"])
        tab_frame.pack(fill="x", padx=40, pady=(10, 0))

        self.mode = tk.StringVar(value="login")
        self.btn_login = tk.Button(tab_frame, text="Войти", font=FONT_BOLD,
            bg=DARK["accent"], fg=DARK["text"], bd=0, cursor="hand2",
            padx=20, pady=6,
            command=lambda: self._switch("login"))
        self.btn_login.pack(side="left", expand=True, fill="x")
        self.btn_reg = tk.Button(tab_frame, text="Регистрация", font=FONT_BOLD,
            bg=DARK["input_bg"], fg=DARK["text_dim"], bd=0, cursor="hand2",
            padx=20, pady=6,
            command=lambda: self._switch("register"))
        self.btn_reg.pack(side="left", expand=True, fill="x")

        form = tk.Frame(inner, bg=DARK["bg"])
        form.pack(fill="x", padx=40, pady=14)

        # Email
        tk.Label(form, text="Email", font=FONT_SMALL,
                 bg=DARK["bg"], fg=DARK["text_dim"]).pack(anchor="w")
        self.email_var = tk.StringVar()
        tk.Entry(form, textvariable=self.email_var, font=FONT_MAIN,
            bg=DARK["input_bg"], fg=DARK["text"],
            insertbackground=DARK["text"], bd=0, relief="flat").pack(
            fill="x", ipady=8, pady=(0, 8))

        # Username (only for register)
        self.username_label = tk.Label(form, text="Имя пользователя", font=FONT_SMALL,
                 bg=DARK["bg"], fg=DARK["text_dim"])
        self.username_var = tk.StringVar()
        self.username_entry = tk.Entry(form, textvariable=self.username_var,
            font=FONT_MAIN, bg=DARK["input_bg"], fg=DARK["text"],
            insertbackground=DARK["text"], bd=0, relief="flat")

        # Password
        tk.Label(form, text="Пароль", font=FONT_SMALL,
                 bg=DARK["bg"], fg=DARK["text_dim"]).pack(anchor="w")
        self.pass_var = tk.StringVar()
        pe = tk.Entry(form, textvariable=self.pass_var, show="●", font=FONT_MAIN,
            bg=DARK["input_bg"], fg=DARK["text"],
            insertbackground=DARK["text"], bd=0, relief="flat")
        pe.pack(fill="x", ipady=8, pady=(0, 4))
        pe.bind("<Return>", lambda e: self._submit())

    def _switch(self, mode):
        self.mode.set(mode)
        if mode == "login":
            self.btn_login.configure(bg=DARK["accent"], fg=DARK["text"])
            self.btn_reg.configure(bg=DARK["input_bg"], fg=DARK["text_dim"])
            self.submit_btn.configure(text="ВОЙТИ")
            self.username_label.pack_forget()
            self.username_entry.pack_forget()
        else:
            self.btn_reg.configure(bg=DARK["accent"], fg=DARK["text"])
            self.btn_login.configure(bg=DARK["input_bg"], fg=DARK["text_dim"])
            self.submit_btn.configure(text="ЗАРЕГИСТРИРОВАТЬСЯ")
            self.username_label.pack(anchor="w")
            self.username_entry.pack(fill="x", pady=(0, 8))

    def _submit(self):
        server = self.server_var.get().strip()
        email = self.email_var.get().strip()
        password = self.pass_var.get()

        if not server or not email or not password:
            self.status_var.set("Заполните все поля")
            return

        self.submit_btn.configure(state="disabled", text="...")
        self.status_var.set("")

        def task():
            try:
                api = SecureChatAPI(server)
                if self.mode.get() == "login":
                    api.login(email, password)
                else:
                    username = self.username_var.get().strip()
                    if not username:
                        self.master.after(0, lambda: self.status_var.set("Введите имя пользователя"))
                        self.master.after(0, lambda: self.submit_btn.configure(state="normal", text="ЗАРЕГИСТРИРОВАТЬСЯ"))
                        return
                    api.register(email, username, password)
                self.master.after(0, lambda: self.on_success(api, server))
            except APIError as e:
                msg = str(e)
                self.master.after(0, lambda: self.status_var.set(msg))
                mode_text = "ВОЙТИ" if self.mode.get() == "login" else "ЗАРЕГИСТРИРОВАТЬСЯ"
                self.master.after(0, lambda: self.submit_btn.configure(state="normal", text=mode_text))
            except Exception as e:
                msg = f"Ошибка подключения: {e}"
                self.master.after(0, lambda: self.status_var.set(msg))
                mode_text = "ВОЙТИ" if self.mode.get() == "login" else "ЗАРЕГИСТРИРОВАТЬСЯ"
                self.master.after(0, lambda: self.submit_btn.configure(state="normal", text=mode_text))

        threading.Thread(target=task, daemon=True).start()


# ════════════════════════════════════════════════════════════════════════════
#  Main Chat Window
# ════════════════════════════════════════════════════════════════════════════
class ChatWindow:
    def __init__(self, master, api: SecureChatAPI, server: str):
        self.master = master
        self.api = api
        self.server = server
        self.enc = E2EEncryption()
        self.current_room: Optional[dict] = None
        self.current_ws: Optional[SecureChatWS] = None
        self.rooms: list = []
        self.users: list = []
        self._typing_timer = None
        self._e2e_enabled = False

        master.title(f"SecureChat — {api.user['username']}")
        master.geometry("1100x700")
        master.minsize(800, 500)
        master.configure(bg=DARK["bg"])
        center_window(master, 1100, 700)
        master.protocol("WM_DELETE_WINDOW", self._on_close)

        self._setup_encryption()
        self._build()
        self._load_rooms()
        self._load_users()

    def _setup_encryption(self):
        """Настроить E2E шифрование"""
        try:
            if os.path.exists(KEY_FILE):
                self.enc.load_private_key_file(KEY_FILE)
            else:
                self.enc.generate_keypair()
                self.enc.save_private_key(KEY_FILE)
            # Upload public key to server
            def upload():
                try:
                    self.api.upload_public_key(self.api.user["id"], self.enc.get_public_pem())
                    self._e2e_enabled = True
                except Exception as e:
                    print(f"E2E key upload failed: {e}")
            threading.Thread(target=upload, daemon=True).start()
        except Exception as e:
            print(f"E2E setup failed: {e}")

    def _build(self):
        # ── Root layout ──
        self.paned = tk.PanedWindow(self.master, orient="horizontal",
            bg=DARK["border"], bd=0, sashwidth=1, sashrelief="flat")
        self.paned.pack(fill="both", expand=True)

        # ── Left sidebar ──
        self.sidebar = tk.Frame(self.paned, bg=DARK["sidebar"], width=260)
        self.paned.add(self.sidebar, minsize=200, width=260)

        # Sidebar header
        header = tk.Frame(self.sidebar, bg=DARK["header"], height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="🔐 SecureChat", font=FONT_BOLD,
                 bg=DARK["header"], fg=DARK["text"]).pack(side="left", padx=14, pady=14)

        # New room button
        tk.Button(header, text="+", font=("Segoe UI", 16, "bold"),
            bg=DARK["header"], fg=DARK["accent2"], bd=0, cursor="hand2",
            command=self._new_room_dialog).pack(side="right", padx=10)

        # Search
        search_frame = tk.Frame(self.sidebar, bg=DARK["sidebar"], padx=8, pady=6)
        search_frame.pack(fill="x")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._filter_rooms)
        se = tk.Entry(search_frame, textvariable=self.search_var,
            font=FONT_MAIN, bg=DARK["input_bg"], fg=DARK["text"],
            insertbackground=DARK["text"], bd=0, relief="flat")
        se.pack(fill="x", ipady=6, padx=4)
        tk.Label(search_frame, text="🔍", font=FONT_SMALL,
                 bg=DARK["sidebar"], fg=DARK["text_muted"]).place(in_=se, relx=1.0, rely=0.5,
                 anchor="e", x=-6)

        # Tabs (Chats / Contacts)
        tabs = tk.Frame(self.sidebar, bg=DARK["sidebar"])
        tabs.pack(fill="x", padx=8, pady=(0, 4))
        self._tab_btns = {}
        for label, key in [("Чаты", "rooms"), ("Контакты", "users")]:
            b = tk.Button(tabs, text=label, font=FONT_SMALL,
                bg=DARK["accent"] if key == "rooms" else DARK["sidebar"],
                fg=DARK["text"] if key == "rooms" else DARK["text_dim"],
                bd=0, cursor="hand2", padx=10, pady=4,
                command=lambda k=key: self._switch_tab(k))
            b.pack(side="left")
            self._tab_btns[key] = b

        # Room/User list
        self.list_frame = tk.Frame(self.sidebar, bg=DARK["sidebar"])
        self.list_frame.pack(fill="both", expand=True)
        self._list_canvas = tk.Canvas(self.list_frame, bg=DARK["sidebar"],
            bd=0, highlightthickness=0)
        self._list_scroll = tk.Scrollbar(self.list_frame, orient="vertical",
            command=self._list_canvas.yview)
        self._list_canvas.configure(yscrollcommand=self._list_scroll.set)
        self._list_scroll.pack(side="right", fill="y")
        self._list_canvas.pack(fill="both", expand=True)
        self._list_inner = tk.Frame(self._list_canvas, bg=DARK["sidebar"])
        self._list_canvas_window = self._list_canvas.create_window(
            (0, 0), window=self._list_inner, anchor="nw")
        self._list_inner.bind("<Configure>", lambda e: self._list_canvas.configure(
            scrollregion=self._list_canvas.bbox("all")))
        self._list_canvas.bind("<Configure>", lambda e: self._list_canvas.itemconfig(
            self._list_canvas_window, width=e.width))
        self._list_canvas.bind_all("<MouseWheel>", lambda e: self._list_canvas.yview_scroll(
            int(-1 * (e.delta / 120)), "units"))

        # User info bar
        user_bar = tk.Frame(self.sidebar, bg=DARK["header"], height=48)
        user_bar.pack(fill="x", side="bottom")
        user_bar.pack_propagate(False)
        av = tk.Label(user_bar, text=self.api.user.get("avatar", "?"),
            font=FONT_BOLD, bg=DARK["accent"], fg="white", width=3, height=1)
        av.pack(side="left", padx=(8, 6), pady=8)
        name_frame = tk.Frame(user_bar, bg=DARK["header"])
        name_frame.pack(side="left", fill="y", pady=8)
        tk.Label(name_frame, text=self.api.user["username"], font=FONT_BOLD,
                 bg=DARK["header"], fg=DARK["text"]).pack(anchor="w")
        tk.Label(name_frame, text=self.api.user["email"], font=FONT_SMALL,
                 bg=DARK["header"], fg=DARK["text_dim"]).pack(anchor="w")

        self.e2e_label = tk.Label(user_bar, text="🔒" if self._e2e_enabled else "🔓",
            font=FONT_SMALL, bg=DARK["header"], fg=DARK["text_dim"],
            cursor="hand2")
        self.e2e_label.pack(side="right", padx=8)
        self.e2e_label.bind("<Button-1>", lambda e: self._toggle_e2e())

        # ── Right chat area ──
        self.chat_area = tk.Frame(self.paned, bg=DARK["chat_bg"])
        self.paned.add(self.chat_area, minsize=400)

        # Welcome screen
        self._show_welcome()
        self._current_tab = "rooms"

    def _show_welcome(self):
        for w in self.chat_area.winfo_children():
            w.destroy()
        frame = tk.Frame(self.chat_area, bg=DARK["chat_bg"])
        frame.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(frame, text="🔐", font=("Segoe UI Emoji", 64),
                 bg=DARK["chat_bg"]).pack()
        tk.Label(frame, text="SecureChat", font=("Segoe UI", 24, "bold"),
                 bg=DARK["chat_bg"], fg=DARK["text"]).pack()
        tk.Label(frame, text="Выберите чат или откройте новый",
                 font=FONT_MAIN, bg=DARK["chat_bg"], fg=DARK["text_dim"]).pack(pady=8)

    def _build_chat_ui(self, room: dict):
        """Создать интерфейс чата для комнаты"""
        for w in self.chat_area.winfo_children():
            w.destroy()

        # Chat header
        ch = tk.Frame(self.chat_area, bg=DARK["header"], height=56)
        ch.pack(fill="x")
        ch.pack_propagate(False)

        name_col = tk.Frame(ch, bg=DARK["header"])
        name_col.pack(side="left", padx=14, pady=8)
        icon = "💬" if room.get("type") == "dm" else "#"
        tk.Label(name_col, text=f"{icon} {room['name'].lstrip('# ')}",
                 font=FONT_BOLD, bg=DARK["header"], fg=DARK["text"]).pack(anchor="w")
        self.room_status_var = tk.StringVar(value=room.get("description", ""))
        tk.Label(name_col, textvariable=self.room_status_var, font=FONT_SMALL,
                 bg=DARK["header"], fg=DARK["text_dim"]).pack(anchor="w")

        # E2E toggle
        self.e2e_toggle_var = tk.BooleanVar(value=False)
        e2e_cb = tk.Checkbutton(ch, text="🔒 E2E", font=FONT_SMALL,
            bg=DARK["header"], fg=DARK["text_dim"],
            selectcolor=DARK["accent"], activebackground=DARK["header"],
            variable=self.e2e_toggle_var, cursor="hand2")
        e2e_cb.pack(side="right", padx=14)

        sep = tk.Frame(self.chat_area, bg=DARK["border"], height=1)
        sep.pack(fill="x")

        # Messages area
        msg_frame = tk.Frame(self.chat_area, bg=DARK["chat_bg"])
        msg_frame.pack(fill="both", expand=True)

        self.msg_canvas = tk.Canvas(msg_frame, bg=DARK["chat_bg"],
            bd=0, highlightthickness=0)
        msg_scroll = tk.Scrollbar(msg_frame, orient="vertical",
            command=self.msg_canvas.yview)
        self.msg_canvas.configure(yscrollcommand=msg_scroll.set)
        msg_scroll.pack(side="right", fill="y")
        self.msg_canvas.pack(fill="both", expand=True)

        self.msg_inner = tk.Frame(self.msg_canvas, bg=DARK["chat_bg"])
        self.msg_canvas_win = self.msg_canvas.create_window(
            (0, 0), window=self.msg_inner, anchor="nw")
        self.msg_inner.bind("<Configure>", lambda e: self.msg_canvas.configure(
            scrollregion=self.msg_canvas.bbox("all")))
        self.msg_canvas.bind("<Configure>", lambda e: (
            self.msg_canvas.itemconfig(self.msg_canvas_win, width=e.width),
            self.msg_canvas.configure(scrollregion=self.msg_canvas.bbox("all"))
        ))
        self.msg_canvas.bind("<MouseWheel>", lambda e: self.msg_canvas.yview_scroll(
            int(-1 * (e.delta / 120)), "units"))

        # Typing indicator
        self.typing_var = tk.StringVar()
        tk.Label(self.chat_area, textvariable=self.typing_var, font=FONT_SMALL,
                 bg=DARK["chat_bg"], fg=DARK["text_dim"], anchor="w").pack(
                 fill="x", padx=16, pady=(2, 0))

        # Input area
        input_frame = tk.Frame(self.chat_area, bg=DARK["input_bg"], pady=8, padx=8)
        input_frame.pack(fill="x", side="bottom")

        self.input_text = tk.Text(input_frame, font=FONT_MAIN,
            bg=DARK["input_bg"], fg=DARK["text"],
            insertbackground=DARK["text"], bd=0, relief="flat",
            height=2, wrap="word")
        self.input_text.pack(side="left", fill="both", expand=True, padx=8)
        self.input_text.bind("<Return>", self._on_return)
        self.input_text.bind("<Shift-Return>", lambda e: None)
        self.input_text.bind("<KeyRelease>", self._on_typing)
        self.input_text.focus_set()

        send_btn = tk.Button(input_frame, text="▶", font=("Segoe UI", 14),
            bg=DARK["accent2"], fg="white", bd=0, cursor="hand2",
            padx=10, pady=4, command=self._send_message)
        send_btn.pack(side="right", padx=(4, 0))

    # ── Rooms ──────────────────────────────────────────────────────────────
    def _load_rooms(self):
        def task():
            try:
                rooms = self.api.get_rooms()
                self.rooms = rooms
                self.master.after(0, self._render_room_list)
            except Exception as e:
                print(f"Load rooms error: {e}")
        threading.Thread(target=task, daemon=True).start()

    def _load_users(self):
        def task():
            try:
                self.users = self.api.get_users()
            except Exception:
                pass
        threading.Thread(target=task, daemon=True).start()

    def _render_room_list(self):
        if self._current_tab != "rooms":
            return
        for w in self._list_inner.winfo_children():
            w.destroy()
        query = self.search_var.get().lower()
        for room in self.rooms:
            if query and query not in room["name"].lower():
                continue
            self._add_room_row(room)

    def _add_room_row(self, room: dict):
        is_active = self.current_room and self.current_room["id"] == room["id"]
        row = tk.Frame(self._list_inner,
            bg=DARK["accent"] if is_active else DARK["sidebar"],
            cursor="hand2")
        row.pack(fill="x")
        row.bind("<Button-1>", lambda e, r=room: self._open_room(r))

        icon = "💬" if room.get("type") == "dm" else "#"
        av = tk.Label(row, text=icon, font=("Segoe UI", 16),
            bg=row["bg"], fg=DARK["accent2"], width=3)
        av.pack(side="left", padx=(8, 4), pady=8)
        av.bind("<Button-1>", lambda e, r=room: self._open_room(r))

        info = tk.Frame(row, bg=row["bg"])
        info.pack(side="left", fill="both", expand=True, pady=8)
        info.bind("<Button-1>", lambda e, r=room: self._open_room(r))

        name = room["name"].lstrip("# ")
        tk.Label(info, text=name, font=FONT_BOLD,
                 bg=row["bg"], fg=DARK["text"], anchor="w").pack(fill="x")
        desc = room.get("description", "")
        if room.get("type") == "dm":
            desc = "Личное сообщение"
        if desc:
            tk.Label(info, text=desc[:40], font=FONT_SMALL,
                     bg=row["bg"], fg=DARK["text_dim"], anchor="w").pack(fill="x")

        sep = tk.Frame(self._list_inner, bg=DARK["border"], height=1)
        sep.pack(fill="x")

    def _render_user_list(self):
        for w in self._list_inner.winfo_children():
            w.destroy()
        query = self.search_var.get().lower()
        for user in self.users:
            if query and query not in user["username"].lower():
                continue
            self._add_user_row(user)

    def _add_user_row(self, user: dict):
        row = tk.Frame(self._list_inner, bg=DARK["sidebar"], cursor="hand2")
        row.pack(fill="x")
        row.bind("<Button-1>", lambda e, u=user: self._open_dm(u))

        av = tk.Label(row, text=user.get("avatar", user["username"][0].upper()),
            font=FONT_BOLD, bg=DARK["accent"], fg="white", width=3)
        av.pack(side="left", padx=(8, 6), pady=8)
        av.bind("<Button-1>", lambda e, u=user: self._open_dm(u))

        info = tk.Frame(row, bg=DARK["sidebar"])
        info.pack(side="left", fill="both", expand=True, pady=8)
        info.bind("<Button-1>", lambda e, u=user: self._open_dm(u))

        tk.Label(info, text=user["username"], font=FONT_BOLD,
                 bg=DARK["sidebar"], fg=DARK["text"]).pack(anchor="w")

        status = user.get("status", "offline")
        status_color = DARK["online"] if status == "online" else DARK["offline"]
        tk.Label(info, text=f"● {status}", font=FONT_SMALL,
                 bg=DARK["sidebar"], fg=status_color).pack(anchor="w")

        tk.Frame(self._list_inner, bg=DARK["border"], height=1).pack(fill="x")

    def _switch_tab(self, tab: str):
        self._current_tab = tab
        for k, b in self._tab_btns.items():
            if k == tab:
                b.configure(bg=DARK["accent"], fg=DARK["text"])
            else:
                b.configure(bg=DARK["sidebar"], fg=DARK["text_dim"])

        for w in self._list_inner.winfo_children():
            w.destroy()

        if tab == "rooms":
            self._render_room_list()
        else:
            self._load_users()
            self.master.after(500, self._render_user_list)

    def _filter_rooms(self, *args):
        if self._current_tab == "rooms":
            self._render_room_list()
        else:
            self._render_user_list()

    # ── Open room ─────────────────────────────────────────────────────────
    def _open_room(self, room: dict):
        if self.current_room and self.current_room["id"] == room["id"]:
            return
        # Disconnect old WS
        if self.current_ws:
            self.current_ws.disconnect()
            self.current_ws = None

        self.current_room = room
        self._render_room_list()
        self._build_chat_ui(room)
        self._load_messages(room["id"])
        self._connect_ws(room["id"])

    def _open_dm(self, user: dict):
        def task():
            try:
                dm = self.api.open_dm(user["id"])
                room = {
                    "id": dm["room_id"],
                    "name": dm["name"],
                    "type": "dm",
                    "description": "Личное сообщение",
                }
                # Add to rooms list if not already
                if not any(r["id"] == room["id"] for r in self.rooms):
                    self.rooms.insert(0, room)
                self.master.after(0, lambda: self._open_room(room))
                self.master.after(0, self._render_room_list)
            except Exception as e:
                self.master.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
        threading.Thread(target=task, daemon=True).start()

    def _load_messages(self, room_id: str):
        def task():
            try:
                msgs = self.api.get_messages(room_id)
                self.master.after(0, lambda: self._render_messages(msgs))
            except Exception as e:
                print(f"Load messages error: {e}")
        threading.Thread(target=task, daemon=True).start()

    def _render_messages(self, msgs: list):
        if not hasattr(self, "msg_inner"):
            return
        for w in self.msg_inner.winfo_children():
            w.destroy()

        prev_user = None
        for msg in msgs:
            self._add_message_widget(msg, show_avatar=msg.get("user_id") != prev_user)
            prev_user = msg.get("user_id")

        self.master.after(100, self._scroll_bottom)

    def _add_message_widget(self, msg: dict, show_avatar=True):
        if not hasattr(self, "msg_inner"):
            return

        is_mine = msg.get("user_id") == self.api.user["id"]
        content = msg.get("content", "")

        # Try decrypt if encrypted
        if msg.get("encrypted") and self._e2e_enabled:
            try:
                content = self.enc.decrypt_message(content)
                content = f"🔒 {content}"
            except Exception:
                content = "🔒 [Зашифровано — нет ключа]"

        ts = msg.get("timestamp", 0)
        time_str = time.strftime("%H:%M", time.localtime(ts)) if ts else ""

        row = tk.Frame(self.msg_inner, bg=DARK["chat_bg"])
        row.pack(fill="x", padx=12, pady=(2 if not show_avatar else 6, 2))

        if is_mine:
            bubble_frame = tk.Frame(row, bg=DARK["chat_bg"])
            bubble_frame.pack(side="right")
            bubble = tk.Frame(bubble_frame, bg=DARK["my_bubble"], padx=10, pady=6)
            bubble.pack(anchor="e")
            tk.Label(bubble, text=content, font=FONT_MAIN,
                     bg=DARK["my_bubble"], fg=DARK["text"],
                     wraplength=400, justify="left", anchor="w").pack(anchor="w")
            tk.Label(bubble_frame, text=time_str, font=("Segoe UI", 8),
                     bg=DARK["chat_bg"], fg=DARK["text_muted"]).pack(anchor="e")
        else:
            if show_avatar:
                av_text = msg.get("avatar", msg.get("username", "?")[0].upper())
                av = tk.Label(row, text=av_text, font=FONT_SMALL,
                    bg=DARK["accent"], fg="white", width=3,
                    relief="flat")
                av.pack(side="left", anchor="n", pady=(2, 0))
            else:
                tk.Label(row, text="", width=3, bg=DARK["chat_bg"]).pack(side="left")

            bubble_frame = tk.Frame(row, bg=DARK["chat_bg"])
            bubble_frame.pack(side="left", padx=6, fill="x", expand=True)

            if show_avatar:
                name_row = tk.Frame(bubble_frame, bg=DARK["chat_bg"])
                name_row.pack(anchor="w")
                tk.Label(name_row, text=msg.get("username", ""),
                    font=FONT_BOLD, bg=DARK["chat_bg"],
                    fg=DARK["accent2"]).pack(side="left")
                tk.Label(name_row, text=f"  {time_str}",
                    font=("Segoe UI", 8), bg=DARK["chat_bg"],
                    fg=DARK["text_muted"]).pack(side="left")

            bubble = tk.Frame(bubble_frame, bg=DARK["their_bubble"], padx=10, pady=6)
            bubble.pack(anchor="w")
            tk.Label(bubble, text=content, font=FONT_MAIN,
                     bg=DARK["their_bubble"], fg=DARK["text"],
                     wraplength=400, justify="left", anchor="w").pack(anchor="w")

    def _scroll_bottom(self):
        if hasattr(self, "msg_canvas"):
            self.msg_canvas.yview_moveto(1.0)

    # ── WebSocket ──────────────────────────────────────────────────────────
    def _connect_ws(self, room_id: str):
        ws = SecureChatWS(
            base_url=self.server,
            token=self.api.token,
            room_id=room_id,
            on_message=self._on_ws_message,
            on_error=lambda e: print(f"WS: {e}"),
            on_close=lambda: self._update_status("Отключено"),
        )
        self.current_ws = ws
        ws.connect()
        self._update_status("Подключено ✓")

    def _on_ws_message(self, data: dict):
        msg_type = data.get("type")
        if msg_type == "message":
            self.master.after(0, lambda: self._add_message_widget(data, show_avatar=True))
            self.master.after(50, self._scroll_bottom)
        elif msg_type == "typing":
            uname = data.get("username", "")
            self.master.after(0, lambda: self.typing_var.set(f"{uname} печатает..."))
            if self._typing_timer:
                self.master.after_cancel(self._typing_timer)
            self._typing_timer = self.master.after(3000, lambda: self.typing_var.set(""))
        elif msg_type == "presence":
            uname = data.get("username", "")
            status = data.get("status", "")
            icon = "🟢" if status == "online" else "⚫"
            self.master.after(0, lambda: self._update_status(f"{icon} {uname} {status}"))

    def _update_status(self, text: str):
        if hasattr(self, "room_status_var"):
            self.room_status_var.set(text)

    # ── Send ───────────────────────────────────────────────────────────────
    def _on_return(self, event):
        if not event.state & 0x1:  # No Shift
            self._send_message()
            return "break"

    def _on_typing(self, event):
        if self.current_ws:
            self.current_ws.send_typing()

    def _send_message(self):
        if not hasattr(self, "input_text"):
            return
        content = self.input_text.get("1.0", "end-1c").strip()
        if not content or not self.current_ws:
            return

        encrypted = False
        if self.e2e_toggle_var.get() and self._e2e_enabled and self.current_room:
            if self.current_room.get("type") == "dm":
                # Get recipient's public key
                members = [m for m in self.current_room.get("members", [])
                           if m != self.api.user["id"]]
                if members:
                    def encrypt_and_send(content=content):
                        try:
                            pub_key = self.api.get_public_key(members[0])
                            encrypted_content = self.enc.encrypt_message(content, pub_key)
                            self.current_ws.send_message(encrypted_content, encrypted=True)
                        except Exception as e:
                            self.current_ws.send_message(content, encrypted=False)
                    threading.Thread(target=encrypt_and_send, daemon=True).start()
                    self.input_text.delete("1.0", "end")
                    return

        self.current_ws.send_message(content, encrypted=encrypted)
        self.input_text.delete("1.0", "end")

    # ── Dialogs ────────────────────────────────────────────────────────────
    def _new_room_dialog(self):
        name = simpledialog.askstring("Новый канал", "Название канала:",
            parent=self.master)
        if not name:
            return
        desc = simpledialog.askstring("Описание", "Описание (необязательно):",
            parent=self.master) or ""

        def task():
            try:
                room = self.api.create_room(name, desc)
                self.rooms.insert(0, room)
                self.master.after(0, self._render_room_list)
                self.master.after(0, lambda: self._open_room(room))
            except APIError as e:
                self.master.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
        threading.Thread(target=task, daemon=True).start()

    def _toggle_e2e(self):
        self._e2e_enabled = not self._e2e_enabled
        icon = "🔒" if self._e2e_enabled else "🔓"
        self.e2e_label.configure(text=icon)

    def _on_close(self):
        if self.current_ws:
            self.current_ws.disconnect()
        self.master.destroy()


# ════════════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════════════
def styled_entry(parent, var, show=None) -> tk.Entry:
    kwargs = dict(textvariable=var, font=FONT_MAIN,
        bg=DARK["input_bg"], fg=DARK["text"],
        insertbackground=DARK["text"], bd=0, relief="flat")
    if show:
        kwargs["show"] = show
    e = tk.Entry(parent, **kwargs)
    e.pack(fill="x", ipady=8, pady=(0, 4))
    return e

def center_window(win, w, h):
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")


# ════════════════════════════════════════════════════════════════════════════
#  Entry Point
# ════════════════════════════════════════════════════════════════════════════
def main():
    root = tk.Tk()
    root.configure(bg=DARK["bg"])

    # Try to remember last server
    last_server = DEFAULT_SERVER
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
                last_server = cfg.get("server", DEFAULT_SERVER)
    except Exception:
        pass

    def on_auth_success(api, server):
        # Save config
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump({"server": server}, f)
        except Exception:
            pass
        # Clear window and open chat
        for w in root.winfo_children():
            w.destroy()
        root.geometry("1100x700")
        root.resizable(True, True)
        ChatWindow(root, api, server)

    auth = AuthWindow(root, on_auth_success)
    root.mainloop()


if __name__ == "__main__":
    main()
