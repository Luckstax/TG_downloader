"""
Telegram Channel Video Downloader - GUI
Requisitos: pip install -r requirements.txt

Configuração:
    Preencha os dados na tela de "Configurações" dentro do programa
    (botão de engrenagem, canto superior direito) — isso salva um
    arquivo .env na mesma pasta do script. Você também pode copiar
    .env.example para .env e editar manualmente.
"""

import asyncio
import os
import re
import threading
import time
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from pathlib import Path

from dotenv import load_dotenv, set_key
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeFilename

# ─── CONFIG (.env) ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

if not ENV_PATH.exists():
    ENV_PATH.touch()

load_dotenv(ENV_PATH)

CONFIG_FIELDS = ["API_ID", "API_HASH", "CHANNEL", "LIMIT", "OUTPUT", "SESSION"]


def get_config():
    """Lê a configuração atual das variáveis de ambiente (recarregadas do .env)."""
    load_dotenv(ENV_PATH, override=True)
    limit_raw = os.getenv("LIMIT", "").strip()
    return {
        "API_ID": os.getenv("API_ID", "").strip(),
        "API_HASH": os.getenv("API_HASH", "").strip(),
        "CHANNEL": os.getenv("CHANNEL", "").strip(),
        "LIMIT": int(limit_raw) if limit_raw.isdigit() else None,
        "OUTPUT": os.getenv("OUTPUT", "").strip(),
        "SESSION": os.getenv("SESSION", "tg_session").strip() or "tg_session",
    }


def save_config(values: dict):
    """Salva os valores no .env (cria o arquivo se não existir)."""
    for key in CONFIG_FIELDS:
        set_key(str(ENV_PATH), key, str(values.get(key, "") or ""))


def config_is_complete(cfg):
    missing = [k for k in ("API_ID", "API_HASH", "CHANNEL", "OUTPUT") if not cfg.get(k)]
    return not missing, missing


# ──────────────────────────────────────────────────────────────────────────────

BG       = "#1e1e2e"
FRAME_BG = "#2a2a3e"
FG       = "#cdd6f4"
ACCENT   = "#89b4fa"
GREEN    = "#a6e3a1"
RED      = "#f38ba8"
MUTED    = "#6c7086"
SURFACE  = "#181825"


def slugify(text, max_len=60):
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:max_len].strip("_")


def is_video(msg):
    if msg.video:
        return True
    if msg.document and msg.document.attributes:
        if any(isinstance(a, DocumentAttributeVideo) for a in msg.document.attributes):
            return True
    if msg.document and msg.document.mime_type:
        return msg.document.mime_type.startswith("video/")
    return False


def get_extension(msg):
    if msg.document and msg.document.attributes:
        for attr in msg.document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                _, ext = os.path.splitext(attr.file_name)
                if ext:
                    return ext.lower()
    if msg.document and msg.document.mime_type:
        ext = msg.document.mime_type.split("/")[-1]
        return ".mkv" if ext in ("x-matroska", "mkv") else f".{ext}"
    return ".mp4"


def build_filename(msg):
    caption = slugify((msg.text or "").strip())
    ext = get_extension(msg)
    return f"{caption}{ext}" if caption else f"video_{msg.id}{ext}"


def _fmt(seconds):
    """Formata segundos em HH:MM:SS ou MM:SS."""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


# ── Tela de Configurações ───────────────────────────────────────────────────

class SettingsWindow(tk.Toplevel):
    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.title("Configurações")
        self.geometry("480x420")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.transient(master)
        self.grab_set()
        self.on_saved = on_saved
        self.entries = {}
        self._build_ui()
        self._load_current()

    def _field(self, parent, label, key, help_text=None, show=None):
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="x", pady=(0, 10))
        tk.Label(wrap, text=label, font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=FG, anchor="w").pack(fill="x")
        if help_text:
            tk.Label(wrap, text=help_text, font=("Segoe UI", 8),
                     bg=BG, fg=MUTED, anchor="w", justify="left",
                     wraplength=440).pack(fill="x")
        entry = tk.Entry(wrap, font=("Consolas", 10), bg=FRAME_BG, fg=FG,
                          insertbackground=FG, relief="flat", show=show)
        entry.pack(fill="x", ipady=4, pady=(4, 0))
        self.entries[key] = entry

    def _build_ui(self):
        P = 16
        tk.Label(self, text="Configurações", font=("Segoe UI", 13, "bold"),
                 bg=BG, fg=ACCENT).pack(pady=(P, 10))

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=P)

        self._field(body, "API_ID", "API_ID",
                    "Número da sua app, obtido em https://my.telegram.org")
        self._field(body, "API_HASH", "API_HASH",
                    "Hash da sua app (mesma página acima).", show="*")
        self._field(body, "Canal", "CHANNEL",
                    "Ex: @nomedocanal")
        self._field(body, "Limite de mensagens (opcional)", "LIMIT",
                    "Deixe vazio para escanear o canal inteiro.")
        self._field(body, "Pasta de saída", "OUTPUT",
                    "Onde os vídeos baixados serão salvos.")
        self._field(body, "Arquivo de sessão", "SESSION",
                    "Nome/caminho do arquivo de sessão do Telethon (sem .session).")

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=P, pady=P)

        tk.Button(btn_row, text="Salvar", font=("Segoe UI", 10, "bold"),
                  bg=ACCENT, fg=BG, relief="flat", padx=16, pady=6,
                  cursor="hand2", command=self._save).pack(side="right")
        tk.Button(btn_row, text="Cancelar", font=("Segoe UI", 10),
                  bg="#45475a", fg=FG, relief="flat", padx=16, pady=6,
                  cursor="hand2", command=self.destroy).pack(side="right", padx=(0, 8))

    def _load_current(self):
        cfg = get_config()
        self.entries["API_ID"].insert(0, cfg["API_ID"])
        self.entries["API_HASH"].insert(0, cfg["API_HASH"])
        self.entries["CHANNEL"].insert(0, cfg["CHANNEL"])
        self.entries["LIMIT"].insert(0, "" if cfg["LIMIT"] is None else str(cfg["LIMIT"]))
        self.entries["OUTPUT"].insert(0, cfg["OUTPUT"])
        self.entries["SESSION"].insert(0, cfg["SESSION"])

    def _save(self):
        values = {k: e.get().strip() for k, e in self.entries.items()}

        if values["API_ID"] and not values["API_ID"].isdigit():
            messagebox.showerror("Configurações", "API_ID deve ser numérico.", parent=self)
            return
        for required in ("API_ID", "API_HASH", "CHANNEL", "OUTPUT"):
            if not values[required]:
                messagebox.showerror(
                    "Configurações",
                    f"O campo '{required}' é obrigatório.", parent=self)
                return

        save_config(values)
        messagebox.showinfo("Configurações", "Salvo com sucesso.", parent=self)
        if self.on_saved:
            self.on_saved()
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Telegram Video Downloader")
        self.geometry("600x540")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._skip = False
        self._build_ui()
        self._refresh_status()

    def _build_ui(self):
        P = 14

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=P, pady=(P, 0))

        tk.Label(header, text="Telegram Video Downloader",
                 font=("Segoe UI", 13, "bold"), bg=BG, fg=ACCENT
                 ).pack(side="left")

        tk.Button(header, text="⚙ Configurações", font=("Segoe UI", 9),
                  bg="#45475a", fg=FG, relief="flat", padx=10, pady=4,
                  cursor="hand2", command=self._open_settings
                  ).pack(side="right")

        self.lbl_status = tk.Label(self, text="", font=("Segoe UI", 8),
                                    bg=BG, fg=MUTED)
        self.lbl_status.pack(fill="x", padx=P, pady=(4, 8))

        # ── Progresso Geral ──────────────────────────────────────────────────
        f1 = tk.Frame(self, bg=FRAME_BG, padx=P, pady=12)
        f1.pack(fill="x", padx=P, pady=(0, 8))

        tk.Label(f1, text="PROGRESSO GERAL", font=("Segoe UI", 8, "bold"),
                 bg=FRAME_BG, fg=MUTED).pack(anchor="w")

        self.lbl_overall = tk.Label(f1, text="Aguardando...",
                                     font=("Segoe UI", 10), bg=FRAME_BG, fg=FG)
        self.lbl_overall.pack(anchor="w", pady=(2, 6))

        row1 = tk.Frame(f1, bg=FRAME_BG)
        row1.pack(fill="x")
        self.bar_overall = ttk.Progressbar(row1, mode="determinate")
        self.bar_overall.pack(side="left", fill="x", expand=True)
        self.lbl_overall_pct = tk.Label(row1, text=" 0%", width=5,
                                         font=("Segoe UI", 9, "bold"),
                                         bg=FRAME_BG, fg=ACCENT)
        self.lbl_overall_pct.pack(side="right")

        # ── Download Atual ───────────────────────────────────────────────────
        f2 = tk.Frame(self, bg=FRAME_BG, padx=P, pady=12)
        f2.pack(fill="x", padx=P, pady=(0, 8))

        tk.Label(f2, text="DOWNLOAD ATUAL", font=("Segoe UI", 8, "bold"),
                 bg=FRAME_BG, fg=MUTED).pack(anchor="w")

        self.lbl_filename = tk.Label(f2, text="—",
                                      font=("Consolas", 9), bg=FRAME_BG, fg=FG,
                                      wraplength=540, justify="left")
        self.lbl_filename.pack(anchor="w", pady=(2, 6))

        row2 = tk.Frame(f2, bg=FRAME_BG)
        row2.pack(fill="x")
        self.bar_current = ttk.Progressbar(row2, mode="determinate")
        self.bar_current.pack(side="left", fill="x", expand=True)
        self.lbl_current_pct = tk.Label(row2, text=" 0%", width=5,
                                         font=("Segoe UI", 9, "bold"),
                                         bg=FRAME_BG, fg=ACCENT)
        self.lbl_current_pct.pack(side="right")

        info = tk.Frame(f2, bg=FRAME_BG)
        info.pack(fill="x", pady=(6, 0))
        self.lbl_mb = tk.Label(info, text="0.0 / 0.0 MB",
                                font=("Segoe UI", 9), bg=FRAME_BG, fg=MUTED)
        self.lbl_mb.pack(side="left")
        self.lbl_speed = tk.Label(info, text="— MB/s",
                                   font=("Segoe UI", 10, "bold"), bg=FRAME_BG, fg=GREEN)
        self.lbl_speed.pack(side="right")

        time_row = tk.Frame(f2, bg=FRAME_BG)
        time_row.pack(fill="x", pady=(2, 0))
        self.lbl_elapsed = tk.Label(time_row, text="Decorrido: —",
                                     font=("Segoe UI", 9), bg=FRAME_BG, fg=MUTED)
        self.lbl_elapsed.pack(side="left")
        self.lbl_eta = tk.Label(time_row, text="Faltam: —",
                                 font=("Segoe UI", 9), bg=FRAME_BG, fg=MUTED)
        self.lbl_eta.pack(side="right")

        # ── Botões ────────────────────────────────────────────────────────────
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(pady=(0, P))

        self.btn = tk.Button(btn_row, text="▶  Iniciar Download",
                              font=("Segoe UI", 10, "bold"),
                              bg=ACCENT, fg=BG, relief="flat",
                              padx=20, pady=8, cursor="hand2",
                              command=self._on_click)
        self.btn.pack(side="left", padx=(0, 8))

        self.btn_skip = tk.Button(btn_row, text="⏭  Pular",
                                   font=("Segoe UI", 10, "bold"),
                                   bg="#45475a", fg=FG, relief="flat",
                                   padx=16, pady=8, cursor="hand2",
                                   state="disabled",
                                   command=self._on_skip)
        self.btn_skip.pack(side="left")

        # ── Log ──────────────────────────────────────────────────────────────
        log_frame = tk.Frame(self, bg=SURFACE)
        log_frame.pack(fill="both", expand=True, padx=P, pady=(0, 8))

        self.log_box = tk.Text(log_frame, bg=SURFACE, fg=MUTED,
                                font=("Consolas", 8), bd=0,
                                state="disabled", relief="flat", wrap="word")
        sb = ttk.Scrollbar(log_frame, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_box.pack(fill="both", expand=True, padx=6, pady=6)

    # ── configurações ────────────────────────────────────────────────────────

    def _open_settings(self):
        SettingsWindow(self, on_saved=self._refresh_status)

    def _refresh_status(self):
        cfg = get_config()
        ok, missing = config_is_complete(cfg)
        if ok:
            self.lbl_status.configure(
                text=f"Canal: {cfg['CHANNEL']}   •   Saída: {cfg['OUTPUT']}",
                fg=MUTED)
        else:
            self.lbl_status.configure(
                text=f"Configuração incompleta — faltam: {', '.join(missing)}. "
                     f"Clique em ⚙ Configurações.",
                fg=RED)

    # ── helpers thread-safe ──────────────────────────────────────────────────

    def log(self, msg, color=None):
        def _():
            self.log_box.configure(state="normal")
            if color:
                tag = f"t{color.replace('#','')}"
                self.log_box.tag_configure(tag, foreground=color)
                self.log_box.insert("end", msg + "\n", tag)
            else:
                self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _)

    def set_overall(self, done, total, label=None):
        def _():
            pct = (done / total * 100) if total else 0
            self.bar_overall["maximum"] = max(total, 1)
            self.bar_overall["value"] = done
            self.lbl_overall_pct.configure(text=f"{pct:.0f}%")
            self.lbl_overall.configure(text=label or f"{done} de {total} vídeos")
        self.after(0, _)

    def set_current(self, fname, cur, tot, speed, elapsed=0, eta=0):
        def _():
            pct = (cur / tot * 100) if tot else 0
            self.bar_current["maximum"] = max(tot, 1)
            self.bar_current["value"] = cur
            self.lbl_current_pct.configure(text=f"{pct:.0f}%")
            self.lbl_filename.configure(text=fname)
            self.lbl_mb.configure(text=f"{cur/1048576:.1f} / {tot/1048576:.1f} MB")
            self.lbl_speed.configure(
                text=f"{speed/1048576:.2f} MB/s" if speed > 0 else "— MB/s")
            self.lbl_elapsed.configure(text=f"Decorrido: {_fmt(elapsed)}")
            self.lbl_eta.configure(text=f"Faltam: {_fmt(eta) if speed > 0 else '—'}")
        self.after(0, _)

    def ask(self, title, prompt, show=None):
        result = {"v": None}
        ev = threading.Event()
        def _():
            result["v"] = simpledialog.askstring(title, prompt, parent=self, show=show)
            ev.set()
        self.after(0, _)
        ev.wait()
        return result["v"]

    def _enable_btn(self):
        self.after(0, lambda: self.btn.configure(
            state="normal", text="▶  Iniciar Download"))
        self.after(0, lambda: self.btn_skip.configure(state="disabled", bg="#45475a"))

    def _on_skip(self):
        self._skip = True
        self.after(0, lambda: self.btn_skip.configure(state="disabled", bg="#45475a"))
        self.log("[⏭] Pulando para o próximo vídeo...", MUTED)

    # ── click / thread ───────────────────────────────────────────────────────

    def _on_click(self):
        cfg = get_config()
        ok, missing = config_is_complete(cfg)
        if not ok:
            messagebox.showwarning(
                "Configuração incompleta",
                f"Preencha antes: {', '.join(missing)}.\n\n"
                f"Clique em ⚙ Configurações.")
            return

        self.btn.configure(state="disabled", text="Em andamento...")
        self.log("Iniciando...", ACCENT)
        threading.Thread(target=self._worker, args=(cfg,), daemon=True).start()

    def _worker(self, cfg):
        try:
            import sys
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            asyncio.run(self._run(cfg))
        except Exception as e:
            import traceback
            self.log(f"ERRO: {e}", RED)
            self.log(traceback.format_exc(), RED)
            self._enable_btn()

    # ── async ─────────────────────────────────────────────────────────────────

    async def _run(self, cfg):
        api_id   = int(cfg["API_ID"])
        api_hash = cfg["API_HASH"]
        channel  = cfg["CHANNEL"]
        limit    = cfg["LIMIT"]
        output   = cfg["OUTPUT"]
        session  = cfg["SESSION"]

        os.makedirs(output, exist_ok=True)
        self.log("Conectando ao Telegram...")

        async with TelegramClient(
                session, api_id, api_hash,
                flood_sleep_threshold=0,
                request_retries=5,
        ) as client:

            if not await client.is_user_authorized():
                phone = self.ask("Login", "Número (ex: +5511999999999):")
                if not phone:
                    self.log("Cancelado.", RED)
                    self._enable_btn()
                    return
                await client.send_code_request(phone)
                code = self.ask("Código", "Código recebido no Telegram:")
                try:
                    await client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    pw = self.ask("2FA", "Senha de dois fatores:", show="*")
                    await client.sign_in(password=pw)

            me = await client.get_me()
            self.log(f"Logado: {me.first_name}", GREEN)

            self.set_overall(0, 0, "Escaneando canal...")
            self.log("Contando vídeos...")

            video_ids = []
            async for msg in client.iter_messages(channel, limit=limit):
                if is_video(msg):
                    video_ids.append(msg.id)

            video_ids.reverse()
            total = len(video_ids)
            self.log(f"Encontrados {total} vídeos.", ACCENT)
            self.set_overall(0, total)

            downloaded = skipped = errors = 0

            for i, msg_id in enumerate(video_ids, 1):
                # Busca a mensagem fresca pra referência não expirar
                msg = await client.get_messages(channel, ids=msg_id)
                if not msg:
                    continue
                filename = build_filename(msg)
                path     = os.path.join(output, filename)
                tmp_path = path + ".tmp"

                if os.path.exists(path):
                    self.log(f"[SKIP] {filename}", MUTED)
                    skipped += 1
                    self.set_overall(i, total)
                    continue

                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except PermissionError:
                        self.log(f"[!] .tmp bloqueado por outro processo, pulando: {filename}", RED)
                        self.set_overall(i, total)
                        continue

                self.log(f"[↓] [{i}/{total}] {filename}", ACCENT)
                self.set_current(filename, 0, 1, 0)
                self._skip = False
                self.after(0, lambda: self.btn_skip.configure(
                    state="normal", bg="#f38ba8"))

                sd = {"last": 0, "t": time.time(), "start": time.time(), "speed": 0.0}

                def make_cb(fn, s):
                    def cb(cur, tot):
                        now = time.time()
                        dt  = now - s["t"]
                        elapsed = now - s["start"]
                        if dt >= 0.5:
                            s["speed"] = (cur - s["last"]) / dt
                            s["last"]  = cur
                            s["t"]     = now
                            eta = (tot - cur) / s["speed"] if s["speed"] > 0 else 0
                            self.set_current(fn, cur, tot, s["speed"], elapsed, eta)
                        if self._skip:
                            raise Exception("skip")
                    return cb

                try:
                    await msg.download_media(file=tmp_path,
                                             progress_callback=make_cb(filename, sd))

                    if self._skip:
                        self.log(f"[⏭] Pulado: {filename}", MUTED)
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                        self._skip = False
                        self.set_overall(i, total)
                        self.after(0, lambda: self.btn_skip.configure(
                            state="disabled", bg="#45475a"))
                        continue
                    os.rename(tmp_path, path)
                    downloaded += 1
                    self.log(f"[✓] {filename}", GREEN)
                except Exception as e:
                    errors += 1
                    self.log(f"[✗] Erro: {e}", RED)
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

                self.set_overall(i, total)

            summary = (f"Concluído! ✓{downloaded} baixados  "
                       f"↷{skipped} pulados  ✗{errors} erros")
            self.log(summary, GREEN)
            self.set_overall(total, total, summary)

        self._enable_btn()


if __name__ == "__main__":
    app = App()
    app.mainloop()
