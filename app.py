
import tkinter as tk
from tkinter import ttk
import ctypes
import os
import psutil
import sys
import threading
import time
import socket
from datetime import datetime


# Windows DPI awareness for sharper rendering
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


BG = "#101010"
PANEL = "#181818"
PANEL2 = "#202020"
BORDER = "#303030"
TEXT = "#ffffff"
MUTED = "#999999"


class NetworkMonitor:
    def __init__(self, root):
        self.root = root
        if getattr(sys, "frozen", False):
            icon_path = os.path.join(sys._MEIPASS, "icon.ico")
        else:
            icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        self.root.iconbitmap(icon_path)
        self.root.title("Network Monitor")
        self.root.geometry("1050x680")
        self.root.minsize(850, 520)
        self.root.configure(bg=BG)

        self.running = False
        self.selected_pids = set()
        self.filter_active = False
        self.all_items = []
        self.lock = threading.Lock()
        self.processes = {}
        self.app_entries = []

        self.setup_style()
        self.build_ui()
        self.refresh_apps()

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Treeview",
            background=PANEL,
            foreground=TEXT,
            fieldbackground=PANEL,
            bordercolor=BORDER,
            borderwidth=1,
            rowheight=28,
            font=("Segoe UI", 10)
        )

        style.configure(
            "Treeview.Heading",
            background=PANEL2,
            foreground=TEXT,
            bordercolor=BORDER,
            relief="flat",
            font=("Segoe UI", 9, "bold")
        )

        style.map(
            "Treeview",
            background=[("selected", "#29476b")],
            foreground=[("selected", TEXT)]
        )

        style.configure(
            "Vertical.TScrollbar",
            background=PANEL2,
            troughcolor=BG,
            bordercolor=BG,
            arrowcolor=TEXT
        )

        style.configure(
            "Horizontal.TScrollbar",
            background=PANEL2,
            troughcolor=BG,
            bordercolor=BG,
            arrowcolor=TEXT
        )

    def build_ui(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=16, pady=(15, 9))

        tk.Label(
            header,
            text="Network Monitor",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 18, "bold")
        ).pack(side="left")

        self.status = tk.Label(
            header,
            text="● Stopped",
            bg=BG,
            fg="#e06c6c",
            font=("Segoe UI", 10)
        )
        self.status.pack(side="right")

        controls = tk.Frame(self.root, bg=BG)
        controls.pack(fill="x", padx=16, pady=5)

        self.start_button = self.make_button(
            controls,
            "Start monitoring",
            self.start_monitoring,
            bold=True
        )
        self.start_button.pack(side="left")

        self.stop_button = self.make_button(
            controls,
            "Stop",
            self.stop_monitoring
        )
        self.stop_button.pack(side="left", padx=7)
        self.stop_button.configure(state="disabled")

        self.make_button(
            controls,
            "Clear",
            self.clear_feed
        ).pack(side="left")

        self.only_selected = tk.BooleanVar(value=False)

        tk.Checkbutton(
            controls,
            text="Only monitor selected apps",
            variable=self.only_selected,
            command=self.update_filter,
            bg=BG,
            fg=TEXT,
            selectcolor=PANEL,
            activebackground=BG,
            activeforeground=TEXT,
            font=("Segoe UI", 9)
        ).pack(side="right")

        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=16, pady=10)

        # Application sidebar
        left = tk.Frame(
            main,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
            width=245
        )
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        tk.Label(
            left,
            text="RUNNING APPLICATIONS",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", padx=11, pady=(13, 8))

        app_buttons = tk.Frame(left, bg=PANEL)
        app_buttons.pack(fill="x", padx=9, pady=(0, 8))

        self.make_button(
            app_buttons,
            "Select all",
            self.select_all,
            small=True
        ).pack(side="left", fill="x", expand=True)

        self.make_button(
            app_buttons,
            "Unselect all",
            self.unselect_all,
            small=True
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

        app_frame = tk.Frame(left, bg=PANEL)
        app_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.app_list = tk.Listbox(
            app_frame,
            bg=PANEL,
            fg=TEXT,
            selectbackground="#29476b",
            selectforeground=TEXT,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            font=("Segoe UI", 9),
            activestyle="none",
            selectmode="multiple"
        )
        self.app_list.pack(side="left", fill="both", expand=True)

        app_scroll = ttk.Scrollbar(
            app_frame,
            orient="vertical",
            command=self.app_list.yview
        )
        app_scroll.pack(side="right", fill="y")
        self.app_list.configure(yscrollcommand=app_scroll.set)

        self.app_list.bind(
            "<<ListboxSelect>>",
            self.update_selection
        )

        self.make_button(
            left,
            "Refresh applications",
            self.refresh_apps,
            small=True
        ).pack(fill="x", padx=9, pady=(0, 10))

        # Connection panel
        right = tk.Frame(
            main,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        right.pack(side="left", fill="both", expand=True)

        top = tk.Frame(right, bg=PANEL)
        top.pack(fill="x", padx=11, pady=11)

        tk.Label(
            top,
            text="LIVE CONNECTIONS",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 9, "bold")
        ).pack(side="left")

        self.connection_count = tk.Label(
            top,
            text="0 connections",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 9)
        )
        self.connection_count.pack(side="right")

        search_frame = tk.Frame(right, bg=PANEL)
        search_frame.pack(fill="x", padx=11, pady=(0, 9))

        tk.Label(
            search_frame,
            text="Search",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(0, 8))

        self.search_var = tk.StringVar()

        search = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            bg=PANEL2,
            fg=TEXT,
            insertbackground=TEXT,
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            font=("Segoe UI", 10)
        )
        search.pack(side="left", fill="x", expand=True)

        self.search_var.trace_add(
            "write",
            self.search_connections
        )

        columns = (
            "time",
            "application",
            "pid",
            "remote",
            "port",
            "protocol",
            "security",
            "state"
        )

        table_frame = tk.Frame(right, bg=PANEL)
        table_frame.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        self.table = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings"
        )

        headings = {
            "time": ("TIME", 80),
            "application": ("APPLICATION", 145),
            "pid": ("PID", 60),
            "remote": ("REMOTE IP", 140),
            "port": ("PORT", 65),
            "protocol": ("PROTOCOL", 80),
            "security": ("SECURITY", 125),
            "state": ("STATE", 105)
        }

        for column, (heading, width) in headings.items():
            self.table.heading(column, text=heading)
            self.table.column(
                column,
                width=width,
                minwidth=45
            )

        y_scroll = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.table.yview
        )

        x_scroll = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.table.xview
        )

        self.table.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set
        )

        self.table.pack(side="top", fill="both", expand=True)
        y_scroll.pack(side="right", fill="y")
        x_scroll.pack(side="bottom", fill="x")

        tk.Label(
            self.root,
            text="Connection metadata only · HTTPS contents are not inspected",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 8)
        ).pack(anchor="w", padx=18, pady=(0, 10))

    def make_button(self, parent, text, command, bold=False, small=False):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=PANEL2,
            fg="#ffffff",
            activebackground="#303030",
            activeforeground="#ffffff",
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            padx=10 if small else 15,
            pady=5 if small else 8,
            font=(
                "Segoe UI",
                8 if small else 9,
                "bold" if bold else "normal"
            ),
            cursor="hand2"
        )

    def refresh_apps(self):
        with self.lock:
            old_selection = set(self.selected_pids)

        self.processes = {}

        for process in psutil.process_iter(["pid", "name"]):
            try:
                pid = process.info["pid"]
                name = process.info["name"] or "Unknown"
                self.processes[pid] = name
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        self.app_entries = sorted(
            self.processes.items(),
            key=lambda item: item[1].lower()
        )

        self.app_list.delete(0, tk.END)

        for index, (pid, name) in enumerate(self.app_entries):
            self.app_list.insert(
                tk.END,
                f"{name}  (PID {pid})"
            )

            if pid in old_selection:
                self.app_list.selection_set(index)

        self.update_selection()

    def select_all(self):
        self.app_list.selection_set(0, tk.END)
        self.update_selection()

    def unselect_all(self):
        self.app_list.selection_clear(0, tk.END)
        self.update_selection()

    def update_selection(self, event=None):
        selected = self.app_list.curselection()

        pids = {
            self.app_entries[index][0]
            for index in selected
            if index < len(self.app_entries)
        }

        with self.lock:
            self.selected_pids = pids

    def update_filter(self):
        with self.lock:
            self.filter_active = self.only_selected.get()

    def start_monitoring(self):
        if self.running:
            return

        self.update_selection()
        self.update_filter()

        self.running = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.configure(
            text="● Monitoring",
            fg="#69c78a"
        )

        self.worker = threading.Thread(
            target=self.monitor_loop,
            daemon=True
        )
        self.worker.start()

    def stop_monitoring(self):
        self.running = False
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status.configure(
            text="● Stopped",
            fg="#e06c6c"
        )

    def monitor_loop(self):
        previous = set()

        while self.running:
            try:
                connections = psutil.net_connections(
                    kind="inet"
                )

                with self.lock:
                    selected = set(self.selected_pids)
                    filter_active = self.filter_active

                for connection in connections:
                    if not self.running:
                        break

                    if not connection.raddr:
                        continue

                    pid = connection.pid

                    if pid is None:
                        continue

                    if filter_active and pid not in selected:
                        continue

                    try:
                        app_name = psutil.Process(pid).name()
                    except (
                        psutil.NoSuchProcess,
                        psutil.AccessDenied
                    ):
                        app_name = "Unknown"

                    remote_ip = connection.raddr.ip
                    remote_port = connection.raddr.port

                    if connection.type == socket.SOCK_DGRAM:
                        protocol = "UDP"
                    else:
                        protocol = "TCP"

                    if remote_port in (443, 8443):
                        security = "Likely encrypted"
                    else:
                        security = "Unknown"

                    state = connection.status or "ACTIVE"

                    key = (
                        pid,
                        remote_ip,
                        remote_port,
                        protocol,
                        state
                    )

                    if key not in previous:
                        timestamp = datetime.now().strftime(
                            "%H:%M:%S"
                        )

                        self.root.after(
                            0,
                            self.add_connection,
                            timestamp,
                            app_name,
                            pid,
                            remote_ip,
                            remote_port,
                            protocol,
                            security,
                            state
                        )

                    previous.add(key)

                previous = {
                    (
                        c.pid,
                        c.raddr.ip,
                        c.raddr.port,
                        "UDP" if c.type == socket.SOCK_DGRAM else "TCP",
                        c.status or "ACTIVE"
                    )
                    for c in connections
                    if c.raddr
                    and c.pid is not None
                    and (not filter_active or c.pid in selected)
                }

            except psutil.AccessDenied:
                self.root.after(
                    0,
                    self.set_status_message,
                    "Access denied - try Administrator"
                )
            except Exception:
                pass

            time.sleep(1)

    def set_status_message(self, message):
        self.status.configure(
            text=message,
            fg="#e0ad62"
        )

    def add_connection(
        self,
        timestamp,
        app,
        pid,
        remote,
        port,
        protocol,
        security,
        state
    ):
        if not self.root.winfo_exists():
            return

        values = (
            timestamp,
            app,
            pid,
            remote,
            port,
            protocol,
            security,
            state
        )

        item = self.table.insert(
            "",
            "end",
            values=values
        )

        self.all_items.append(item)

        if len(self.all_items) > 1500:
            oldest = self.all_items.pop(0)

            try:
                self.table.delete(oldest)
            except tk.TclError:
                pass

        self.connection_count.configure(
            text=f"{len(self.all_items)} connections"
        )

        self.apply_search()

        children = self.table.get_children()
        if children:
            self.table.see(children[-1])

    def search_connections(self, *args):
        self.apply_search()

    def apply_search(self):
        query = self.search_var.get().lower().strip()

        for item in self.all_items:
            try:
                values = self.table.item(item, "values")
            except tk.TclError:
                continue

            content = " ".join(
                str(value) for value in values
            ).lower()

            if query in content:
                self.table.reattach(item, "", "end")
            else:
                self.table.detach(item)

    def clear_feed(self):
        self.table.delete(*self.table.get_children())
        self.all_items.clear()

        self.connection_count.configure(
            text="0 connections"
        )

    def close(self):
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = NetworkMonitor(root)
    root.mainloop()
