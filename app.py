"""Saints Critical Text Studio — Native Offline-First Windows Desktop Application (Tk 9.0).

Run directly with zero internet required:
    python app.py
or double-click `Launch-Saints-Critical-Text-Studio.vbs` (windowless native desktop launch).
"""

from __future__ import annotations
import ctypes
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

from studio.brains.base import BrainConfig
from studio.catalog import (
    BOOKS_BY_SLUG,
    CRITICAL_OUTPUT_ROOTS,
    DIVISIONS,
    BookSpec,
    chapters_for_language,
    get_books_for_language,
)
from studio.engine import CriticalTextEngine

# Enable crisp Per-Monitor HiDPI rendering on Windows 10/11
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

LANG_OPTIONS = [
    ("greek", "1 · Greek (Priority 1 — 70 Books: LXX + NT)"),
    ("hebrew", "2 · Hebrew (Priority 2 — Masoretic & Ancient OT)"),
    ("latin", "3 · Latin (Priority 3 — Early Pandects & Vulgate)"),
]

BRAIN_OPTIONS = [
    ("offline_philological", "Offline Philological Brain (Zero Internet)"),
    ("textual_analysis", "Textual Analysis Brain (internal evidence · offline; optional Claude review)"),
    ("openai_review", "OpenAI Review Brain (advisory · requires unlock)"),
    ("local_ollama", "Local Offline LLM (Ollama / llama.cpp · 127.0.0.1)"),
    ("cloud_gemini", "Cloud Gemini 4 + Decision-1 (Requires Unlock)"),
]


class CriticalTextDesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Saints Critical Text Studio — Offline-First Open-Source Edition")
        self.root.geometry("1480x930")
        self.root.minsize(1140, 740)

        self.engine = CriticalTextEngine()
        self.ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()

        self.current_lang = tk.StringVar(value="greek")
        self.current_division = tk.StringVar(value="01_Law")
        self.current_book_slug = tk.StringVar(value="genesis")
        self.current_chapter = tk.IntVar(value=1)
        self.home_view_mode = tk.StringVar(value="scripture")
        self.show_translit_var = tk.BooleanVar(value=True)

        self.brain_var = tk.StringVar(value=self.engine.config.provider_id)
        self.offline_lock_var = tk.BooleanVar(value=self.engine.config.offline_locked)
        self.status_var = tk.StringVar(value="Ready · 100% Offline Self-Contained Studio Active")

        self.loaded_chapter_data: Optional[Dict[str, Any]] = None
        self.home_selected_chapter: Optional[Dict[str, Any]] = None
        self.home_selected_book_slug: str = "genesis"
        self.selected_verse_obj: Optional[Dict[str, Any]] = None
        self.books_in_div: List[BookSpec] = []

        # Tab 5 — The Saints Concordance state
        self.conc_search_var = tk.StringVar(value="")
        self.conc_lang_var = tk.StringVar(value="all")
        self.conc_colour_var = tk.StringVar(value="all")
        self.conc_atom_kind_var = tk.StringVar(value="roots")
        self.conc_selected_concept_id: Optional[int] = None
        self.conc_active_sense_id: Optional[int] = None
        self.conc_loaded_graph: Optional[Dict[str, Any]] = None
        self.conc_selected_occ: Optional[Dict[str, Any]] = None
        self._conc_occ_by_iid: Dict[str, Dict[str, Any]] = {}

        self._configure_styles()
        self._build_layout()
        self._refresh_divisions_and_books()
        self._refresh_witness_table()
        self._refresh_audit_log()
        self._refresh_library_home()
        self._refresh_concordance_tab(select_concept_id=1)
        self._load_or_collate_initial()
        self._poll_queue()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")

        self.font_ui = ("Segoe UI", 10)
        self.font_ui_bold = ("Segoe UI", 10, "bold")
        self.font_header = ("Segoe UI Semibold", 13)
        self.font_scripture = ("Palatino Linotype", 13)
        self.font_scripture_lg = ("Palatino Linotype", 14)
        self.font_mono = ("Consolas", 10)

        style.configure("Treeview", font=self.font_ui, rowheight=28)
        style.configure("Treeview.Heading", font=self.font_ui_bold)
        style.configure("TNotebook.Tab", font=("Segoe UI Semibold", 10), padding=(14, 7))
        style.configure("Accent.TButton", font=self.font_ui_bold, padding=(10, 5))
        style.configure("TButton", font=self.font_ui, padding=(8, 4))

    def _build_layout(self) -> None:
        # === Top Command Header ===
        hdr = tk.Frame(self.root, bg="#0F172A", padx=16, pady=10)
        hdr.pack(fill="x")

        title_box = tk.Frame(hdr, bg="#0F172A")
        title_box.pack(side="left")
        tk.Label(
            title_box,
            text="SAINTS CRITICAL TEXT STUDIO",
            fg="#F8FAFC",
            bg="#0F172A",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text="Self-Contained Trilingual Critical Edition Home, Collation Workbench, Witness Gatekeeper & Saints Concordance · 100% Offline",
            fg="#94A3B8",
            bg="#0F172A",
            font=("Segoe UI", 9),
        ).pack(anchor="w")

        ctrl_box = tk.Frame(hdr, bg="#0F172A")
        ctrl_box.pack(side="right")

        tk.Label(ctrl_box, text="Language Priority:", fg="#CBD5E1", bg="#0F172A", font=self.font_ui_bold).grid(
            row=0, column=0, padx=(0, 6)
        )
        self.lang_combo = ttk.Combobox(
            ctrl_box,
            state="readonly",
            width=36,
            font=self.font_ui,
            values=[lbl for _, lbl in LANG_OPTIONS],
        )
        self.lang_combo.current(0)
        self.lang_combo.grid(row=0, column=1, padx=(0, 14))
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_lang_changed)

        tk.Label(ctrl_box, text="AI Brain:", fg="#CBD5E1", bg="#0F172A", font=self.font_ui_bold).grid(
            row=0, column=2, padx=(0, 6)
        )
        self.brain_combo = ttk.Combobox(
            ctrl_box,
            state="readonly",
            width=38,
            font=self.font_ui,
            values=[lbl for _, lbl in BRAIN_OPTIONS],
        )
        brain_ids = [bid for bid, _ in BRAIN_OPTIONS]
        self.brain_combo.current(
            brain_ids.index(self.engine.config.provider_id) if self.engine.config.provider_id in brain_ids else 0
        )
        self.brain_combo.grid(row=0, column=3, padx=(0, 14))
        self.brain_combo.bind("<<ComboboxSelected>>", self._on_brain_quick_changed)

        self.lock_btn = tk.Checkbutton(
            ctrl_box,
            text="🔒 Strict Offline Lock",
            variable=self.offline_lock_var,
            command=self._on_offline_lock_toggled,
            fg="#86EFAC",
            bg="#1E293B",
            selectcolor="#0F172A",
            activebackground="#1E293B",
            activeforeground="#86EFAC",
            font=self.font_ui_bold,
            padx=10,
            pady=4,
            indicatoron=True,
        )
        self.lock_btn.grid(row=0, column=4)

        # === Main 5-Tab Notebook ===
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(8, 4))

        self.tab_home = ttk.Frame(self.notebook)
        self.tab_workbench = ttk.Frame(self.notebook)
        self.tab_gatekeeper = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        self.tab_concordance = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_home, text="  1 · Saints Critical Text Home (Library)  ")
        self.notebook.add(self.tab_workbench, text="  2 · Collation Workbench  ")
        self.notebook.add(self.tab_gatekeeper, text="  3 · Witness Gatekeeper (Add / Disregard Texts)  ")
        self.notebook.add(self.tab_settings, text="  4 · Audit Log & AI Brain Configuration  ")
        self.notebook.add(self.tab_concordance, text="  5 · Saints Concordance (Trilingual Root Graph)  ")

        self._build_home_tab()
        self._build_workbench_tab()
        self._build_gatekeeper_tab()
        self._build_settings_tab()
        self._build_concordance_tab()

        # === Bottom Status Bar ===
        status_bar = tk.Frame(self.root, bg="#E2E8F0", padx=12, pady=5)
        status_bar.pack(fill="x", side="bottom")
        tk.Label(status_bar, textvariable=self.status_var, bg="#E2E8F0", fg="#0F172A", font=self.font_ui).pack(
            side="left"
        )
        self.progress = ttk.Progressbar(status_bar, mode="indeterminate", length=180)
        self.progress.pack(side="right")

    # ------------------------------------------------------------------
    # TAB 1: SAINTS CRITICAL TEXT HOME (IN-STUDIO EDITION LIBRARY & READER)
    # ------------------------------------------------------------------
    def _build_home_tab(self) -> None:
        banner = tk.Frame(self.tab_home, bg="#1E293B", padx=14, pady=9)
        banner.pack(fill="x", padx=8, pady=(8, 6))

        self.home_summary_var = tk.StringVar(value="Saints Critical Text Library")
        self.home_path_var = tk.StringVar(value="")
        left_info = tk.Frame(banner, bg="#1E293B")
        left_info.pack(side="left", fill="x", expand=True)
        tk.Label(
            left_info,
            textvariable=self.home_summary_var,
            fg="#F8FAFC",
            bg="#1E293B",
            font=("Segoe UI Semibold", 11),
        ).pack(anchor="w")
        tk.Label(
            left_info,
            textvariable=self.home_path_var,
            fg="#93C5FD",
            bg="#1E293B",
            font=("Consolas", 9),
        ).pack(anchor="w")

        actions = ttk.Frame(self.tab_home, padding=(8, 2))
        actions.pack(fill="x")

        ttk.Label(actions, text="Reader View:", font=self.font_ui_bold).pack(side="left", padx=(0, 6))
        for mode_id, mode_lbl in [
            ("scripture", "📖 Clean Scripture Edition"),
            ("markdown", "📜 Full 4-Section Critical Edition (.md)"),
            ("tsv", "📊 Pipeline TSV (.tsv)"),
        ]:
            ttk.Radiobutton(
                actions,
                text=mode_lbl,
                value=mode_id,
                variable=self.home_view_mode,
                command=self._render_home_reader,
            ).pack(side="left", padx=(0, 12))

        ttk.Checkbutton(
            actions,
            text="Aa Transliteration (Greek/Hebrew)",
            variable=self.show_translit_var,
            command=self._on_translit_toggled,
        ).pack(side="left", padx=(4, 10))

        ttk.Button(
            actions,
            text="📂 Open Edition Home Folder",
            command=self._open_output_folder,
        ).pack(side="right", padx=(6, 0))
        ttk.Button(
            actions,
            text="⚡ Collate Next Chapter in Book",
            command=self._collate_next_from_home,
        ).pack(side="right", padx=(6, 0))
        ttk.Button(
            actions,
            text="✎ Open in Collation Workbench",
            style="Accent.TButton",
            command=self._jump_from_home_to_workbench,
        ).pack(side="right", padx=(6, 0))

        split = ttk.PanedWindow(self.tab_home, orient="horizontal")
        split.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        # Left: 7-Division -> 70-Book -> Saved Chapters Tree
        tree_frame = ttk.LabelFrame(split, text=" 7-Division Saints Canon & Saved Chapters ", padding=6)
        self.lib_tree = ttk.Treeview(
            tree_frame,
            columns=("progress", "details"),
            show="tree headings",
            selectmode="browse",
        )
        self.lib_tree.heading("#0", text="Division / Book / Saved Chapter")
        self.lib_tree.heading("progress", text="Saved")
        self.lib_tree.heading("details", text="Status / Apparatus")
        self.lib_tree.column("#0", width=265, anchor="w")
        self.lib_tree.column("progress", width=80, anchor="center", stretch=False)
        self.lib_tree.column("details", width=165, anchor="w")

        self.lib_tree.tag_configure("division", font=self.font_ui_bold, background="#F1F5F9")
        self.lib_tree.tag_configure("book_saved", background="#F0FDF4", font=self.font_ui_bold)
        self.lib_tree.tag_configure("book_empty", foreground="#64748B")
        self.lib_tree.tag_configure("chapter_row", background="#FFFBEB")

        lt_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.lib_tree.yview)
        self.lib_tree.configure(yscrollcommand=lt_scroll.set)
        self.lib_tree.pack(side="left", fill="both", expand=True)
        lt_scroll.pack(side="right", fill="y")
        self.lib_tree.bind("<<TreeviewSelect>>", self._on_library_node_selected)
        self.lib_tree.bind("<Double-1>", lambda _e: self._jump_from_home_to_workbench())
        split.add(tree_frame, weight=2)

        # Right: Full Saints Edition Reader
        reader_box = ttk.LabelFrame(split, text=" Saints Critical Text Reader (Permanent In-Studio Home) ", padding=6)
        self.home_reader_title = ttk.Label(reader_box, text="Select a Saved Chapter", font=self.font_header)
        self.home_reader_title.pack(anchor="w", pady=(0, 6))

        txt_wrap = ttk.Frame(reader_box)
        txt_wrap.pack(fill="both", expand=True)
        self.home_reader_text = tk.Text(
            txt_wrap,
            wrap="word",
            font=self.font_scripture_lg,
            bg="#FFFDF7",
            fg="#0F172A",
            padx=18,
            pady=14,
            relief="flat",
            state="disabled",
        )
        hr_scroll = ttk.Scrollbar(txt_wrap, orient="vertical", command=self.home_reader_text.yview)
        self.home_reader_text.configure(yscrollcommand=hr_scroll.set)
        self.home_reader_text.tag_configure("h1", font=("Segoe UI", 15, "bold"), foreground="#0F172A", spacing3=8)
        self.home_reader_text.tag_configure("h2", font=("Segoe UI Semibold", 12), foreground="#1E3A8A", spacing1=10, spacing3=4)
        self.home_reader_text.tag_configure("meta", font=("Segoe UI", 9), foreground="#475569", spacing3=8)
        self.home_reader_text.tag_configure("vnum", foreground="#B45309", font=("Segoe UI", 10, "bold"))
        self.home_reader_text.tag_configure("locked", background="#DCFCE7")
        self.home_reader_text.tag_configure("mono", font=self.font_mono)
        self.home_reader_text.tag_configure("rtl", justify="right")
        self.home_reader_text.tag_configure("ltr", justify="left")
        self.home_reader_text.tag_configure(
            "translit",
            font=("Segoe UI", 10, "italic"),
            foreground="#475569",
            lmargin1=24,
            lmargin2=24,
            spacing3=8,
        )
        self.home_reader_text.pack(side="left", fill="both", expand=True)
        hr_scroll.pack(side="right", fill="y")
        split.add(reader_box, weight=4)

    # ------------------------------------------------------------------
    # TAB 2: COLLATION WORKBENCH
    # ------------------------------------------------------------------
    def _build_workbench_tab(self) -> None:
        bar = ttk.Frame(self.tab_workbench, padding=(8, 8))
        bar.pack(fill="x")

        ttk.Label(bar, text="Division:", font=self.font_ui_bold).pack(side="left", padx=(0, 4))
        self.div_combo = ttk.Combobox(
            bar,
            state="readonly",
            width=26,
            font=self.font_ui,
            values=[d["label"] for d in DIVISIONS],
        )
        self.div_combo.current(0)
        self.div_combo.pack(side="left", padx=(0, 10))
        self.div_combo.bind("<<ComboboxSelected>>", self._on_division_changed)

        ttk.Label(bar, text="Book:", font=self.font_ui_bold).pack(side="left", padx=(0, 4))
        self.book_combo = ttk.Combobox(bar, state="readonly", width=24, font=self.font_ui)
        self.book_combo.pack(side="left", padx=(0, 10))
        self.book_combo.bind("<<ComboboxSelected>>", self._on_book_changed)

        ttk.Label(bar, text="Chapter:", font=self.font_ui_bold).pack(side="left", padx=(0, 4))
        self.ch_spin = ttk.Spinbox(
            bar, from_=1, to=151, width=6, textvariable=self.current_chapter, font=self.font_ui, command=self._on_chapter_selected
        )
        self.ch_spin.pack(side="left", padx=(0, 12))
        self.ch_spin.bind("<Return>", lambda _e: self._on_chapter_selected())

        ttk.Button(
            bar,
            text="⚡ Collate & Adjudicate Chapter",
            style="Accent.TButton",
            command=self._run_collate_current,
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            bar,
            text="📚 Batch Collate Book",
            command=self._run_batch_book,
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            bar,
            text="📂 Open Edition Home Folder",
            command=self._open_output_folder,
        ).pack(side="left", padx=(0, 8))

        ttk.Checkbutton(
            bar,
            text="Aa Transliteration",
            variable=self.show_translit_var,
            command=self._on_translit_toggled,
        ).pack(side="left", padx=(4, 8))

        ttk.Button(
            bar,
            text="☁ Sync Chapter to Google Drive",
            command=self._sync_current_to_drive,
        ).pack(side="right")

        # Main Horizontal Split: Left (Continuous Text + Verse Table) | Right (Verse Apparatus & Override Inspector)
        h_paned = ttk.PanedWindow(self.tab_workbench, orient="horizontal")
        h_paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        left_pane = ttk.PanedWindow(h_paned, orient="vertical")
        right_pane = ttk.Frame(h_paned, padding=(8, 0, 0, 0))
        h_paned.add(left_pane, weight=3)
        h_paned.add(right_pane, weight=2)

        # Left Top: Continuous Critical Text Reader
        reader_frame = ttk.LabelFrame(left_pane, text=" Continuous Reconstructed Saints Critical Text ", padding=6)
        self.continuous_text = tk.Text(
            reader_frame,
            height=9,
            wrap="word",
            font=self.font_scripture,
            bg="#FFFBEB",
            fg="#0F172A",
            padx=12,
            pady=8,
            relief="flat",
        )
        r_scroll = ttk.Scrollbar(reader_frame, orient="vertical", command=self.continuous_text.yview)
        self.continuous_text.configure(yscrollcommand=r_scroll.set)
        self.continuous_text.tag_configure("vnum", foreground="#B45309", font=("Segoe UI", 10, "bold"))
        self.continuous_text.tag_configure("contested", background="#FEF3C7")
        self.continuous_text.tag_configure("locked", background="#DCFCE7")
        self.continuous_text.tag_configure("rtl", justify="right")
        self.continuous_text.tag_configure("ltr", justify="left")
        self.continuous_text.tag_configure(
            "translit",
            font=("Segoe UI", 9, "italic"),
            foreground="#475569",
            lmargin1=18,
            lmargin2=18,
            spacing3=6,
        )
        self.continuous_text.pack(side="left", fill="both", expand=True)
        r_scroll.pack(side="right", fill="y")
        left_pane.add(reader_frame, weight=2)

        # Left Bottom: Verse-by-Verse Table
        table_frame = ttk.LabelFrame(left_pane, text=" Verse-by-Verse Collation Summary (Select a Verse to Inspect / Override) ", padding=6)
        cols = ("verse", "critical_text", "variants", "noise", "conf", "status")
        self.verse_tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        self.verse_tree.heading("verse", text="V.")
        self.verse_tree.heading("critical_text", text="Saints Critical Text Reading")
        self.verse_tree.heading("variants", text="Apparatus")
        self.verse_tree.heading("noise", text="Disregarded Noise")
        self.verse_tree.heading("conf", text="Confidence")
        self.verse_tree.heading("status", text="Decision Source")

        self.verse_tree.column("verse", width=48, anchor="center", stretch=False)
        self.verse_tree.column("critical_text", width=470, anchor="w")
        self.verse_tree.column("variants", width=95, anchor="center", stretch=False)
        self.verse_tree.column("noise", width=125, anchor="center", stretch=False)
        self.verse_tree.column("conf", width=85, anchor="center", stretch=False)
        self.verse_tree.column("status", width=170, anchor="w", stretch=False)

        self.verse_tree.tag_configure("has_variant", background="#FFF7ED")
        self.verse_tree.tag_configure("human_locked", background="#DCFCE7")

        vt_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.verse_tree.yview)
        self.verse_tree.configure(yscrollcommand=vt_scroll.set)
        self.verse_tree.pack(side="left", fill="both", expand=True)
        vt_scroll.pack(side="right", fill="y")
        self.verse_tree.bind("<<TreeviewSelect>>", self._on_verse_selected)
        left_pane.add(table_frame, weight=3)

        # Right Pane: Selected Verse Inspector
        self.inspector_hdr = ttk.Label(right_pane, text="Verse Inspector — Select a Verse", font=self.font_header)
        self.inspector_hdr.pack(anchor="w", pady=(0, 6))

        edit_frame = ttk.LabelFrame(right_pane, text=" Reconstructed Critical Text (Editable / Lockable) ", padding=6)
        edit_frame.pack(fill="x", pady=(0, 8))
        self.verse_edit_text = tk.Text(edit_frame, height=3, wrap="word", font=self.font_scripture, padx=6, pady=4)
        self.verse_edit_text.pack(fill="x", pady=(0, 4))

        ttk.Label(
            edit_frame,
            text="Latinized Pronunciation (English-Friendly Transliteration):",
            font=("Segoe UI", 8, "bold"),
            foreground="#475569",
        ).pack(anchor="w")
        self.verse_translit_text = tk.Text(
            edit_frame,
            height=2,
            wrap="word",
            font=("Segoe UI", 10, "italic"),
            bg="#F8FAFC",
            fg="#334155",
            padx=6,
            pady=3,
            relief="flat",
            state="disabled",
        )
        self.verse_translit_text.pack(fill="x", pady=(2, 6))

        btn_row = ttk.Frame(edit_frame)
        btn_row.pack(fill="x")
        ttk.Button(
            btn_row,
            text="✓ Save & Lock Human Reading",
            style="Accent.TButton",
            command=self._save_human_verse_override,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            btn_row,
            text="↺ Unlock Verse",
            command=self._unlock_human_verse,
        ).pack(side="left")
        ttk.Button(
            btn_row,
            text="🔗 Inspect in Concordance",
            command=self._jump_from_workbench_to_concordance,
        ).pack(side="right")

        # Sub-notebook inside right inspector: Apparatus | Witnesses & Disregarded Noise | Rationale
        insp_nb = ttk.Notebook(right_pane)
        insp_nb.pack(fill="both", expand=True)

        # Subtab A: Substantive Apparatus + One-Click Adopt
        tab_app = ttk.Frame(insp_nb, padding=6)
        insp_nb.add(tab_app, text=" Critical Apparatus ")
        self.app_listbox = tk.Listbox(tab_app, font=self.font_scripture, height=7, activestyle="dotbox")
        self.app_listbox.pack(fill="both", expand=True, pady=(0, 6))
        ttk.Button(
            tab_app,
            text="⇄ Replace Lemma in Critical Text with Selected Variant",
            command=self._adopt_selected_variant,
        ).pack(fill="x")

        # Subtab B: All Admitted Witnesses & Disregarded Surface Noise
        tab_wit = ttk.Frame(insp_nb, padding=6)
        insp_nb.add(tab_wit, text=" Witness Matrix & Disregarded Noise ")
        self.witness_matrix_text = tk.Text(
            tab_wit, wrap="word", font=self.font_ui, bg="#F8FAFC", padx=8, pady=6, state="disabled"
        )
        wm_scroll = ttk.Scrollbar(tab_wit, orient="vertical", command=self.witness_matrix_text.yview)
        self.witness_matrix_text.configure(yscrollcommand=wm_scroll.set)
        self.witness_matrix_text.tag_configure("sig", font=self.font_ui_bold, foreground="#1E3A8A")
        self.witness_matrix_text.tag_configure("grk", font=self.font_scripture)
        self.witness_matrix_text.tag_configure("tr", font=("Segoe UI", 9, "italic"), foreground="#475569", lmargin1=16, lmargin2=16)
        self.witness_matrix_text.tag_configure("noise_hdr", font=self.font_ui_bold, foreground="#B91C1C")
        self.witness_matrix_text.pack(side="left", fill="both", expand=True)
        wm_scroll.pack(side="right", fill="y")

        # Subtab C: Philological Rationale
        tab_rat = ttk.Frame(insp_nb, padding=6)
        insp_nb.add(tab_rat, text=" AI Rationale ")
        self.rationale_text = tk.Text(tab_rat, wrap="word", font=self.font_ui, padx=8, pady=6)
        self.rationale_text.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # TAB 3: WITNESS GATEKEEPER ("ADD VS. DISREGARD")
    # ------------------------------------------------------------------
    def _build_gatekeeper_tab(self) -> None:
        top = ttk.Frame(self.tab_gatekeeper, padding=8)
        top.pack(fill="x")

        ttk.Label(
            top,
            text="AI Witness Gatekeeper — Evaluates New Texts for License Safety, Corruption & Independence",
            font=self.font_header,
        ).pack(side="left")

        ttk.Button(
            top,
            text="➕ Add & Evaluate Witness File (.txt/.usfm/.xml/.tsv/.json/.pdf)...",
            style="Accent.TButton",
            command=self._open_add_witness_file_dialog,
        ).pack(side="right", padx=(6, 0))

        ttk.Button(
            top,
            text="📋 Paste Raw Witness Text...",
            command=self._open_paste_witness_dialog,
        ).pack(side="right")

        mid = ttk.PanedWindow(self.tab_gatekeeper, orient="vertical")
        mid.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        tbl_box = ttk.Frame(mid)
        wcols = ("siglum", "title", "scope", "tier", "status", "weight", "license", "text_type")
        self.wit_tree = ttk.Treeview(tbl_box, columns=wcols, show="headings", selectmode="browse")
        for cid, hdr, w_px in [
            ("siglum", "Siglum", 150),
            ("title", "Witness / Edition Title", 340),
            ("scope", "Scope", 70),
            ("tier", "Tier", 65),
            ("status", "AI Gatekeeper Status", 170),
            ("weight", "Weight", 75),
            ("license", "Detected License", 210),
            ("text_type", "Textual Stream", 250),
        ]:
            self.wit_tree.heading(cid, text=hdr)
            self.wit_tree.column(cid, width=w_px, anchor="w" if w_px > 100 else "center")

        self.wit_tree.tag_configure("ADMITTED", background="#F0FDF4")
        self.wit_tree.tag_configure("QUARANTINED_NC", background="#FEF2F2")
        self.wit_tree.tag_configure("DISREGARDED_CORRUPT", background="#FFF1F2")
        self.wit_tree.tag_configure("DISREGARDED_DUPLICATE", background="#FEFCE8")

        w_scroll = ttk.Scrollbar(tbl_box, orient="vertical", command=self.wit_tree.yview)
        self.wit_tree.configure(yscrollcommand=w_scroll.set)
        self.wit_tree.pack(side="left", fill="both", expand=True)
        w_scroll.pack(side="right", fill="y")
        self.wit_tree.bind("<<TreeviewSelect>>", self._on_witness_selected)
        mid.add(tbl_box, weight=3)

        detail_box = ttk.LabelFrame(mid, text=" Selected Witness Gatekeeper Verdict & Manual Editorial Override ", padding=8)
        self.wit_detail_text = tk.Text(detail_box, height=5, wrap="word", font=self.font_ui, bg="#F8FAFC", state="disabled")
        self.wit_detail_text.pack(fill="both", expand=True, pady=(0, 6))

        act_bar = ttk.Frame(detail_box)
        act_bar.pack(fill="x")
        ttk.Label(act_bar, text="Override Status / Weight:", font=self.font_ui_bold).pack(side="left", padx=(0, 8))
        self.override_weight_var = tk.DoubleVar(value=0.90)
        ttk.Label(act_bar, text="Weight (0.0–1.0):").pack(side="left", padx=(0, 4))
        ttk.Spinbox(act_bar, from_=0.0, to=1.0, increment=0.02, width=6, textvariable=self.override_weight_var).pack(
            side="left", padx=(0, 10)
        )
        ttk.Button(
            act_bar,
            text="✓ Force ADMIT to Active Collation",
            command=lambda: self._override_selected_witness("ADMITTED"),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            act_bar,
            text="⚠ Quarantine (Tier 5 Study-Only)",
            command=lambda: self._override_selected_witness("QUARANTINED_NC"),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            act_bar,
            text="✕ Disregard Witness",
            command=lambda: self._override_selected_witness("DISREGARDED_DUPLICATE"),
        ).pack(side="left")

        mid.add(detail_box, weight=1)

    # ------------------------------------------------------------------
    # TAB 4: AUDIT LOG & BRAIN CONFIGURATION
    # ------------------------------------------------------------------
    def _build_settings_tab(self) -> None:
        cfg_box = ttk.LabelFrame(
            self.tab_settings,
            text=" Pluggable Open-Source AI Brain Settings (Offline Philological · Textual Analysis · Local LLM · Cloud) ",
            padding=12,
        )
        cfg_box.pack(fill="x", padx=10, pady=10)

        self.local_ep_var = tk.StringVar(value=self.engine.config.local_endpoint)
        self.local_mdl_var = tk.StringVar(value=self.engine.config.local_model)
        self.gem_key_var = tk.StringVar(value=self.engine.config.gemini_api_key)
        self.gem_mdl_var = tk.StringVar(value=self.engine.config.gemini_model)
        self.gem_think_var = tk.StringVar(value=self.engine.config.gemini_thinking_level)

        grid = ttk.Frame(cfg_box)
        grid.pack(fill="x")

        ttk.Label(grid, text="Local Offline LLM URL (127.0.0.1 only):", font=self.font_ui_bold).grid(
            row=0, column=0, sticky="w", pady=4
        )
        ttk.Entry(grid, textvariable=self.local_ep_var, width=44, font=self.font_mono).grid(
            row=0, column=1, sticky="w", padx=8, pady=4
        )
        ttk.Label(grid, text="Local Model Tag:", font=self.font_ui_bold).grid(row=0, column=2, sticky="w", padx=(16, 4))
        ttk.Entry(grid, textvariable=self.local_mdl_var, width=24, font=self.font_mono).grid(
            row=0, column=3, sticky="w", pady=4
        )

        ttk.Label(grid, text="Optional Cloud GEMINI_API_KEY:", font=self.font_ui_bold).grid(
            row=1, column=0, sticky="w", pady=4
        )
        ttk.Entry(grid, textvariable=self.gem_key_var, width=44, show="•", font=self.font_mono).grid(
            row=1, column=1, sticky="w", padx=8, pady=4
        )
        ttk.Label(grid, text="Cloud Model:", font=self.font_ui_bold).grid(row=1, column=2, sticky="w", padx=(16, 4))
        ttk.Combobox(
            grid,
            textvariable=self.gem_mdl_var,
            state="readonly",
            width=22,
            values=["gemini-4-carbon", "gemini-4-argon", "gemini-4-hydrogen", "gemini-3.5-flash-lite"],
        ).grid(row=1, column=3, sticky="w", pady=4)

        # Optional Claude review for the Textual Analysis Brain (advisory; never changes the text)
        self.claude_review_var = tk.BooleanVar(value=self.engine.config.claude_review)
        self.claude_mdl_var = tk.StringVar(value=self.engine.config.claude_model)
        self.claude_effort_var = tk.StringVar(value=self.engine.config.claude_effort)
        self.claude_key_var = tk.StringVar(value=self.engine.config.anthropic_api_key)
        ttk.Checkbutton(
            grid,
            text="Claude review of contested readings (Textual Analysis Brain; needs Offline Lock off, `pip install anthropic`)",
            variable=self.claude_review_var,
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 4))
        ttk.Label(grid, text="Claude Model / Effort:", font=self.font_ui_bold).grid(row=3, column=0, sticky="w", pady=4)
        claude_box = ttk.Frame(grid)
        claude_box.grid(row=3, column=1, sticky="w", padx=8)
        ttk.Combobox(
            claude_box,
            textvariable=self.claude_mdl_var,
            state="readonly",
            width=20,
            values=["claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-2"],
        ).pack(side="left")
        ttk.Combobox(
            claude_box,
            textvariable=self.claude_effort_var,
            state="readonly",
            width=8,
            values=["low", "medium", "high", "xhigh", "max"],
        ).pack(side="left", padx=(6, 0))
        ttk.Label(grid, text="ANTHROPIC_API_KEY (blank = SDK login):", font=self.font_ui_bold).grid(
            row=3, column=2, sticky="w", padx=(16, 4)
        )
        ttk.Entry(grid, textvariable=self.claude_key_var, width=24, show="•", font=self.font_mono).grid(
            row=3, column=3, sticky="w"
        )

        self.openai_key_var = tk.StringVar(value=self.engine.config.openai_api_key)
        self.openai_mdl_var = tk.StringVar(value=self.engine.config.openai_model)
        self.openai_effort_var = tk.StringVar(value=self.engine.config.openai_effort)
        ttk.Label(grid, text="OpenAI review: select OpenAI Review Brain above; requires Offline Lock off. "
                  "Sends witness text to OpenAI; API usage may incur charges. No extra packages required.",
                  wraplength=1000).grid(row=4, column=0, columnspan=4, sticky="w", pady=(10, 4))
        ttk.Label(grid, text="OPENAI_API_KEY (blank = environment):", font=self.font_ui_bold).grid(
            row=5, column=0, sticky="w", pady=4)
        ttk.Entry(grid, textvariable=self.openai_key_var, width=44, show="•", font=self.font_mono).grid(
            row=5, column=1, sticky="w", padx=8, pady=4)
        ttk.Label(grid, text="OpenAI Model / Effort:", font=self.font_ui_bold).grid(
            row=5, column=2, sticky="w", padx=(16, 4))
        openai_box = ttk.Frame(grid)
        openai_box.grid(row=5, column=3, sticky="w")
        ttk.Entry(openai_box, textvariable=self.openai_mdl_var, width=18, font=self.font_mono).pack(side="left")
        ttk.Combobox(openai_box, textvariable=self.openai_effort_var, state="readonly", width=7,
                     values=["low", "medium", "high", "xhigh", "max"]).pack(side="left", padx=(6, 0))

        ttk.Button(
            cfg_box,
            text="💾 Save Brain Configuration",
            style="Accent.TButton",
            command=self._save_brain_settings_form,
        ).pack(anchor="w", pady=(8, 0))

        log_box = ttk.LabelFrame(self.tab_settings, text=" Chronological Gatekeeper Decision Audit Log ", padding=8)
        log_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        lcols = ("time", "lang", "witness", "decision", "tier", "conf", "model", "summary")
        self.log_tree = ttk.Treeview(log_box, columns=lcols, show="headings")
        for cid, hdr, w_px in [
            ("time", "UTC Timestamp", 145),
            ("lang", "Lang", 65),
            ("witness", "Witness", 230),
            ("decision", "Decision", 160),
            ("tier", "Tier", 55),
            ("conf", "Conf.", 65),
            ("model", "Brain Used", 190),
            ("summary", "Summary", 440),
        ]:
            self.log_tree.heading(cid, text=hdr)
            self.log_tree.column(cid, width=w_px, anchor="w" if w_px > 90 else "center")

        l_scroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=l_scroll.set)
        self.log_tree.pack(side="left", fill="both", expand=True)
        l_scroll.pack(side="right", fill="y")

    # ------------------------------------------------------------------
    # SAINTS CRITICAL TEXT HOME (LIBRARY) HANDLERS
    # ------------------------------------------------------------------
    def _refresh_library_home(self, select_target: Optional[tuple[str, int]] = None) -> None:
        lang = self.current_lang.get()
        summary = self.engine.get_edition_home_summary(lang)
        self.home_summary_var.set(
            f"{summary['edition_title']}  —  {summary['saved_chapter_count']} / {summary['total_chapters_in_canon']} Chapters Saved  "
            f"·  {summary['saved_verse_count']:,} Reconstructed Verses  ·  {summary['locked_verse_count']} Human Verified  "
            f"·  {summary['review_flag_count']} ⚑ Review Flags"
        )
        self.home_path_var.set(f"In-Studio Home: {summary['home_path']}")

        saved_by_book: Dict[str, List[Dict[str, Any]]] = {}
        for row in summary["saved_chapters"]:
            saved_by_book.setdefault(str(row["book_slug"]), []).append(row)

        for item in self.lib_tree.get_children():
            self.lib_tree.delete(item)

        books = get_books_for_language(lang)
        first_saved_iid = ""
        target_iid = ""

        for div in DIVISIONS:
            div_books = [b for b in books if b.division == div["id"]]
            if not div_books:
                continue
            div_saved_cnt = sum(len(saved_by_book.get(b.slug, [])) for b in div_books)
            div_tot_cnt = sum(chapters_for_language(b, lang) for b in div_books)
            div_iid = f"div:{div['id']}"
            self.lib_tree.insert(
                "",
                "end",
                iid=div_iid,
                text=div["label"],
                values=(f"{div_saved_cnt}/{div_tot_cnt}", f"{len(div_books)} books"),
                open=(div_saved_cnt > 0 or div["id"] == "01_Law"),
                tags=("division",),
            )
            for b in div_books:
                b_saved = saved_by_book.get(b.slug, [])
                b_iid = f"book:{b.slug}"
                b_tag = "book_saved" if b_saved else "book_empty"
                status_txt = f"{len(b_saved)} saved in Studio" if b_saved else "Not yet collated"
                self.lib_tree.insert(
                    div_iid,
                    "end",
                    iid=b_iid,
                    text=f"{b.order:02d} · {b.title}",
                    values=(f"{len(b_saved)}/{chapters_for_language(b, lang)}", status_txt),
                    open=bool(b_saved),
                    tags=(b_tag,),
                )
                for ch_row in b_saved:
                    c_num = int(ch_row["chapter"])
                    c_iid = f"ch:{b.slug}:{c_num}"
                    if not first_saved_iid:
                        first_saved_iid = c_iid
                    if select_target and select_target == (b.slug, c_num):
                        target_iid = c_iid
                    flags_str = f" · ⚑ {ch_row['review_flag_count']}" if int(ch_row.get("review_flag_count", 0)) else ""
                    lock_str = f" · 🔒 {ch_row['locked_count']}" if int(ch_row.get("locked_count", 0)) else ""
                    self.lib_tree.insert(
                        b_iid,
                        "end",
                        iid=c_iid,
                        text=f"Chapter {c_num:02d}",
                        values=(
                            f"{ch_row['verse_count']} vv.",
                            f"{ch_row['variant_verse_count']} apparatus{lock_str}{flags_str}",
                        ),
                        tags=("chapter_row",),
                    )

        pick_iid = target_iid or first_saved_iid
        if pick_iid and self.lib_tree.exists(pick_iid):
            self.lib_tree.selection_set(pick_iid)
            self._on_library_node_selected()
        else:
            self.home_selected_chapter = None
            self._render_home_reader()

    def _on_library_node_selected(self, _event: Any = None) -> None:
        sel = self.lib_tree.selection()
        if not sel:
            return
        iid = sel[0]
        lang = self.current_lang.get()
        if iid.startswith("ch:"):
            _, slug, ch_str = iid.split(":", 2)
            self.home_selected_book_slug = slug
            self.home_selected_chapter = self.engine.get_saved_chapter(lang, slug, int(ch_str))
            self._render_home_reader()
        elif iid.startswith("book:"):
            slug = iid.split(":", 1)[1]
            self.home_selected_book_slug = slug
            saved_list = [r for r in self.engine.list_saved_chapters(lang) if r["book_slug"] == slug]
            if saved_list:
                self.home_selected_chapter = self.engine.get_saved_chapter(lang, slug, int(saved_list[0]["chapter"]))
            else:
                self.home_selected_chapter = None
            self._render_home_reader()

    def _render_home_reader(self) -> None:
        self.home_reader_text.configure(state="normal")
        self.home_reader_text.delete("1.0", "end")

        ch_data = self.home_selected_chapter
        if not ch_data:
            book_title = BOOKS_BY_SLUG[self.home_selected_book_slug].title if self.home_selected_book_slug in BOOKS_BY_SLUG else "Selected Book"
            self.home_reader_title.configure(text=f"{book_title} — Not Yet Collated")
            self.home_reader_text.insert(
                "end",
                f"No chapters of {book_title} have been saved into the Saints {self.current_lang.get().title()} Critical Text home yet.\n\n"
                f"Click '⚡ Collate Next Chapter in Book' above (or open '2 · Collation Workbench') to reconstruct Chapter 1 offline.",
                ("meta",),
            )
            self.home_reader_text.configure(state="disabled")
            return

        lang = str(ch_data["language"])
        b_title = str(ch_data["book_title"])
        ch_num = int(ch_data["chapter"])
        mode = self.home_view_mode.get()
        self.home_reader_title.configure(
            text=f"{b_title} {ch_num:02d} — Saints {lang.title()} Critical Text ({ch_data['verse_count']} verses)"
        )

        if mode == "markdown" and ch_data.get("local_md_path") and Path(ch_data["local_md_path"]).exists():
            md_txt = Path(ch_data["local_md_path"]).read_text(encoding="utf-8", errors="replace")
            for line in md_txt.splitlines():
                if line.startswith("# "):
                    self.home_reader_text.insert("end", line[2:] + "\n", ("h1",))
                elif line.startswith("## ") or line.startswith("### "):
                    self.home_reader_text.insert("end", line.lstrip("#").strip() + "\n", ("h2",))
                else:
                    self.home_reader_text.insert("end", line + "\n")
        elif mode == "tsv" and ch_data.get("local_tsv_path") and Path(ch_data["local_tsv_path"]).exists():
            tsv_txt = Path(ch_data["local_tsv_path"]).read_text(encoding="utf-8", errors="replace")
            self.home_reader_text.insert("end", tsv_txt, ("mono",))
        else:
            # Clean Scripture Edition
            self.home_reader_text.insert("end", f"{b_title} · Chapter {ch_num}\n", ("h1",))
            self.home_reader_text.insert(
                "end",
                f"Saints {lang.title()} Critical Text  ·  {ch_data['verse_count']} Verses  ·  "
                f"{ch_data['variant_verse_count']} Apparatus Units  ·  Updated {ch_data['updated_at']}\n\n",
                ("meta",),
            )
            show_tr = bool(self.show_translit_var.get()) and lang in ("greek", "hebrew")
            for vr in ch_data.get("verses", []):
                v_tags = ("vnum", "rtl") if lang == "hebrew" else ("vnum",)
                self.home_reader_text.insert("end", f"{vr['verse']} ", v_tags)
                t_tags: List[str] = []
                if vr.get("human_locked"):
                    t_tags.append("locked")
                if lang == "hebrew":
                    t_tags.append("rtl")
                self.home_reader_text.insert("end", f"{vr['critical_text']}\n", tuple(t_tags))
                if show_tr:
                    tr = self.engine.transliterate(str(vr["critical_text"]), lang)
                    if tr:
                        self.home_reader_text.insert("end", f"{tr}\n", ("translit", "ltr"))

        self.home_reader_text.configure(state="disabled")

    def _on_translit_toggled(self) -> None:
        """Refresh Library Reader, Collation Workbench, and Tab 5 Concordance when transliteration is toggled."""
        self._render_home_reader()
        if self.loaded_chapter_data:
            sel_v = int(self.selected_verse_obj["verse"]) if self.selected_verse_obj else None
            self._render_chapter(self.loaded_chapter_data)
            if sel_v is not None and self.verse_tree.exists(str(sel_v)):
                self.verse_tree.selection_set(str(sel_v))
                self.verse_tree.see(str(sel_v))
                self._on_verse_selected()
        if hasattr(self, "conc_atom_tree"):
            self._refresh_concordance_atoms()
        if hasattr(self, "conc_canvas") and self.conc_loaded_graph:
            self._draw_concordance_graph()
            self._populate_concordance_occurrences()

    def _jump_from_home_to_workbench(self) -> None:
        slug = self.home_selected_book_slug
        ch_num = int(self.home_selected_chapter["chapter"]) if self.home_selected_chapter else 1
        if slug not in BOOKS_BY_SLUG:
            return
        book = BOOKS_BY_SLUG[slug]
        # Set division, book, and chapter in Workbench
        div_labels = list(self.div_combo["values"])
        target_div_lbl = next((d["label"] for d in DIVISIONS if d["id"] == book.division), "")
        if target_div_lbl in div_labels:
            self.div_combo.current(div_labels.index(target_div_lbl))
            self._populate_books_for_current_div()
        for idx, b in enumerate(self.books_in_div):
            if b.slug == slug:
                self.book_combo.current(idx)
                self.current_book_slug.set(slug)
                self.ch_spin.configure(to=chapters_for_language(b, self.current_lang.get()))
                break
        self.current_chapter.set(ch_num)
        self.notebook.select(self.tab_workbench)
        self._on_chapter_selected()

    def _collate_next_from_home(self) -> None:
        lang = self.current_lang.get()
        slug = self.home_selected_book_slug
        if slug not in BOOKS_BY_SLUG:
            return
        book = BOOKS_BY_SLUG[slug]
        saved_nums = {int(r["chapter"]) for r in self.engine.list_saved_chapters(lang) if r["book_slug"] == slug}
        next_ch = next((c for c in range(1, chapters_for_language(book, lang) + 1) if c not in saved_nums), 1)

        def _work() -> Dict[str, Any]:
            return self.engine.collate_and_adjudicate(lang, slug, next_ch, preserve_human_locks=True)

        def _done(data: Dict[str, Any]) -> None:
            self._refresh_library_home(select_target=(slug, next_ch))
            self.status_var.set(
                f"Saved {book.title} {next_ch} into Saints {lang.title()} Critical Text Home ({data['verse_count']} verses)."
            )

        self._run_bg(f"Collating {lang.title()} {book.title} {next_ch}", _work, _done)

    # ------------------------------------------------------------------
    # EVENT HANDLERS & BACKGROUND WORKERS
    # ------------------------------------------------------------------
    def _poll_queue(self) -> None:
        while not self.ui_queue.empty():
            fn = self.ui_queue.get_nowait()
            fn()
        self.root.after(80, self._poll_queue)

    def _run_bg(self, label: str, worker: Callable[[], Any], on_done: Callable[[Any], None]) -> None:
        self.status_var.set(f"Working: {label}...")
        self.progress.start(12)

        def _target() -> None:
            try:
                res = worker()
                self.ui_queue.put(lambda: self._finish_bg(label, res, None, on_done))
            except Exception as exc:
                self.ui_queue.put(lambda e=exc: self._finish_bg(label, None, e, on_done))

        threading.Thread(target=_target, daemon=True).start()

    def _finish_bg(
        self,
        label: str,
        result: Any,
        err: Optional[Exception],
        on_done: Callable[[Any], None],
    ) -> None:
        self.progress.stop()
        if err is not None:
            self.status_var.set(f"Error during {label}: {err}")
            messagebox.showerror("Operation Error", str(err), parent=self.root)
            return
        on_done(result)

    def _on_lang_changed(self, _event: Any = None) -> None:
        idx = self.lang_combo.current()
        lang_code = LANG_OPTIONS[idx][0]
        self.current_lang.set(lang_code)
        self._refresh_divisions_and_books()
        self._refresh_witness_table()
        self._refresh_library_home()
        self._load_or_collate_initial()

    def _on_brain_quick_changed(self, _event: Any = None) -> None:
        idx = self.brain_combo.current()
        pid = BRAIN_OPTIONS[idx][0]
        if pid == "cloud_gemini" and self.offline_lock_var.get():
            messagebox.showinfo(
                "Strict Offline Lock Active",
                "Strict Offline Lock is currently ON (blocking all internet calls).\n\n"
                "Uncheck '🔒 Strict Offline Lock' in the top-right bar when you want Cloud Gemini 4 to make live API calls; otherwise it will safely run the local Offline Philological Brain.",
                parent=self.root,
            )
        self.engine.config.provider_id = pid
        self.engine.save_settings(self.engine.config)
        self.status_var.set(f"Active AI Brain switched to: {BRAIN_OPTIONS[idx][1]}")

    def _on_offline_lock_toggled(self) -> None:
        locked = bool(self.offline_lock_var.get())
        self.engine.config.offline_locked = locked
        self.engine.save_settings(self.engine.config)
        state_txt = "OFFLINE LOCKED (100% Air-Gapped)" if locked else "Internet Unlocked (Cloud / Drive Sync Permitted)"
        self.status_var.set(f"Network Guard: {state_txt}")

    def _refresh_divisions_and_books(self) -> None:
        lang = self.current_lang.get()
        avail_books = get_books_for_language(lang)
        avail_divs = [d for d in DIVISIONS if any(b.division == d["id"] for b in avail_books)]
        self.div_combo["values"] = [d["label"] for d in avail_divs]
        if avail_divs:
            self.div_combo.current(0)
            self.current_division.set(avail_divs[0]["id"])
        self._populate_books_for_current_div()

    def _populate_books_for_current_div(self) -> None:
        lang = self.current_lang.get()
        div_label = self.div_combo.get()
        div_id = next((d["id"] for d in DIVISIONS if d["label"] == div_label), "01_Law")
        self.current_division.set(div_id)
        self.books_in_div = [b for b in get_books_for_language(lang) if b.division == div_id]
        self.book_combo["values"] = [f"{b.order:02d} · {b.title}" for b in self.books_in_div]
        if self.books_in_div:
            self.book_combo.current(0)
            self.current_book_slug.set(self.books_in_div[0].slug)
            self.ch_spin.configure(to=chapters_for_language(self.books_in_div[0], lang))
            self.current_chapter.set(1)

    def _on_division_changed(self, _event: Any = None) -> None:
        self._populate_books_for_current_div()
        self._on_chapter_selected()

    def _on_book_changed(self, _event: Any = None) -> None:
        idx = self.book_combo.current()
        if 0 <= idx < len(self.books_in_div):
            b = self.books_in_div[idx]
            self.current_book_slug.set(b.slug)
            self.ch_spin.configure(to=chapters_for_language(b, self.current_lang.get()))
            self.current_chapter.set(1)
            self._on_chapter_selected()

    def _on_chapter_selected(self) -> None:
        lang = self.current_lang.get()
        slug = self.current_book_slug.get()
        ch = int(self.current_chapter.get())
        saved = self.engine.get_saved_chapter(lang, slug, ch)
        if saved:
            self._render_chapter(saved)
            self.status_var.set(
                f"Loaded saved Saints {lang.title()} Critical Text: {saved['book_title']} {ch} ({saved['verse_count']} verses, {saved['variant_verse_count']} contested)"
            )
        else:
            self._run_collate_current()

    def _load_or_collate_initial(self) -> None:
        self._on_chapter_selected()

    def _run_collate_current(self) -> None:
        lang = self.current_lang.get()
        slug = self.current_book_slug.get()
        ch = int(self.current_chapter.get())
        book = BOOKS_BY_SLUG[slug]

        def _work() -> Dict[str, Any]:
            return self.engine.collate_and_adjudicate(lang, slug, ch, preserve_human_locks=True)

        def _done(data: Dict[str, Any]) -> None:
            self._refresh_library_home(select_target=(slug, ch))
            still_selected = (
                self.current_lang.get() == lang
                and self.current_book_slug.get() == slug
                and int(self.current_chapter.get()) == ch
            )
            if not still_selected:
                self.status_var.set(f"Collated {lang.title()} {book.title} {ch} in the background (saved; not shown).")
                return
            self._render_chapter(data)
            self.status_var.set(
                f"Adjudicated & Saved {lang.title()} {book.title} {ch} → {data['verse_count']} verses "
                f"({data['variant_verse_count']} with apparatus entries) · In-Studio Home Updated"
            )

        self._run_bg(f"Collating {lang.title()} {book.title} {ch}", _work, _done)

    def _run_batch_book(self) -> None:
        lang = self.current_lang.get()
        slug = self.current_book_slug.get()
        book = BOOKS_BY_SLUG[slug]
        total_ch = chapters_for_language(book, lang)
        if not messagebox.askyesno(
            "Batch Collate Book",
            f"Collate and adjudicate all {total_ch} chapters of {book.title} ({lang.title()}) offline and save them into Saints-{lang.title()}-Critical-Text?",
            parent=self.root,
        ):
            return

        def _work() -> tuple[int, List[str]]:
            count = 0
            skipped: List[str] = []
            for c in range(1, total_ch + 1):
                self.ui_queue.put(
                    lambda ch_n=c: self.status_var.set(
                        f"Batch Collating {book.title}: Chapter {ch_n} of {total_ch}..."
                    )
                )
                try:
                    self.engine.collate_and_adjudicate(lang, slug, c, preserve_human_locks=True)
                    count += 1
                except (LookupError, ValueError) as exc:
                    skipped.append(f"{c}: {exc}")
            return count, skipped

        def _done(res: tuple[int, List[str]]) -> None:
            done_count, skipped = res
            self._refresh_library_home(select_target=(slug, 1))
            self._on_chapter_selected()
            skipped_txt = ("\n\nSkipped:\n" + "\n".join(skipped[:12])) if skipped else ""
            messagebox.showinfo(
                "Batch Collation Complete",
                f"Collated {done_count} of {total_ch} chapters of {book.title} ({lang.title()}).\n\nSaved inside Studio at:\n{CRITICAL_OUTPUT_ROOTS[lang] / book.division / book.folder_name}{skipped_txt}",
                parent=self.root,
            )

        self._run_bg(f"Batch Collating {book.title}", _work, _done)

    def _render_chapter(self, data: Dict[str, Any]) -> None:
        self.loaded_chapter_data = data
        verses = data.get("verses", [])

        # Render continuous text
        lang = str(data.get("language", ""))
        show_tr = bool(self.show_translit_var.get()) and lang in ("greek", "hebrew")
        self.continuous_text.configure(state="normal")
        self.continuous_text.delete("1.0", "end")
        for vr in verses:
            v_tags = ("vnum", "rtl") if lang == "hebrew" else ("vnum",)
            self.continuous_text.insert("end", f"{vr['verse']} ", v_tags)
            t_tags: List[str] = []
            if vr.get("human_locked"):
                t_tags.append("locked")
            elif vr.get("apparatus"):
                t_tags.append("contested")
            if lang == "hebrew":
                t_tags.append("rtl")
            suffix = "\n" if show_tr else "  "
            self.continuous_text.insert("end", f"{vr['critical_text']}{suffix}", tuple(t_tags))
            if show_tr:
                tr = self.engine.transliterate(str(vr["critical_text"]), lang)
                if tr:
                    self.continuous_text.insert("end", f"{tr}\n", ("translit", "ltr"))
        self.continuous_text.configure(state="disabled")

        # Render verse table
        for item in self.verse_tree.get_children():
            self.verse_tree.delete(item)

        for vr in verses:
            app_cnt = len(vr.get("apparatus", []))
            dis_cnt = len(vr.get("disregarded", []))
            tag = "human_locked" if vr.get("human_locked") else ("has_variant" if app_cnt > 0 else "")
            src_label = (
                "🔒 Human Verified"
                if vr.get("human_locked")
                else ("⚑ Needs review" if vr.get("needs_review") else str(vr.get("decision_source", ""))[:26])
            )
            self.verse_tree.insert(
                "",
                "end",
                iid=str(vr["verse"]),
                values=(
                    vr["verse"],
                    vr["critical_text"],
                    f"{app_cnt} unit(s)" if app_cnt else "—",
                    f"{dis_cnt} filtered" if dis_cnt else "—",
                    f"{vr['confidence']:.0%}",
                    src_label,
                ),
                tags=(tag,) if tag else (),
            )

        if verses:
            first_iid = str(verses[0]["verse"])
            self.verse_tree.selection_set(first_iid)
            self._populate_verse_inspector(verses[0])

    def _on_verse_selected(self, _event: Any = None) -> None:
        if not self.loaded_chapter_data:
            return
        sel = self.verse_tree.selection()
        if not sel:
            return
        v_num = int(sel[0])
        for vr in self.loaded_chapter_data.get("verses", []):
            if int(vr["verse"]) == v_num:
                self._populate_verse_inspector(vr)
                break

    def _populate_verse_inspector(self, vr: Dict[str, Any]) -> None:
        self.selected_verse_obj = vr
        ch_title = self.loaded_chapter_data["book_title"] if self.loaded_chapter_data else ""
        ch_num = self.loaded_chapter_data["chapter"] if self.loaded_chapter_data else 1
        lock_badge = " [HUMAN LOCKED]" if vr.get("human_locked") else (" [⚑ NEEDS REVIEW]" if vr.get("needs_review") else "")
        self.inspector_hdr.configure(text=f"{ch_title} {ch_num}:{vr['verse']}{lock_badge}")

        lang = str(self.loaded_chapter_data.get("language", "")) if self.loaded_chapter_data else ""
        show_tr = bool(self.show_translit_var.get()) and lang in ("greek", "hebrew")

        self.verse_edit_text.delete("1.0", "end")
        self.verse_edit_text.insert("1.0", vr["critical_text"])
        self.verse_edit_text.tag_configure("rtl", justify="right")
        if lang == "hebrew":
            self.verse_edit_text.tag_add("rtl", "1.0", "end")

        # Populate Latinized Pronunciation strip
        self.verse_translit_text.configure(state="normal")
        self.verse_translit_text.delete("1.0", "end")
        if show_tr:
            self.verse_translit_text.insert("1.0", self.engine.transliterate(str(vr["critical_text"]), lang))
        elif lang == "latin":
            self.verse_translit_text.insert("1.0", "— Latin text (already in the Latin alphabet) —")
        else:
            self.verse_translit_text.insert("1.0", "— Transliteration hidden (enable 'Aa Transliteration' above) —")
        self.verse_translit_text.configure(state="disabled")

        # Populate Apparatus Listbox
        self.app_listbox.delete(0, "end")
        self._current_variant_choices: List[tuple[int, int]] = []
        for a_idx, a in enumerate(vr.get("apparatus", [])):
            lemma = a["lemma"]
            lwits = " ".join(a.get("lemma_witnesses", []))
            l_tr = f" [{self.engine.transliterate(str(lemma), lang)}]" if show_tr and lemma else ""
            for v_idx, var in enumerate(a.get("variants", [])):
                rdg = var["reading"]
                vwits = " ".join(var.get("witnesses", []))
                r_tr = f" [{self.engine.transliterate(str(rdg), lang)}]" if show_tr and rdg else ""
                prefix = "[whole verse] " if a.get("kind") == "verse" else ""
                self.app_listbox.insert("end", f"{prefix}{lemma}{l_tr} ({lwits})  ]  {rdg}{r_tr} ({vwits})")
                self._current_variant_choices.append((a_idx, v_idx))
        if not self._current_variant_choices:
            self.app_listbox.insert("end", "No substantive variants — witnesses agree on underlying wording.")

        # Populate Witness Matrix & Disregarded Surface Noise
        self.witness_matrix_text.configure(state="normal")
        self.witness_matrix_text.delete("1.0", "end")
        self.witness_matrix_text.insert("end", "ADMITTED WITNESS READINGS:\n", ("sig",))
        refs = vr.get("witness_refs", {}) or {}
        for sig, wtxt in vr.get("witness_readings", {}).items():
            ref_note = f" [numbered {refs[sig]} in this witness]" if sig in refs else ""
            self.witness_matrix_text.insert("end", f"• {sig}{ref_note}: ", ("sig",))
            self.witness_matrix_text.insert("end", f"{wtxt}\n", ("grk",))
            if show_tr and wtxt:
                w_tr = self.engine.transliterate(str(wtxt), lang)
                if w_tr:
                    self.witness_matrix_text.insert("end", f"↳ {w_tr}\n", ("tr",))
        for sig in vr.get("absent_witnesses", []) or []:
            self.witness_matrix_text.insert("end", f"• {sig}: ", ("sig",))
            self.witness_matrix_text.insert("end", "— verse absent from this witness —\n")

        findings = [(a.get("lemma", ""), f) for a in vr.get("apparatus", []) for f in a.get("analysis", []) or []]
        verse_findings = vr.get("analysis", []) or []
        if findings or verse_findings:
            self.witness_matrix_text.insert("end", "\nINTERNAL-EVIDENCE ANALYSIS (Textual Analysis Brain):\n", ("noise_hdr",))
            for f in verse_findings:
                self.witness_matrix_text.insert("end", f"• {f.get('canon', '')}: {f.get('note', '')}\n")
            for lemma, f in findings:
                if f.get("strength") == "info" and not str(f.get("canon", "")).startswith("variant type"):
                    continue
                self.witness_matrix_text.insert("end", f"• [{lemma}] {f.get('canon', '')}: {f.get('note', '')}\n")

        dis_list = vr.get("disregarded", [])
        if dis_list:
            self.witness_matrix_text.insert("end", "\nDISREGARDED ORTHOGRAPHIC / SCRIBAL NOISE:\n", ("noise_hdr",))
            for d in dis_list:
                dforms = ", ".join(d.get("disregarded_forms", []))
                dwits = ", ".join(d.get("witnesses", []))
                self.witness_matrix_text.insert(
                    "end",
                    f"• Kept '{d['kept_form']}' over [{dforms}] ({dwits})\n  Reason: {d['reason']}\n",
                )
        self.witness_matrix_text.configure(state="disabled")

        # Rationale
        self.rationale_text.delete("1.0", "end")
        self.rationale_text.insert("1.0", vr.get("rationale", ""))

    def _adopt_selected_variant(self) -> None:
        if not self.selected_verse_obj or not self._current_variant_choices:
            return
        sel = self.app_listbox.curselection()
        if not sel:
            messagebox.showinfo("Select Variant", "Select a variant line in the Critical Apparatus list first.", parent=self.root)
            return
        if sel[0] >= len(self._current_variant_choices):
            return
        a_idx, v_idx = self._current_variant_choices[sel[0]]
        v_num = int(self.selected_verse_obj["verse"])
        try:
            updated = self.engine.adopt_variant(
                language=self.loaded_chapter_data["language"],
                book_slug=self.loaded_chapter_data["book_slug"],
                chapter=int(self.loaded_chapter_data["chapter"]),
                verse=v_num,
                apparatus_index=a_idx,
                variant_index=v_idx,
            )
        except (ValueError, KeyError, IndexError) as exc:
            messagebox.showwarning("Cannot Adopt Automatically", str(exc), parent=self.root)
            return
        self._render_chapter(updated)
        self._refresh_library_home(select_target=(updated["book_slug"], int(updated["chapter"])))
        self.verse_tree.selection_set(str(v_num))
        self._on_verse_selected()
        self.status_var.set(f"Adopted variant in verse {v_num}, locked it, and updated the in-Studio MD/JSON/TSV.")

    def _save_human_verse_override(self) -> None:
        if not self.loaded_chapter_data or not self.selected_verse_obj:
            return
        v_num = int(self.selected_verse_obj["verse"])
        new_txt = self.verse_edit_text.get("1.0", "end").strip()
        new_rat = self.rationale_text.get("1.0", "end").strip()
        if not new_txt:
            messagebox.showwarning("Empty Reading", "The verse text is empty; nothing was saved.", parent=self.root)
            return
        try:
            updated = self.engine.override_verse(
                language=self.loaded_chapter_data["language"],
                book_slug=self.loaded_chapter_data["book_slug"],
                chapter=int(self.loaded_chapter_data["chapter"]),
                verse=v_num,
                new_critical_text=new_txt,
                rationale_note=new_rat,
                lock=True,
            )
        except KeyError as exc:
            messagebox.showerror("Cannot Save", str(exc), parent=self.root)
            return
        self._render_chapter(updated)
        self._refresh_library_home(select_target=(updated["book_slug"], int(updated["chapter"])))
        self.verse_tree.selection_set(str(v_num))
        self._on_verse_selected()
        self.status_var.set(f"Locked human scholarly reading for Verse {v_num} and updated in-Studio MD/JSON/TSV.")

    def _unlock_human_verse(self) -> None:
        if not self.loaded_chapter_data or not self.selected_verse_obj:
            return
        v_num = int(self.selected_verse_obj["verse"])
        self.engine.override_verse(
            language=self.loaded_chapter_data["language"],
            book_slug=self.loaded_chapter_data["book_slug"],
            chapter=int(self.loaded_chapter_data["chapter"]),
            verse=v_num,
            new_critical_text=self.verse_edit_text.get("1.0", "end").strip(),
            rationale_note=self.rationale_text.get("1.0", "end").strip(),
            lock=False,
        )
        self._run_collate_current()

    def _open_output_folder(self) -> None:
        lang = self.current_lang.get()
        folder = CRITICAL_OUTPUT_ROOTS[lang]
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))  # type: ignore[attr-defined]

    def _sync_current_to_drive(self) -> None:
        if self.offline_lock_var.get():
            messagebox.showwarning(
                "Strict Offline Lock Active",
                "Uncheck '🔒 Strict Offline Lock' in the top-right bar when you are online and want to sync this chapter to Google Drive.",
                parent=self.root,
            )
            return
        lang = self.current_lang.get()
        slug = self.current_book_slug.get()
        ch = int(self.current_chapter.get())

        def _work() -> tuple[str, str]:
            return self.engine.sync_saved_chapter_to_drive(lang, slug, ch)

        def _done(res: tuple[str, str]) -> None:
            _fid, url = res
            self.status_var.set(f"Synced to Google Drive: {url}")
            messagebox.showinfo(
                "Synced to Google Drive",
                f"Chapter synced cleanly to Saints Website on Google Drive:\n\n{url}",
                parent=self.root,
            )

        self._run_bg("Syncing Chapter to Google Drive", _work, _done)

    # ------------------------------------------------------------------
    # WITNESS GATEKEEPER HANDLERS
    # ------------------------------------------------------------------
    def _refresh_witness_table(self) -> None:
        for item in self.wit_tree.get_children():
            self.wit_tree.delete(item)
        rows = self.engine.list_witnesses(self.current_lang.get())
        self._wit_by_id: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            wid = str(r["id"])
            self._wit_by_id[wid] = r
            st = str(r["status"])
            self.wit_tree.insert(
                "",
                "end",
                iid=wid,
                values=(
                    r["siglum"],
                    r["title"],
                    r["testament_scope"],
                    f"Tier {r['tier']}" if int(r["tier"]) > 0 else "—",
                    st,
                    f"{float(r['weight']):.2f}",
                    r["license"],
                    r["text_type"],
                ),
                tags=(st,),
            )

    def _on_witness_selected(self, _event: Any = None) -> None:
        sel = self.wit_tree.selection()
        if not sel:
            return
        w = self._wit_by_id.get(sel[0])
        if not w:
            return
        self.override_weight_var.set(float(w["weight"]) if float(w["weight"]) > 0 else 0.85)
        self.wit_detail_text.configure(state="normal")
        self.wit_detail_text.delete("1.0", "end")
        self.wit_detail_text.insert(
            "1.0",
            f"Siglum: {w['siglum']}  |  Status: {w['status']}  |  License: {w['license']}\n"
            f"Path: {w['file_path']}\n"
            f"Gatekeeper Verdict: {w['gatekeeper_summary']}",
        )
        self.wit_detail_text.configure(state="disabled")

    def _override_selected_witness(self, new_status: str) -> None:
        sel = self.wit_tree.selection()
        if not sel:
            return
        wid = sel[0]
        current_tier = int(self._wit_by_id.get(wid, {}).get("tier", 0) or 0)
        if new_status == "ADMITTED":
            new_tier = current_tier if 1 <= current_tier <= 4 else 1
        else:
            new_tier = 5 if new_status == "QUARANTINED_NC" else 0
        self.engine.update_witness_status(
            witness_id=wid,
            new_status=new_status,
            new_weight=float(self.override_weight_var.get()),
            new_tier=new_tier,
        )
        self._refresh_witness_table()
        self._refresh_audit_log()
        self.wit_tree.selection_set(wid)
        self._on_witness_selected()
        self.status_var.set(f"Updated witness '{wid}' → {new_status}")

    def _open_add_witness_file_dialog(self) -> None:
        fp_str = filedialog.askopenfilename(
            parent=self.root,
            title="Select Biblical Witness File to Evaluate",
            filetypes=[
                ("Supported Witness Files", "*.txt *.usfm *.sfm *.xml *.tei *.osis *.usfx *.tsv *.csv *.json *.pdf"),
                ("All Files", "*.*"),
            ],
        )
        if not fp_str:
            return
        fp = Path(fp_str)
        self._open_metadata_and_ingest_modal(source_file=fp)

    def _open_paste_witness_dialog(self) -> None:
        self._open_metadata_and_ingest_modal(source_file=None)

    def _open_metadata_and_ingest_modal(self, source_file: Optional[Path]) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title("AI Witness Gatekeeper — Evaluate New Text")
        dlg.geometry("680x520" if source_file is None else "620x320")
        dlg.transient(self.root)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=14)
        frm.pack(fill="both", expand=True)

        sig_var = tk.StringVar(value=source_file.stem[:14] if source_file else "MS-New")
        title_var = tk.StringVar(value=source_file.name if source_file else "New Manuscript / Edition Sample")
        scope_var = tk.StringVar(value="OT/NT")
        lic_var = tk.StringVar(value="")

        ttk.Label(frm, text=f"Target Language: {self.current_lang.get().upper()}", font=self.font_ui_bold).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        if source_file:
            ttk.Label(frm, text=f"File: {source_file}", font=self.font_mono).grid(
                row=1, column=0, columnspan=2, sticky="w", pady=(0, 8)
            )

        ttk.Label(frm, text="Siglum (Short Apparatus Code):").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=sig_var, width=28).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(frm, text="Witness / Edition Title:").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=title_var, width=48).grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(frm, text="Testament Scope:").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Combobox(frm, textvariable=scope_var, state="readonly", values=["OT", "NT", "OT/NT"], width=14).grid(
            row=4, column=1, sticky="w", pady=4
        )

        ttk.Label(frm, text="Declared License (blank = AI auto-detect):").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=lic_var, width=48).grid(row=5, column=1, sticky="w", pady=4)

        raw_box: Optional[tk.Text] = None
        if source_file is None:
            ttk.Label(frm, text="Paste Verse Lines (e.g. 'Genesis 1:1 ...' or '1:1 ...' or USFM):").grid(
                row=6, column=0, columnspan=2, sticky="w", pady=(8, 4)
            )
            raw_box = tk.Text(frm, height=10, wrap="word", font=self.font_scripture)
            raw_box.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=4)
            frm.rowconfigure(7, weight=1)

        def _submit() -> None:
            pasted = raw_box.get("1.0", "end").strip() if raw_box else ""
            dlg.destroy()

            def _work() -> tuple[str, Any]:
                return self.engine.ingest_new_witness(
                    language=self.current_lang.get(),
                    siglum=sig_var.get(),
                    title=title_var.get(),
                    testament_scope=scope_var.get(),
                    declared_license=lic_var.get(),
                    source_file=source_file,
                    pasted_text=pasted,
                )

            def _done(res: tuple[str, Any]) -> None:
                wid, verdict = res
                self._refresh_witness_table()
                self._refresh_audit_log()
                self.wit_tree.selection_set(wid)
                self._on_witness_selected()
                reasons_bullet = "\n".join(f"• {r}" for r in verdict.reasons if r)
                messagebox.showinfo(
                    f"AI Gatekeeper Verdict: {verdict.decision}",
                    f"Decision: {verdict.decision}\n"
                    f"Assigned Tier: {verdict.tier_assigned}  |  Recommended Weight: {verdict.recommended_weight:.2f}\n"
                    f"Confidence: {verdict.confidence:.0%}  |  Brain: {verdict.model_used}\n\n"
                    f"{verdict.summary}\n\n"
                    f"Detailed Findings:\n{reasons_bullet}",
                    parent=self.root,
                )

            self._run_bg("Running AI Gatekeeper Evaluation", _work, _done)

        ttk.Button(frm, text="🧠 Evaluate with AI Gatekeeper Brain", style="Accent.TButton", command=_submit).grid(
            row=8, column=0, columnspan=2, pady=(12, 0)
        )

    # ------------------------------------------------------------------
    # SETTINGS & AUDIT LOG
    # ------------------------------------------------------------------
    def _save_brain_settings_form(self) -> None:
        cfg = BrainConfig(
            provider_id=BRAIN_OPTIONS[self.brain_combo.current()][0],
            offline_locked=bool(self.offline_lock_var.get()),
            local_endpoint=self.local_ep_var.get().strip(),
            local_model=self.local_mdl_var.get().strip(),
            gemini_api_key=self.gem_key_var.get().strip(),
            gemini_model=self.gem_mdl_var.get().strip(),
            gemini_thinking_level=self.gem_think_var.get().strip(),
            use_decision_model=True,
            claude_review=bool(self.claude_review_var.get()),
            claude_model=self.claude_mdl_var.get().strip() or "claude-opus-5-5",
            claude_effort=self.claude_effort_var.get().strip() or "high",
            anthropic_api_key=self.claude_key_var.get().strip(),
            openai_api_key=self.openai_key_var.get().strip(),
            openai_model=self.openai_mdl_var.get().strip() or BrainConfig().openai_model,
            openai_effort=self.openai_effort_var.get().strip() or "high",
        )
        self.engine.save_settings(cfg)
        self.status_var.set("Saved AI Brain settings locally.")
        messagebox.showinfo("Settings Saved", "AI Brain configuration saved locally.", parent=self.root)

    def _refresh_audit_log(self) -> None:
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
        for row in self.engine.list_gatekeeper_log(150):
            self.log_tree.insert(
                "",
                "end",
                values=(
                    row["created_at"],
                    str(row["language"]).upper(),
                    row["witness_title"],
                    row["decision"],
                    row["tier_assigned"],
                    f"{float(row['confidence']):.0%}",
                    row["model_used"],
                    row["summary"],
                ),
            )

    # ------------------------------------------------------------------
    # TAB 5: THE SAINTS CONCORDANCE (TRILINGUAL ROOT & MORPHEME GRAPH)
    # ------------------------------------------------------------------
    _RAINBOW_PALETTE: Dict[str, tuple[str, str, str]] = {
        "red": ("#E0473A", "#FEF2F2", "#991B1B"),
        "orange": ("#EE7A1A", "#FFF7ED", "#9A3412"),
        "yellow": ("#D9A310", "#FEFCE8", "#854D0E"),
        "green": ("#2E8B57", "#F0FDF4", "#166534"),
        "blue": ("#3A7BD5", "#EFF6FF", "#1E40AF"),
        "indigo": ("#4B3FA8", "#EEF2FF", "#3730A3"),
        "violet": ("#A24BC4", "#FAF5FF", "#6B21A8"),
    }

    def _build_concordance_tab(self) -> None:
        # 1. Top Dark Slate Telemetry & Zero-Bloat Compression Banner
        banner = tk.Frame(self.tab_concordance, bg="#1E293B", padx=14, pady=9)
        banner.pack(fill="x", padx=8, pady=(8, 6))

        self.conc_banner_title_var = tk.StringVar(
            value="THE SAINTS CONCORDANCE — lemmas, roots & parses from tagged Hebrew, Greek and Latin editions (Saints.Bible verse numbers)"
        )
        self.conc_banner_metrics_var = tk.StringVar(value="Loading Concordance statistics...")
        self.conc_banner_submetrics_var = tk.StringVar(value="")
        self.conc_savings_badge_var = tk.StringVar(value="Pack: not exported yet")

        # Pack the right-hand badge first so wide metrics text never pushes it off-screen.
        badge = tk.Frame(banner, bg="#0F172A", padx=12, pady=6, highlightthickness=1, highlightbackground="#334155")
        badge.pack(side="right", padx=(12, 0))
        tk.Label(
            badge,
            textvariable=self.conc_savings_badge_var,
            fg="#4ADE80",
            bg="#0F172A",
            font=("Segoe UI", 9, "bold"),
        ).pack()

        left_b = tk.Frame(banner, bg="#1E293B")
        left_b.pack(side="left", fill="x", expand=True)
        self._conc_banner_title_lbl = tk.Label(
            left_b,
            textvariable=self.conc_banner_title_var,
            fg="#F8FAFC",
            bg="#1E293B",
            font=("Segoe UI Semibold", 11),
            anchor="w",
            justify="left",
        )
        self._conc_banner_title_lbl.pack(anchor="w", fill="x")
        self._conc_banner_metrics_lbl = tk.Label(
            left_b,
            textvariable=self.conc_banner_metrics_var,
            fg="#93C5FD",
            bg="#1E293B",
            font=("Consolas", 9),
            anchor="w",
            justify="left",
        )
        self._conc_banner_metrics_lbl.pack(anchor="w", fill="x")
        self._conc_banner_submetrics_lbl = tk.Label(
            left_b,
            textvariable=self.conc_banner_submetrics_var,
            fg="#CBD5E1",
            bg="#1E293B",
            font=("Consolas", 8),
            anchor="w",
            justify="left",
        )
        self._conc_banner_submetrics_lbl.pack(anchor="w", fill="x")

        def _sync_conc_banner_wrap(event: Any) -> None:
            wrap = max(int(event.width) - 8, 320)
            self._conc_banner_title_lbl.configure(wraplength=wrap)
            self._conc_banner_metrics_lbl.configure(wraplength=wrap)
            self._conc_banner_submetrics_lbl.configure(wraplength=wrap)

        left_b.bind("<Configure>", _sync_conc_banner_wrap)

        # 2. Search, Filter & Offline Pipeline Toolbar
        tbar = ttk.Frame(self.tab_concordance, padding=(8, 2))
        tbar.pack(fill="x")

        ttk.Label(tbar, text="Search Root / Translit / Strong's:", font=self.font_ui_bold).pack(side="left", padx=(0, 4))
        self.conc_search_entry = ttk.Entry(tbar, textvariable=self.conc_search_var, width=22, font=self.font_ui)
        self.conc_search_entry.pack(side="left", padx=(0, 4))
        self.conc_search_entry.bind("<Return>", lambda _e: self._refresh_concordance_tab())

        ttk.Button(tbar, text="🔍 Search", command=self._refresh_concordance_tab).pack(side="left", padx=(0, 3))
        ttk.Button(tbar, text="✕", width=3, command=self._clear_concordance_search).pack(side="left", padx=(0, 8))

        ttk.Label(tbar, text="Lang:", font=self.font_ui_bold).pack(side="left", padx=(0, 4))
        self.conc_lang_combo = ttk.Combobox(
            tbar,
            state="readonly",
            width=9,
            values=["all", "heb", "arc", "grc", "lat"],
            textvariable=self.conc_lang_var,
        )
        self.conc_lang_combo.pack(side="left", padx=(0, 6))
        self.conc_lang_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_concordance_tab())

        ttk.Label(tbar, text="Theme:", font=self.font_ui_bold).pack(side="left", padx=(0, 4))
        self.conc_col_combo = ttk.Combobox(
            tbar,
            state="readonly",
            width=14,
            values=["all", "curated_rainbow", "indigo", "blue", "violet", "yellow", "orange", "green", "red"],
            textvariable=self.conc_colour_var,
        )
        self.conc_col_combo.pack(side="left", padx=(0, 8))
        self.conc_col_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_concordance_tab())

        ttk.Checkbutton(
            tbar,
            text="Aa Transliteration",
            variable=self.show_translit_var,
            command=self._on_translit_toggled,
        ).pack(side="left", padx=(2, 6))

        ttk.Button(
            tbar,
            text="📦 Export Saints.Bible Pack",
            style="Accent.TButton",
            command=self._run_concordance_export,
        ).pack(side="right", padx=(4, 0))
        ttk.Button(
            tbar,
            text="➕ Add / Edit Sense",
            command=self._open_concordance_sense_modal,
        ).pack(side="right", padx=(4, 0))
        ttk.Button(
            tbar,
            text="🔄 Rebuild All Books",
            command=self._run_concordance_index_all,
        ).pack(side="right", padx=(4, 0))
        ttk.Button(
            tbar,
            text="⚡ Index Current Book",
            command=self._run_concordance_index_current_book,
        ).pack(side="right", padx=(4, 0))

        # 3. Main Horizontal Split: Left (Concept & Root Browser) | Right (Visual Graph + Aligned Occurrences)
        main_split = ttk.PanedWindow(self.tab_concordance, orient="horizontal")
        main_split.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        left_nb = ttk.Notebook(main_split)
        main_split.add(left_nb, weight=2)

        # Left Tab A: Unified Trilingual Concepts & Sense Offsets
        tab_concepts = ttk.Frame(left_nb, padding=4)
        left_nb.add(tab_concepts, text=" Unified Concepts & Senses ")

        self.conc_tree = ttk.Treeview(
            tab_concepts,
            columns=("langs", "senses", "hits"),
            show="tree headings",
            selectmode="browse",
        )
        self.conc_tree.heading("#0", text="Concept Family / Sense Offset")
        self.conc_tree.heading("langs", text="Streams")
        self.conc_tree.heading("senses", text="Role / Offsets")
        self.conc_tree.heading("hits", text="Hits")
        self.conc_tree.column("#0", width=235, anchor="w")
        self.conc_tree.column("langs", width=62, anchor="center", stretch=False)
        self.conc_tree.column("senses", width=110, anchor="w", stretch=False)
        self.conc_tree.column("hits", width=52, anchor="center", stretch=False)

        for cname, (_hex, pastel, fg_hex) in self._RAINBOW_PALETTE.items():
            self.conc_tree.tag_configure(f"col_{cname}", background=pastel, foreground=fg_hex, font=self.font_ui_bold)
        self.conc_tree.tag_configure("concept_plain", font=self.font_ui_bold)
        self.conc_tree.tag_configure("sense_child", foreground="#334155")

        ct_scroll = ttk.Scrollbar(tab_concepts, orient="vertical", command=self.conc_tree.yview)
        self.conc_tree.configure(yscrollcommand=ct_scroll.set)
        self.conc_tree.pack(side="left", fill="both", expand=True)
        ct_scroll.pack(side="right", fill="y")
        self.conc_tree.bind("<<TreeviewSelect>>", self._on_conc_tree_selected)

        # Left Tab B: Atomic Roots & Morpheme Algebra
        tab_atoms = ttk.Frame(left_nb, padding=4)
        left_nb.add(tab_atoms, text=" Core Roots & Morphemes ")

        atom_bar = ttk.Frame(tab_atoms)
        atom_bar.pack(fill="x", pady=(0, 4))
        ttk.Radiobutton(
            atom_bar,
            text="Core Etymological Roots",
            value="roots",
            variable=self.conc_atom_kind_var,
            command=self._refresh_concordance_atoms,
        ).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(
            atom_bar,
            text="Morpheme Algebra",
            value="morphemes",
            variable=self.conc_atom_kind_var,
            command=self._refresh_concordance_atoms,
        ).pack(side="left")

        self.conc_atom_tree = ttk.Treeview(
            tab_atoms,
            columns=("lang", "key", "detail", "count"),
            show="headings",
            selectmode="browse",
        )
        self.conc_atom_tree.heading("lang", text="Lang")
        self.conc_atom_tree.heading("key", text="Root / Code")
        self.conc_atom_tree.heading("detail", text="Core Image / Morpheme Function")
        self.conc_atom_tree.heading("count", text="Stems")
        self.conc_atom_tree.column("lang", width=48, anchor="center", stretch=False)
        self.conc_atom_tree.column("key", width=155, anchor="w", stretch=False)
        self.conc_atom_tree.column("detail", width=195, anchor="w")
        self.conc_atom_tree.column("count", width=55, anchor="center", stretch=False)

        at_scroll = ttk.Scrollbar(tab_atoms, orient="vertical", command=self.conc_atom_tree.yview)
        self.conc_atom_tree.configure(yscrollcommand=at_scroll.set)
        self.conc_atom_tree.pack(side="left", fill="both", expand=True)
        at_scroll.pack(side="right", fill="y")
        self.conc_atom_tree.bind("<Double-1>", self._on_atom_double_clicked)

        # Right Vertical Split: Top (Interactive Visual Decomposition Canvas) | Bottom (Aligned Occurrence Matrix)
        right_split = ttk.PanedWindow(main_split, orient="vertical")
        main_split.add(right_split, weight=5)

        graph_frame = ttk.LabelFrame(
            right_split,
            text=" Visual Root → Morpheme Recipe → Unified Concept → Contextual Senses (Click a Sense Card to Filter) ",
            padding=4,
        )
        canvas_wrap = tk.Frame(graph_frame, bg="#F8FAFC")
        canvas_wrap.pack(fill="both", expand=True)

        self.conc_canvas = tk.Canvas(canvas_wrap, bg="#F8FAFC", highlightthickness=0, height=340)
        cg_scroll = ttk.Scrollbar(canvas_wrap, orient="vertical", command=self.conc_canvas.yview)
        self.conc_canvas.configure(yscrollcommand=cg_scroll.set)
        self.conc_canvas.pack(side="left", fill="both", expand=True)
        cg_scroll.pack(side="right", fill="y")
        self.conc_canvas.bind("<Configure>", lambda _e: self._draw_concordance_graph())
        right_split.add(graph_frame, weight=3)

        occ_frame = ttk.LabelFrame(
            right_split,
            text=" Trilingual Aligned Occurrences & Sense Curation (Double-Click a Verse to Open in Collation Workbench) ",
            padding=6,
        )
        occ_top = ttk.Frame(occ_frame)
        occ_top.pack(fill="both", expand=True)

        occ_cols = ("ref", "rendered", "role", "state", "heb", "grc", "lat", "lock")
        self.conc_occ_tree = ttk.Treeview(occ_top, columns=occ_cols, show="headings", selectmode="browse", height=7)
        self.conc_occ_tree.heading("ref", text="Verse")
        self.conc_occ_tree.heading("rendered", text="Saints Word")
        self.conc_occ_tree.heading("role", text="Sense Role")
        self.conc_occ_tree.heading("state", text="Stream State")
        self.conc_occ_tree.heading("heb", text="Hebrew [Root + Morphemes]")
        self.conc_occ_tree.heading("grc", text="Greek [Root + Morphemes]")
        self.conc_occ_tree.heading("lat", text="Latin [Root + Morphemes]")
        self.conc_occ_tree.heading("lock", text="Lock")

        self.conc_occ_tree.column("ref", width=78, anchor="w", stretch=False)
        self.conc_occ_tree.column("rendered", width=105, anchor="w", stretch=False)
        self.conc_occ_tree.column("role", width=120, anchor="w", stretch=False)
        self.conc_occ_tree.column("state", width=95, anchor="center", stretch=False)
        self.conc_occ_tree.column("heb", width=195, anchor="w")
        self.conc_occ_tree.column("grc", width=195, anchor="w")
        self.conc_occ_tree.column("lat", width=195, anchor="w")
        self.conc_occ_tree.column("lock", width=48, anchor="center", stretch=False)

        self.conc_occ_tree.tag_configure("locked_occ", background="#F0FDF4")
        self.conc_occ_tree.tag_configure("divergent_occ", background="#FFFBEB")

        ot_scroll = ttk.Scrollbar(occ_top, orient="vertical", command=self.conc_occ_tree.yview)
        self.conc_occ_tree.configure(yscrollcommand=ot_scroll.set)
        self.conc_occ_tree.pack(side="left", fill="both", expand=True)
        ot_scroll.pack(side="right", fill="y")
        self.conc_occ_tree.bind("<<TreeviewSelect>>", self._on_conc_occ_selected)
        self.conc_occ_tree.bind("<Double-1>", lambda _e: self._jump_from_concordance_to_workbench())

        # Scholarly Sense Override & Nuance Inspector Bar
        cur_bar = ttk.Frame(occ_frame, padding=(0, 6, 0, 0))
        cur_bar.pack(fill="x")

        self.conc_note_var = tk.StringVar(
            value="Select any Trilingual Concept or Sense Offset above to inspect its shared etymological roots, morpheme formulas, and verse occurrences."
        )
        tk.Label(
            cur_bar,
            textvariable=self.conc_note_var,
            fg="#1E293B",
            bg="#EFF6FF",
            anchor="w",
            justify="left",
            padx=10,
            pady=5,
            font=self.font_ui,
            wraplength=920,
        ).pack(fill="x", pady=(0, 6))

        edit_strip = ttk.Frame(cur_bar)
        edit_strip.pack(fill="x")
        ttk.Label(edit_strip, text="Selected Occurrence Sense:", font=self.font_ui_bold).pack(side="left", padx=(0, 6))
        self.conc_occ_sense_combo = ttk.Combobox(edit_strip, state="readonly", width=30, font=self.font_ui)
        self.conc_occ_sense_combo.pack(side="left", padx=(0, 8))

        self.conc_occ_plural_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(edit_strip, text="Plural (-s / ENG:PL)", variable=self.conc_occ_plural_var).pack(
            side="left", padx=(0, 8)
        )
        self.conc_occ_lock_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(edit_strip, text="🔒 Human Lock", variable=self.conc_occ_lock_var).pack(side="left", padx=(0, 10))

        ttk.Button(
            edit_strip,
            text="✓ Apply Sense to Verse",
            style="Accent.TButton",
            command=self._apply_selected_occurrence_sense,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            edit_strip,
            text="↺ Show All Senses in Concept",
            command=self._clear_active_sense_filter,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            edit_strip,
            text="✎ Open Verse in Workbench",
            command=self._jump_from_concordance_to_workbench,
        ).pack(side="right")

        right_split.add(occ_frame, weight=2)

    def _clear_concordance_search(self) -> None:
        self.conc_search_var.set("")
        self.conc_lang_var.set("all")
        self.conc_colour_var.set("all")
        self._refresh_concordance_tab()

    def _refresh_concordance_telemetry(self) -> None:
        """Measured figures only (the first build showed a hard-coded '99.1 % bloat eliminated')."""
        st = self.engine.get_concordance_stats()
        lemmas = st.get("lemmas_used_by_lang") or {}
        roots = st.get("roots_used_by_lang") or {}
        parts = []
        tot_content = 0
        tot_func = 0
        tot_indexed = 0
        tot_morph = 0
        for lang in ("hebrew", "greek", "latin"):
            c = (st.get("coverage") or {}).get(lang)
            if c and c.get("tokens"):
                pct = 100.0 * c["indexed"] / c["tokens"]
                parts.append(f"{lang.title()} {c['indexed']:,}/{c['tokens']:,} ({pct:.1f}%, {c['untagged']:,} untagged)")
                tot_indexed += int(c.get("indexed", 0))
                tot_content += int(c.get("content_words", c.get("indexed", 0)))
                tot_func += int(c.get("function_words", 0))
                tot_morph += int(c.get("with_morph", 0))
        self.conc_banner_metrics_var.set(
            ("Indexed: " + "  |  ".join(parts)) if parts else "Not built yet — click 🔄 Rebuild All Books"
        )
        sub_parts = []
        if tot_indexed:
            sub_parts.append(f"Content/func: {tot_content:,} / {tot_func:,}")
            if tot_morph:
                sub_parts.append(f"Parsed: {tot_morph:,} ({100.0 * tot_morph / tot_indexed:.1f}%)")
        lr = " · ".join(f"{k.upper()} {lemmas.get(k, 0):,}/{roots.get(k, 0):,}" for k in sorted(set(lemmas) | set(roots)))
        if lr:
            sub_parts.append(f"Lemmas/roots: {lr}")
        sub_parts.append(f"Hub alignments: {st['total_alignments']:,} ({st['locked_tokens']} 🔒)")
        if st.get("last_build_at"):
            sub_parts.append(f"Built {st['last_build_at']} ({st['last_build_seconds']:.0f} s)")
        self.conc_banner_submetrics_var.set("  |  ".join(sub_parts))
        if st["exported_gz_bytes"] > 0:
            self.conc_savings_badge_var.set(f"Pack: {st['exported_gz_bytes'] / 1024.0:,.0f} KB gzip (measured)")
        else:
            self.conc_savings_badge_var.set("Pack: not exported yet")

    def _refresh_concordance_tab(self, select_concept_id: Optional[int] = None) -> None:
        self._refresh_concordance_telemetry()
        self._refresh_concordance_atoms()

        for item in self.conc_tree.get_children():
            self.conc_tree.delete(item)

        concepts = self.engine.search_concordance(
            query=self.conc_search_var.get(),
            lang_filter=self.conc_lang_var.get(),
            colour_filter=self.conc_colour_var.get(),
            limit=250,
        )

        target_cid = select_concept_id or self.conc_selected_concept_id
        first_cid: Optional[int] = None

        for c in concepts:
            cid = int(c["concept_id"])
            if first_cid is None:
                first_cid = cid
            col = c.get("theme_colour")
            tag = f"col_{col}" if col in self._RAINBOW_PALETTE else "concept_plain"
            parent_iid = f"c:{cid}"
            badge = f"[{col.upper()}] " if col else ""
            self.conc_tree.insert(
                "",
                "end",
                iid=parent_iid,
                text=f"{badge}{c['eng_base_word']}  ({c['concept_slug']})",
                values=(f"{c['lang_span']} lang", f"{c['sense_count']} senses", c["hit_count"]),
                tags=(tag,),
                open=(cid == target_cid or len(concepts) <= 12),
            )
            for s in c.get("senses", []):
                sid = int(s["sense_id"])
                self.conc_tree.insert(
                    parent_iid,
                    "end",
                    iid=f"s:{cid}:{sid}",
                    text=f"  #{s['sense_offset']}  {s['base_word']}",
                    values=("→", s["sense_role"], s["hit_count"]),
                    tags=("sense_child",),
                )

        chosen = target_cid if (target_cid and self.conc_tree.exists(f"c:{target_cid}")) else first_cid
        if chosen is not None:
            self.conc_tree.selection_set(f"c:{chosen}")
            self.conc_tree.see(f"c:{chosen}")
            self._load_concordance_concept(chosen, active_sense_id=None)
        else:
            self.conc_loaded_graph = None
            self.conc_canvas.delete("all")
            for item in self.conc_occ_tree.get_children():
                self.conc_occ_tree.delete(item)

    def _refresh_concordance_atoms(self) -> None:
        for item in self.conc_atom_tree.get_children():
            self.conc_atom_tree.delete(item)
        kind = self.conc_atom_kind_var.get()
        rows = self.engine.list_concordance_catalog(
            kind=kind,
            lang_filter=self.conc_lang_var.get(),
            query=self.conc_search_var.get(),
            limit=300,
        )
        if kind == "morphemes":
            self.conc_atom_tree.heading("key", text="Morpheme / Affix")
            self.conc_atom_tree.heading("detail", text="Slot · Grammatical Function")
            self.conc_atom_tree.heading("count", text="ID")
            for r in rows:
                disp = f"{r['morph_code']} ({r['affix_form']})" if r["affix_form"] != "—" else r["morph_code"]
                self.conc_atom_tree.insert(
                    "",
                    "end",
                    values=(r["lang"].upper(), disp, f"[{r['morph_slot']}] {r['grammatical_fn']}", r["morph_id"]),
                )
        else:
            show_tr = bool(self.show_translit_var.get())
            self.conc_atom_tree.heading("key", text="Core Root (Translit)" if show_tr else "Core Root")
            self.conc_atom_tree.heading("detail", text="Irreducible Core Image")
            self.conc_atom_tree.heading("count", text="Stems")
            for r in rows:
                hno = f"[{r['homograph_no']}]" if int(r["homograph_no"]) > 1 else ""
                tr = str(r.get("translit") or "").strip()
                disp = f"{r['root_key']}{hno}  ({tr})" if (show_tr and tr and tr != r["root_key"]) else f"{r['root_key']}{hno}"
                self.conc_atom_tree.insert(
                    "",
                    "end",
                    values=(r["lang"].upper(), disp, r["core_idea"], r["stem_count"]),
                )

    def _on_atom_double_clicked(self, _event: Any = None) -> None:
        sel = self.conc_atom_tree.selection()
        if not sel or self.conc_atom_kind_var.get() != "roots":
            return
        vals = self.conc_atom_tree.item(sel[0], "values")
        if len(vals) >= 2:
            raw_root = str(vals[1]).split("(")[0].split("[")[0].strip()
            self.conc_search_var.set(raw_root)
            self._refresh_concordance_tab()

    def _on_conc_tree_selected(self, _event: Any = None) -> None:
        sel = self.conc_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("c:"):
            cid = int(iid.split(":")[1])
            self._load_concordance_concept(cid, active_sense_id=None)
        elif iid.startswith("s:"):
            _, cid_s, sid_s = iid.split(":")
            self._load_concordance_concept(int(cid_s), active_sense_id=int(sid_s))

    def _load_concordance_concept(self, concept_id: int, active_sense_id: Optional[int] = None) -> None:
        self.conc_selected_concept_id = concept_id
        self.conc_active_sense_id = active_sense_id
        self.conc_loaded_graph = self.engine.get_concordance_concept_graph(concept_id)
        tc = self.conc_loaded_graph["concept"]
        senses = self.conc_loaded_graph["senses"]

        # Populate sense dropdown for scholarly override
        self._sense_combo_ids = [int(s["sense_id"]) for s in senses]
        self.conc_occ_sense_combo["values"] = [
            f"#{s['sense_offset']} {s['base_word']} ({s['sense_role']})" for s in senses
        ]
        if senses:
            self.conc_occ_sense_combo.current(0)

        if active_sense_id is not None:
            s_match = next((s for s in senses if int(s["sense_id"]) == active_sense_id), None)
            if s_match:
                self.conc_note_var.set(
                    f"[{tc['concept_slug']} · Sense #{s_match['sense_offset']} '{s_match['base_word']}']  "
                    f"{s_match['usage_nuance']}  —  Base Concept: {tc['summary_note']}"
                )
        else:
            self.conc_note_var.set(f"[{tc['concept_slug']} · Base '{tc['eng_base_word']}']  {tc['summary_note']}")

        self._draw_concordance_graph()
        self._populate_concordance_occurrences()

    def _clear_active_sense_filter(self) -> None:
        if self.conc_selected_concept_id is not None:
            self._load_concordance_concept(self.conc_selected_concept_id, active_sense_id=None)

    def _populate_concordance_occurrences(self) -> None:
        for item in self.conc_occ_tree.get_children():
            self.conc_occ_tree.delete(item)
        self._conc_occ_by_iid.clear()
        self.conc_selected_occ = None
        if not self.conc_loaded_graph:
            return

        active_sid = self.conc_active_sense_id
        show_tr = bool(self.show_translit_var.get())
        for occ in self.conc_loaded_graph["occurrences"]:
            if active_sid is not None and int(occ["sense_id"]) != active_sid:
                continue
            iid = str(occ.get("occ_key") or f"occ:{occ['align_id']}")
            self._conc_occ_by_iid[iid] = occ
            tags = []
            if occ.get("human_locked"):
                tags.append("locked_occ")
            elif occ.get("alignment_state") not in ("unified", "grc_lat_only"):
                tags.append("divergent_occ")
            heb_val = occ.get("heb_formula_translit", occ["heb_formula"]) if show_tr else occ["heb_formula"]
            grc_val = occ.get("grc_formula_translit", occ["grc_formula"]) if show_tr else occ["grc_formula"]
            self.conc_occ_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    occ["saints_ref"],
                    occ["rendered_word"],
                    occ["sense_role"],
                    occ["alignment_state"],
                    heb_val,
                    grc_val,
                    occ["lat_formula"],
                    "🔒" if occ.get("human_locked") else "auto",
                ),
                tags=tuple(tags),
            )

    def _on_conc_occ_selected(self, _event: Any = None) -> None:
        sel = self.conc_occ_tree.selection()
        if not sel:
            return
        occ = self._conc_occ_by_iid.get(sel[0])
        if not occ:
            return
        self.conc_selected_occ = occ
        sid = int(occ["sense_id"])
        if hasattr(self, "_sense_combo_ids") and sid in self._sense_combo_ids:
            self.conc_occ_sense_combo.current(self._sense_combo_ids.index(sid))
        self.conc_occ_plural_var.set(occ.get("eng_morph_code") == "ENG:PL")
        # A sense chosen by a person is locked unless they untick the box (the first build pre-set the
        # box from the row, i.e. unlocked for every machine row, so curations were silently left 'auto').
        self.conc_occ_lock_var.set(True)

    def _apply_selected_occurrence_sense(self) -> None:
        if not self.conc_selected_occ or not hasattr(self, "_sense_combo_ids"):
            messagebox.showinfo("Select Occurrence", "Select a verse row in the Trilingual Occurrences table first.", parent=self.root)
            return
        if self.conc_selected_occ.get("align_id") is None:
            messagebox.showinfo(
                "Single-language occurrence",
                "Senses are assigned to the colour-hub alignment units. This row is a single word filed under its "
                "lemma; open a colour hub to change the sense of an aligned verse.",
                parent=self.root,
            )
            return
        idx = self.conc_occ_sense_combo.current()
        if idx < 0 or idx >= len(self._sense_combo_ids):
            return
        new_sid = self._sense_combo_ids[idx]
        align_id = int(self.conc_selected_occ["align_id"])
        ref = str(self.conc_selected_occ["saints_ref"])  # read before the reload clears the selection
        self.engine.set_concordance_alignment_sense(
            align_id=align_id,
            new_sense_id=new_sid,
            eng_plural=bool(self.conc_occ_plural_var.get()),
            lock=bool(self.conc_occ_lock_var.get()),
            rationale="Updated in Saints Concordance Studio Tab 5",
        )
        self._refresh_concordance_telemetry()
        if self.conc_selected_concept_id is not None:
            self._load_concordance_concept(self.conc_selected_concept_id, active_sense_id=self.conc_active_sense_id)
        if self.conc_occ_tree.exists(f"occ:{align_id}"):
            self.conc_occ_tree.selection_set(f"occ:{align_id}")
            self.conc_occ_tree.see(f"occ:{align_id}")
        self.status_var.set(f"Updated Concordance sense for {ref}.")

    def _draw_concordance_graph(self) -> None:
        """Render the 4-column Trilingual Root -> Morpheme Stem -> Base Concept -> Sense Offset graph."""
        c = self.conc_canvas
        c.delete("all")
        g = self.conc_loaded_graph
        if not g:
            c.create_text(
                280, 140,
                text="No Concept Selected — Search or pick a Trilingual Concept on the left.",
                fill="#64748B",
                font=self.font_ui_bold,
            )
            return

        w = max(c.winfo_width(), 860)
        roots = g["roots"][:10]
        stems = g["stems"][:12]
        senses = g["senses"]
        tc = g["concept"]

        col_name = tc.get("theme_colour") or "indigo"
        accent_hex, accent_pastel, _ = self._RAINBOW_PALETTE.get(col_name, ("#4B3FA8", "#EEF2FF", "#3730A3"))

        # Column X anchors across responsive canvas width
        pad_x = 18
        col1_x = pad_x
        col1_w = int(w * 0.21)
        col2_x = int(w * 0.25)
        col2_w = int(w * 0.23)
        col3_x = int(w * 0.52)
        col3_w = int(w * 0.18)
        col4_x = int(w * 0.74)
        col4_w = w - col4_x - pad_x

        # Column headers
        hdr_y = 16
        for hx, hw, htxt in [
            (col1_x, col1_w, "1 · CORE ROOTS (HEB / GRC / LAT)"),
            (col2_x, col2_w, "2 · MORPHEME COMPOSITIONS"),
            (col3_x, col3_w, "3 · UNIFIED BASE ANCHOR"),
            (col4_x, col4_w, "4 · CONTEXTUAL SENSES (CLICK)"),
        ]:
            c.create_text(hx + hw // 2, hdr_y, text=htxt, fill="#475569", font=("Segoe UI", 8, "bold"))

        top_y = 36
        root_h, root_gap = 52, 10
        stem_h, stem_gap = 46, 8
        sense_h, sense_gap = 52, 9

        total_h = max(
            320,
            top_y + len(roots) * (root_h + root_gap) + 24,
            top_y + len(stems) * (stem_h + stem_gap) + 24,
            top_y + len(senses) * (sense_h + sense_gap) + 24,
        )
        c.configure(scrollregion=(0, 0, w, total_h))

        lang_styles = {
            "heb": ("#FEF3C7", "#D97706", "#78350F", "HEB"),
            "arc": ("#FFEDD5", "#EA580C", "#7C2D12", "ARC"),
            "grc": ("#E0F2FE", "#0284C7", "#0C4A6E", "GRC"),
            "lat": ("#DCFCE7", "#16A34A", "#14532D", "LAT"),
        }

        # Precompute node center Y positions
        root_pos: Dict[int, tuple[int, int]] = {}
        for i, r in enumerate(roots):
            ry = top_y + i * (root_h + root_gap)
            root_pos[int(r["root_id"])] = (col1_x + col1_w, ry + root_h // 2)

        stem_pos: Dict[int, tuple[int, int, int]] = {}
        for i, st in enumerate(stems):
            sy = top_y + i * (stem_h + stem_gap)
            stem_pos[int(st["stem_id"])] = (col2_x, col2_x + col2_w, sy + stem_h // 2)

        hub_h = 108
        hub_y = max(top_y + 20, (min(total_h, 380) - hub_h) // 2)
        hub_left = (col3_x, hub_y + hub_h // 2)
        hub_right = (col3_x + col3_w, hub_y + hub_h // 2)

        sense_pos: Dict[int, tuple[int, int]] = {}
        for i, s in enumerate(senses):
            sy = top_y + i * (sense_h + sense_gap)
            sense_pos[int(s["sense_id"])] = (col4_x, sy + sense_h // 2)

        # Draw smooth cubic Bezier curves behind boxes
        for st in stems:
            rid = int(st["root_id"])
            sid = int(st["stem_id"])
            if rid in root_pos and sid in stem_pos:
                x1, y1 = root_pos[rid]
                x2, _, y2 = stem_pos[sid]
                mx = (x1 + x2) // 2
                c.create_line(x1, y1, mx, y1, mx, y2, x2, y2, smooth=True, width=1.6, fill="#94A3B8")
            if sid in stem_pos:
                _, sx2, sy2 = stem_pos[sid]
                hx1, hy1 = hub_left
                mx = (sx2 + hx1) // 2
                c.create_line(sx2, sy2, mx, sy2, mx, hy1, hx1, hy1, smooth=True, width=1.6, fill="#94A3B8")

        for s in senses:
            ssid = int(s["sense_id"])
            sx1, sy1 = sense_pos[ssid]
            hx2, hy2 = hub_right
            mx = (hx2 + sx1) // 2
            is_active = self.conc_active_sense_id == ssid
            line_col = accent_hex if (is_active or self.conc_active_sense_id is None) else "#CBD5E1"
            line_w = 2.8 if is_active else 1.7
            c.create_line(hx2, hy2, mx, hy2, mx, sy1, sx1, sy1, smooth=True, width=line_w, fill=line_col)

        show_tr = bool(self.show_translit_var.get())

        # Draw Column 1: Core Roots
        for i, r in enumerate(roots):
            ry = top_y + i * (root_h + root_gap)
            bg, bd, fg, badge_lbl = lang_styles.get(str(r["lang"]), ("#F1F5F9", "#64748B", "#0F172A", "ROOT"))
            c.create_rectangle(col1_x, ry, col1_x + col1_w, ry + root_h, fill=bg, outline=bd, width=1.5)
            hno = f"[{r['homograph_no']}]" if int(r["homograph_no"]) > 1 else ""
            r_tr = str(r.get("translit") or "").strip()
            r_lbl = f"{badge_lbl} · {r['root_key']}{hno}"
            if show_tr and r_tr and r_tr != r["root_key"]:
                r_lbl = f"{r_lbl} ({r_tr})"
            if len(r_lbl) > 28:
                r_lbl = r_lbl[:27] + "…"
            c.create_text(
                col1_x + 8, ry + 15,
                anchor="w",
                text=r_lbl,
                fill=fg,
                font=("Segoe UI", 9 if (show_tr and r_tr) else 10, "bold"),
            )
            idea = str(r["core_idea"])
            if len(idea) > 30:
                idea = idea[:29] + "…"
            c.create_text(col1_x + 8, ry + 35, anchor="w", text=idea, fill="#334155", font=("Segoe UI", 8))

        # Draw Column 2: Compositional Stems
        for i, st in enumerate(stems):
            sy = top_y + i * (stem_h + stem_gap)
            _, bd, _, _ = lang_styles.get(str(st["lang"]), ("#FFFFFF", "#64748B", "#0F172A", ""))
            c.create_rectangle(col2_x, sy, col2_x + col2_w, sy + stem_h, fill="#FFFFFF", outline=bd, width=1.2)
            strongs_lbl = f" ({st['ext_strongs']})" if st.get("ext_strongs") else ""
            s_tr = str(st.get("stem_translit") or "").strip()
            if show_tr and s_tr and s_tr != st["canonical_stem"]:
                stem_hdr = f"{st['canonical_stem']} · {s_tr}{strongs_lbl}"
            else:
                stem_hdr = f"{st['canonical_stem']}{strongs_lbl}"
            if len(stem_hdr) > 30:
                stem_hdr = stem_hdr[:29] + "…"
            c.create_text(
                col2_x + 8, sy + 14,
                anchor="w",
                text=stem_hdr,
                fill="#0F172A",
                font=("Palatino Linotype", 9 if (show_tr and s_tr) else 10, "bold"),
            )
            form_txt = str(st.get("structural_formula") or st["base_gloss"])
            if len(form_txt) > 32:
                form_txt = form_txt[:31] + "…"
            c.create_text(col2_x + 8, sy + 32, anchor="w", text=form_txt, fill="#475569", font=("Consolas", 8))

        # Draw Column 3: Central Unified Concept Hub
        c.create_rectangle(col3_x, hub_y, col3_x + col3_w, hub_y + hub_h, fill="#0F172A", outline=accent_hex, width=3)
        c.create_rectangle(col3_x, hub_y, col3_x + col3_w, hub_y + 22, fill=accent_hex, outline=accent_hex)
        c.create_text(
            col3_x + col3_w // 2, hub_y + 11,
            text=f"CONCEPT · {col_name.upper()}",
            fill="#FFFFFF",
            font=("Segoe UI", 8, "bold"),
        )
        c.create_text(
            col3_x + col3_w // 2, hub_y + 46,
            text=str(tc["eng_base_word"]).upper(),
            fill="#F8FAFC",
            font=("Segoe UI", 10, "bold"),
            width=col3_w - 12,
        )
        c.create_text(
            col3_x + col3_w // 2, hub_y + 80,
            text=f"{len(roots)} roots → {len(senses)} senses\n(Click hub to show all)",
            fill="#93C5FD",
            font=("Segoe UI", 8),
            justify="center",
        )
        hub_tag = "hub_reset"
        r_hit = c.create_rectangle(col3_x, hub_y, col3_x + col3_w, hub_y + hub_h, fill="", outline="", tags=(hub_tag,))
        c.tag_bind(r_hit, "<Button-1>", lambda _e: self._clear_active_sense_filter())

        # Draw Column 4: Contextual Sense Offset Nodes (Clickable!)
        for i, s in enumerate(senses):
            ssid = int(s["sense_id"])
            sy = top_y + i * (sense_h + sense_gap)
            is_active = self.conc_active_sense_id == ssid
            fill_c = accent_pastel if is_active else "#FFFFFF"
            out_c = accent_hex if is_active else "#94A3B8"
            out_w = 2.6 if is_active else 1.2
            stag = f"sense_card_{ssid}"
            c.create_rectangle(col4_x, sy, col4_x + col4_w, sy + sense_h, fill=fill_c, outline=out_c, width=out_w, tags=(stag,))
            c.create_text(
                col4_x + 9, sy + 15,
                anchor="w",
                text=f"#{s['sense_offset']}  {s['base_word']}   [{s['hit_count']} hits · {s['varint_byte_len']}B]",
                fill="#0F172A",
                font=("Segoe UI", 9, "bold"),
                tags=(stag,),
            )
            nuance = str(s["usage_nuance"])
            if len(nuance) > 38:
                nuance = nuance[:37] + "…"
            c.create_text(
                col4_x + 9, sy + 35,
                anchor="w",
                text=f"{s['sense_role']}: {nuance}",
                fill="#475569",
                font=("Segoe UI", 8),
                tags=(stag,),
            )
            c.tag_bind(
                stag,
                "<Button-1>",
                lambda _e, target_sid=ssid: self._load_concordance_concept(
                    int(self.conc_selected_concept_id or 1),
                    active_sense_id=(None if self.conc_active_sense_id == target_sid else target_sid),
                ),
            )

    # ------------------------------------------------------------------
    # CONCORDANCE <-> WORKBENCH NAVIGATION & PIPELINE ACTIONS
    # ------------------------------------------------------------------
    _STREAM_LANG = {"heb_ot": "hebrew", "grc_ot": "greek", "grc_nt": "greek", "lat_bible": "latin"}

    def _jump_from_concordance_to_workbench(self) -> None:
        """Open the occurrence's verse in the Workbench, converting the Saints.Bible verse number to the
        numbering of the language shown (Hebrew MT / Latin column).  Never starts a collation."""
        occ = self.conc_selected_occ
        if not occ:
            return
        slug = str(occ["book_slug"])
        if slug not in BOOKS_BY_SLUG:
            return
        book = BOOKS_BY_SLUG[slug]
        s_ch, s_vs = int(occ["chapter"]), int(occ["verse"])
        sub = int(occ.get("subverse") or 0)
        lang = self._STREAM_LANG.get(str(occ.get("lang_stream") or ""))
        if occ.get("align_id") is not None or lang is None:
            cur = self.current_lang.get()
            lang = cur if any(b.slug == slug for b in get_books_for_language(cur)) else "greek"
        targets = self.engine.concordance_verse_in_language(lang, slug, s_ch, s_vs, subverse=sub)
        if not targets and sub:
            for cand_lang in ("hebrew", "latin", "greek"):
                if cand_lang == lang:
                    continue
                cand_targets = self.engine.concordance_verse_in_language(cand_lang, slug, s_ch, s_vs, subverse=sub)
                if cand_targets:
                    lang, targets = cand_lang, cand_targets
                    break
        if not targets:
            self.status_var.set(f"{book.title} {s_ch}:{s_vs} (Saints.Bible numbering) has no counterpart in the {lang.title()} text.")
            return
        ch_num, vs_num = targets[0]
        if self.current_lang.get() != lang:
            self.current_lang.set(lang)
            self.lang_combo.current([code for code, _ in LANG_OPTIONS].index(lang))
            self._refresh_divisions_and_books()
            self._refresh_witness_table()
        div_labels = list(self.div_combo["values"])
        target_div_lbl = next((d["label"] for d in DIVISIONS if d["id"] == book.division), "")
        if target_div_lbl in div_labels:
            self.div_combo.current(div_labels.index(target_div_lbl))
            self._populate_books_for_current_div()
        for idx, b in enumerate(self.books_in_div):
            if b.slug == slug:
                self.book_combo.current(idx)
                self.current_book_slug.set(slug)
                self.ch_spin.configure(to=chapters_for_language(b, lang))
                break
        self.current_chapter.set(ch_num)
        self.notebook.select(self.tab_workbench)
        saved = self.engine.get_saved_chapter(lang, slug, ch_num)
        if not saved:
            self.status_var.set(
                f"{lang.title()} {book.title} {ch_num} is not saved yet — choose it in the Workbench to collate it."
            )
            return
        self._render_chapter(saved)
        if self.verse_tree.exists(str(vs_num)):
            self.verse_tree.selection_set(str(vs_num))
            self.verse_tree.see(str(vs_num))
            self._on_verse_selected()
        if (ch_num, vs_num) != (s_ch, s_vs):
            self.status_var.set(f"Saints.Bible {book.title} {s_ch}:{s_vs} = {lang.title()} {ch_num}:{vs_num}.")

    def _jump_from_workbench_to_concordance(self) -> None:
        slug = self.current_book_slug.get()
        lang = self.current_lang.get()
        ch_num = int(self.current_chapter.get())
        vs_num = int(self.selected_verse_obj["verse"]) if self.selected_verse_obj else 1
        info = self.engine.get_verse_concordance(slug, ch_num, vs_num, language=lang)
        self.notebook.select(self.tab_concordance)
        if info["tokens"]:
            pick = next((t for t in info["tokens"] if t.get("theme_colour")), None) or next(
                (t for t in info["tokens"] if t.get("is_content", 1)), info["tokens"][0]
            )
            cid = int(pick["concept_id"])
            sid = int(pick["sense_id"])
            self._refresh_concordance_tab(select_concept_id=cid)
            # after the queued <<TreeviewSelect>> of the refresh, so the sense filter is not reset
            self.root.after_idle(lambda: self._load_concordance_concept(cid, active_sense_id=sid))
            self.status_var.set(f"Loaded {info['saints_ref']} in Saints Concordance ({len(info['tokens'])} indexed words in the verse).")
        else:
            self.status_var.set(
                f"No indexed Concordance words for {info['saints_ref']} — click '⚡ Index Current Book' in Tab 5."
            )

    def _run_conc_job(self, label: str, work: Callable[[], Any], done: Callable[[Any], None]) -> None:
        """One Concordance build/export at a time; errors are shown, never swallowed."""
        if getattr(self, "_conc_job_running", False):
            messagebox.showinfo("Concordance busy", "A Concordance build or export is still running.", parent=self.root)
            return
        self._conc_job_running = True

        def _w() -> Any:
            try:
                return ("ok", work())
            except Exception as exc:  # shown below
                return ("err", exc)

        def _d(res: Any) -> None:
            self._conc_job_running = False
            status, val = res
            if status == "err":
                self.status_var.set(f"Error during {label}: {val}")
                messagebox.showerror("Concordance Error", str(val), parent=self.root)
                return
            done(val)

        self._run_bg(label, _w, _d)

    @staticmethod
    def _summarise_build(res: Dict[str, Any]) -> str:
        lines = []
        for lang, c in (res.get("languages") or {}).items():
            tok = int(c.get("tokens", 0)) or 1
            cont = int(c.get("content_words", c.get("indexed", 0)))
            func = int(c.get("function_words", 0))
            morph = int(c.get("with_morph", 0))
            extra_v = int(c.get("extra_site_verses", 0))
            dup_v = int(c.get("skipped_duplicate_verses", 0))
            dup_tok = int(c.get("tokens_in_duplicate_verses", 0))
            extra_note = f"; {extra_v:,} extra-site verses" if extra_v else ""
            dup_note = f"; {dup_v:,} dup/placeholder verses skipped ({dup_tok:,} words)" if dup_v else ""
            lines.append(
                f"• {lang.title()}: {c.get('indexed', 0):,} of {c.get('tokens', 0):,} words indexed "
                f"({100.0 * c.get('indexed', 0) / tok:.1f}% — {cont:,} content + {func:,} function); "
                f"{morph:,} parsed; {c.get('untagged', 0):,} untagged{extra_note}{dup_note}"
            )
        lines.append(f"• Colour-hub alignment units: {sum((res.get('alignments') or {}).values()):,}")
        if res.get("hub_links_missing"):
            lines.append(f"• Hub members not found: {len(res['hub_links_missing'])}")
        lines.append(f"• Time: {res.get('seconds', 0)} s")
        return "\n".join(lines)

    def _run_concordance_index_current_book(self) -> None:
        slug = self.current_book_slug.get()

        def _work() -> Dict[str, Any]:
            return self.engine.index_concordance_chapters(book_slug=slug)

        def _done(res: Dict[str, Any]) -> None:
            self._refresh_concordance_tab(select_concept_id=self.conc_selected_concept_id)
            self.status_var.set(f"Indexed {BOOKS_BY_SLUG[slug].title} (all three languages) in {res.get('seconds', 0)} s.")
            messagebox.showinfo(f"Concordance: {BOOKS_BY_SLUG[slug].title}", self._summarise_build(res), parent=self.root)

        self._run_conc_job(f"Indexing {BOOKS_BY_SLUG[slug].title} into the Saints Concordance", _work, _done)

    def _run_concordance_index_all(self) -> None:
        if not messagebox.askyesno(
            "Rebuild the whole Concordance",
            "Tag every saved Hebrew, Greek and Latin chapter with lemmas from the tagged editions, file each word "
            "under its Saints.Bible verse and rebuild the postings? Senses you set by hand are kept.",
            parent=self.root,
        ):
            return

        def _work() -> Dict[str, Any]:
            return self.engine.index_concordance_chapters(book_slug=None)

        def _done(res: Dict[str, Any]) -> None:
            self._refresh_concordance_tab(select_concept_id=self.conc_selected_concept_id)
            self.status_var.set(f"Concordance rebuilt in {res.get('seconds', 0)} s.")
            messagebox.showinfo("Saints Concordance rebuilt", self._summarise_build(res), parent=self.root)

        self._run_conc_job("Rebuilding the Saints Concordance", _work, _done)

    def _run_concordance_export(self) -> None:
        def _work() -> Dict[str, Any]:
            return self.engine.export_concordance_pack()

        def _done(res: Dict[str, Any]) -> None:
            self._refresh_concordance_telemetry()
            m = res.get("measured") or {}
            lines = []
            total = 0
            for lang in ("heb", "grc", "lat"):
                x = m.get(lang)
                if x:
                    total += int(x["gz_bytes"])
                    lines.append(
                        f"• saints-concordance-{lang}.json.gz: {x['gz_bytes'] / 1024.0:,.0f} KB — {x['lemmas']:,} lemmas, "
                        f"{x['roots']:,} roots, {x['indexed_tokens']:,} words (same postings by surface form: "
                        f"{x['surface_baseline_postings_gz_bytes'] / 1024.0:,.0f} KB)"
                    )
            if m.get("hubs"):
                total += int(m["hubs"]["gz_bytes"])
                lines.append(f"• saints-concordance-hubs.json.gz: {m['hubs']['gz_bytes'] / 1024.0:,.0f} KB")
            self.status_var.set(f"Exported Saints Concordance pack ({total / 1024.0:,.0f} KB gzip) -> {res['pack_dir']}")
            messagebox.showinfo(
                "Saints Concordance pack exported",
                f"Output folder:\n{res['pack_dir']}\n\n" + "\n".join(lines)
                + "\n• saints-concordance-decoder.js, manifest.json (attribution + note of changes), CONCORDANCE_REPORT.md",
                parent=self.root,
            )

        self._run_conc_job("Exporting the Saints Concordance pack", _work, _done)

    def _open_concordance_sense_modal(self) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title("Add / Update Trilingual Concept & Contextual Sense Offset")
        dlg.geometry("600x410")
        dlg.transient(self.root)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=14)
        frm.pack(fill="both", expand=True)

        g = self.conc_loaded_graph
        tc = g["concept"] if g else {}
        next_off = len(g["senses"]) + 1 if g else 1

        slug_v = tk.StringVar(value=str(tc.get("concept_slug", "ORIGIN_HEAD_START")))
        base_v = tk.StringVar(value=str(tc.get("eng_base_word", "head / origin")))
        col_v = tk.StringVar(value=str(tc.get("theme_colour") or ""))  # keep 'no colour' unless the user picks one
        off_v = tk.IntVar(value=next_off)
        word_v = tk.StringVar(value="")
        role_v = tk.StringVar(value="contextual_nuance")
        nuance_v = tk.StringVar(value="")

        fields = [
            ("Concept Slug:", ttk.Entry(frm, textvariable=slug_v, width=42)),
            ("English Core / Base Word:", ttk.Entry(frm, textvariable=base_v, width=42)),
            ("Saints Rainbow Colour:", ttk.Combobox(frm, textvariable=col_v, state="readonly", width=18,
                                                    values=["", "red", "orange", "yellow", "green", "blue", "indigo", "violet"])),
            ("Sense Offset # (1..64):", ttk.Spinbox(frm, from_=1, to=64, textvariable=off_v, width=10)),
            ("Contextual Saints Word (singular):", ttk.Entry(frm, textvariable=word_v, width=42)),
            ("Sense Role Tag:", ttk.Entry(frm, textvariable=role_v, width=42)),
            ("Usage Nuance (shown on tap):", ttk.Entry(frm, textvariable=nuance_v, width=52)),
        ]
        for idx, (lbl, wdg) in enumerate(fields):
            ttk.Label(frm, text=lbl, font=self.font_ui_bold).grid(row=idx, column=0, sticky="w", pady=4, padx=(0, 8))
            wdg.grid(row=idx, column=1, sticky="w", pady=4)

        ttk.Label(frm, text="Shared Concept Note:", font=self.font_ui_bold).grid(row=7, column=0, sticky="nw", pady=4)
        note_box = tk.Text(frm, height=4, width=44, wrap="word", font=self.font_ui)
        note_box.insert("1.0", str(tc.get("summary_note", "Shared meaning across Hebrew, Greek and Latin (the roots differ by language).")))
        note_box.grid(row=7, column=1, sticky="nsew", pady=4)

        def _save() -> None:
            if not word_v.get().strip():
                messagebox.showwarning("Missing Word", "Enter the contextual Saints base word (e.g., 'headwater').", parent=dlg)
                return
            out = self.engine.save_concordance_sense(
                concept_slug=slug_v.get(),
                eng_base_word=base_v.get(),
                summary_note=note_box.get("1.0", "end").strip(),
                sense_offset=int(off_v.get()),
                sense_base_word=word_v.get(),
                sense_role=role_v.get(),
                usage_nuance=nuance_v.get() or f"Contextual usage '{word_v.get().strip()}'",
                theme_colour=col_v.get() or None,
            )
            dlg.destroy()
            self._refresh_concordance_tab(select_concept_id=out["concept_id"])
            self._load_concordance_concept(out["concept_id"], active_sense_id=out["sense_id"])
            self.status_var.set(f"Saved Sense #{off_v.get()} '{word_v.get()}' under {slug_v.get()}.")

        ttk.Button(frm, text="✓ Save Concept & Sense Offset", style="Accent.TButton", command=_save).grid(
            row=8, column=0, columnspan=2, pady=(12, 0)
        )


def main() -> None:
    root = tk.Tk()
    CriticalTextDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
