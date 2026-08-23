#!/usr/bin/env python3
"""
Miu Robot Companion App GUI
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
import queue
from datetime import datetime
from miu_companion import MiuCompanionApp, MiuRobotController, AVAILABLE_COMMANDS, AVAILABLE_FACES

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("[WARNING] python-dotenv not installed. .env file will be ignored.")

class MiuGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Miu Robot Companion")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        self.robot_ip = os.getenv("MIU_ROBOT_IP", "192.168.1.1")
        self.miu_local = os.getenv("MIU_LOCAL", "false").lower() == "true"
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.tts_engine = tk.StringVar(value=os.getenv("TTS_ENGINE", "pyttsx3"))
        self.voice_enabled = tk.BooleanVar(value=True)
        self.wake_word_mode = tk.BooleanVar(value=os.getenv("WAKE_WORD_MODE", "false").lower() == "true")
        self.wake_word = os.getenv("WAKE_WORD", "hey miu")
        
        self.is_listening = False
        self.is_speaking = False
        self.app : MiuCompanionApp
        self.message_queue = queue.Queue()
        
        # Theme (Miu Captive Portal Theme)
        self.bg_color = "#09041c"        # Dark Navy/Space
        self.secondary_bg = "#11092b"    # Lighter space blue
        self.accent_color = "#a855f7"    # Neon Purple
        self.accent_secondary = "#38bdf8" # Light Blue
        self.text_color = "#e9d5ff"      # Light Purple Text
        self.success_color = "#4ade80"   # Neon Green
        self.error_color = "#f44336"     # Red
        
        self.setup_ui()
        self.start_backend()
        self.process_queue()
        
    def setup_ui(self):
        """Setup the user interface"""
        self.root.configure(bg=self.bg_color)
        self.root.attributes('-alpha', 0.93) # Glass blur effect simulation
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabel", background=self.bg_color, foreground=self.text_color, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("Accent.TButton", font=("Segoe UI", 12, "bold"))
        
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.create_status_bar(main_frame)
        
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.create_quick_actions(left_frame)
        
        center_frame = ttk.Frame(content_frame)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        self.create_chat_area(center_frame)
        
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.create_settings_panel(right_frame)
        
    def create_status_bar(self, parent):
        """Create the top status bar"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = ttk.Label(status_frame, text="MIU DESKTOP INTERFACE", font=("Segoe UI", 20, "bold"))
        title_label.pack(side=tk.LEFT)
        
        self.connection_label = ttk.Label(status_frame, text="[*] Disconnected", font=("Segoe UI", 10))
        self.connection_label.pack(side=tk.RIGHT, padx=10)
        
        self.robot_status_label = ttk.Label(status_frame, text="Status: Idle", font=("Segoe UI", 10))
        self.robot_status_label.pack(side=tk.RIGHT, padx=10)
        
    def create_quick_actions(self, parent):
        """Create quick action buttons panel"""
        label = ttk.Label(parent, text="Quick Actions", font=("Segoe UI", 12, "bold"))
        label.pack(pady=(0, 10))
        
        commands = [
            ("Wave", "wave"),
            ("Dance", "dance"),
            ("Walk", "walk"),
            ("Rest", "rest"),
            ("Pushup", "pushup"),
            ("Crab Walk", "crab"),
            ("Swim", "swim"),
            ("Bow", "bow"),
            ("Stop", "stop"),
        ]
        
        for text, command in commands:
            btn = tk.Button(
                parent,
                text=text,
                command=lambda cmd=command: self.send_quick_command(cmd),
                bg=self.secondary_bg,
                fg=self.text_color,
                activebackground=self.accent_color,
                font=("Segoe UI", 10),
                relief=tk.FLAT,
                padx=10,
                pady=8,
                cursor="hand2"
            )
            btn.pack(fill=tk.X, pady=2)
            
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        refresh_btn = tk.Button(
            parent,
            text="Refresh Status",
            command=self.refresh_status,
            bg=self.secondary_bg,
            fg=self.text_color,
            activebackground=self.accent_color,
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            padx=10,
            pady=5
        )
        refresh_btn.pack(fill=tk.X)
        
    def create_chat_area(self, parent):
        """Create the main chat interface"""
        chat_frame = ttk.Frame(parent)
        chat_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(chat_frame, text="Conversation", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self.secondary_bg,
            fg=self.text_color,
            insertbackground=self.text_color,
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        self.chat_display.config(state=tk.DISABLED)
        
        self.chat_display.tag_config("user", foreground="#64b5f6", font=("Consolas", 10, "bold"))
        self.chat_display.tag_config("miu", foreground=self.accent_color, font=("Consolas", 10, "bold"))
        self.chat_display.tag_config("system", foreground="#aaaaaa", font=("Consolas", 9, "italic"))
        self.chat_display.tag_config("error", foreground=self.error_color)
        self.chat_display.tag_config("success", foreground=self.success_color)
        
        input_frame = ttk.Frame(parent)
        input_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.input_entry = tk.Entry(
            input_frame,
            font=("Segoe UI", 11),
            bg=self.secondary_bg,
            fg=self.text_color,
            insertbackground=self.text_color,
            relief=tk.FLAT
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 5))
        self.input_entry.bind("<Return>", lambda e: self.send_message())
        
        self.mic_button = tk.Button(
            input_frame,
            text="MIC",
            command=self.toggle_listening,
            bg=self.accent_color,
            fg="white",
            activebackground=self.accent_color,
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
            width=4,
            cursor="hand2"
        )
        self.mic_button.pack(side=tk.LEFT, padx=(0, 5))
        
        send_button = tk.Button(
            input_frame,
            text="Send",
            command=self.send_message,
            bg=self.accent_color,
            fg="white",
            activebackground=self.accent_color,
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
            padx=15,
            cursor="hand2"
        )
        send_button.pack(side=tk.LEFT)
        
    def create_settings_panel(self, parent):
        """Create settings and info panel"""
        ttk.Label(parent, text="Settings", font=("Segoe UI", 12, "bold")).pack(pady=(0, 10))
        
        voice_check = tk.Checkbutton(
            parent,
            text="Voice Mode",
            variable=self.voice_enabled,
            command=self.toggle_voice_mode,
            bg=self.bg_color,
            fg=self.text_color,
            selectcolor=self.secondary_bg,
            activebackground=self.bg_color,
            activeforeground=self.text_color,
            font=("Segoe UI", 10)
        )
        voice_check.pack(anchor=tk.W, pady=5)
        
        wake_check = tk.Checkbutton(
            parent,
            text=f"Wake Word Mode ({self.wake_word})",
            variable=self.wake_word_mode,
            command=self.toggle_wake_word_mode,
            bg=self.bg_color,
            fg=self.text_color,
            selectcolor=self.secondary_bg,
            activebackground=self.bg_color,
            activeforeground=self.text_color,
            font=("Segoe UI", 10)
        )
        wake_check.pack(anchor=tk.W, pady=5)
        
        ttk.Label(parent, text="TTS Engine:", font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(10, 2))
        
        tts_frame = ttk.Frame(parent)
        tts_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(
            tts_frame,
            text="pyttsx3 (Fast)",
            variable=self.tts_engine,
            value="pyttsx3",
            command=self.change_tts_engine
        ).pack(anchor=tk.W)
        
        ttk.Radiobutton(
            tts_frame,
            text="Gemini (Natural)",
            variable=self.tts_engine,
            value="gemini",
            command=self.change_tts_engine
        ).pack(anchor=tk.W)
        
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        
        ttk.Label(parent, text="Robot Info", font=("Segoe UI", 12, "bold")).pack(pady=(0, 10))
        
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X)
        
        ttk.Label(info_frame, text="IP:", font=("Segoe UI", 9)).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.ip_label = ttk.Label(info_frame, text=self.robot_ip, font=("Segoe UI", 9, "bold"))
        self.ip_label.grid(row=0, column=1, sticky=tk.W, pady=2, padx=5)
        
        ttk.Label(info_frame, text="Face:", font=("Segoe UI", 9)).grid(row=1, column=0, sticky=tk.W, pady=2)
        self.face_label = ttk.Label(info_frame, text="unknown", font=("Segoe UI", 9, "bold"))
        self.face_label.grid(row=1, column=1, sticky=tk.W, pady=2, padx=5)
        
        ttk.Label(info_frame, text="Command:", font=("Segoe UI", 9)).grid(row=2, column=0, sticky=tk.W, pady=2)
        self.command_label = ttk.Label(info_frame, text="none", font=("Segoe UI", 9, "bold"))
        self.command_label.grid(row=2, column=1, sticky=tk.W, pady=2, padx=5)
        
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        
        ttk.Label(parent, text="Available Commands", font=("Segoe UI", 10, "bold")).pack(pady=(0, 5))
        
        commands_text = scrolledtext.ScrolledText(
            parent,
            height=8,
            wrap=tk.WORD,
            font=("Consolas", 8),
            bg=self.secondary_bg,
            fg=self.text_color,
            relief=tk.FLAT
        )
        commands_text.pack(fill=tk.BOTH)
        commands_text.insert(tk.END, ", ".join(AVAILABLE_COMMANDS))
        commands_text.config(state=tk.DISABLED)
        
    def start_backend(self):
        """Initialize the backend app in a separate thread"""
        def init_app():
            try:
                self.app = MiuCompanionApp(
                    robot_ip=self.robot_ip,
                    miu_local=False,
                    gemini_api_key=self.api_key,
                    voice_enabled=self.voice_enabled.get(),
                    tts_engine=self.tts_engine.get(),
                    wake_word=self.wake_word,
                    wake_word_mode=self.wake_word_mode.get(),
                    gemini_model=self.gemini_model
                )
                self.message_queue.put(("system", "[OK] Backend initialized"))
                self.check_connection()
            except Exception as e:
                self.message_queue.put(("error", f"Failed to initialize: {e}"))
        
        thread = threading.Thread(target=init_app, daemon=True)
        thread.start()
        
    def check_connection(self):
        """Check robot connection status"""
        if not self.app:
            return
            
        def check():
            try:
                status = self.app.robot.get_status()
                if "error" in status:
                    self.message_queue.put(("connection", False))
                else:
                    self.message_queue.put(("connection", True))
                    self.message_queue.put(("status", status))
            except Exception as e:
                self.message_queue.put(("connection", False))
        
        thread = threading.Thread(target=check, daemon=True)
        thread.start()
        
    def send_message(self):
        """Send a text message"""
        message = self.input_entry.get().strip()
        if not message:
            return
            
        self.input_entry.delete(0, tk.END)
        self.add_message("user", message)
        
        def process():
            try:
                response, interpretation = self.app.process_input(message)
                self.message_queue.put(("miu", interpretation.get("response", response)))
                
                if self.voice_enabled.get() and "response" in interpretation:
                    face = interpretation.get("face") if not interpretation.get("command") else None
                    self.app.voice.speak(
                        interpretation["response"],
                        async_mode=True,
                        face=face,
                        robot_controller=self.app.robot
                    )
            except Exception as e:
                self.message_queue.put(("error", f"Error: {e}"))
        
        thread = threading.Thread(target=process, daemon=True)
        thread.start()
        
    def toggle_listening(self):
        """Toggle voice listening"""
        if not self.voice_enabled.get():
            self.add_message("system", "Voice mode is disabled. Enable it in settings.")
            return
        
        if self.wake_word_mode.get():
            self.add_message("system", f"Wake word mode is active. Say '{self.wake_word}' to trigger listening.")
            return
            
        if self.is_listening:
            return
            
        self.is_listening = True
        self.mic_button.config(bg=self.error_color, text="STOP")
        self.add_message("system", "Listening...")
        
        def listen():
            try:
                text = self.app.voice.listen()
                if text:
                    self.message_queue.put(("voice_input", text))
                else:
                    self.message_queue.put(("system", "No speech detected"))
            except Exception as e:
                self.message_queue.put(("error", f"Voice error: {e}"))
            finally:
                self.message_queue.put(("listening_done", None))
        
        thread = threading.Thread(target=listen, daemon=True)
        thread.start()
        
    def send_quick_command(self, command):
        """Send a quick command"""
        self.add_message("system", f"Executing: {command}")
        
        def execute():
            try:
                result = self.app.robot.send_command(command)
                if "error" in result:
                    self.message_queue.put(("error", f"Command failed: {result['error']}"))
                else:
                    self.message_queue.put(("success", f"[OK] {command} executed"))
                    self.refresh_status()
            except Exception as e:
                self.message_queue.put(("error", f"Error: {e}"))
        
        thread = threading.Thread(target=execute, daemon=True)
        thread.start()
        
    def refresh_status(self):
        """Refresh robot status"""
        self.check_connection()
        
    def toggle_voice_mode(self):
        """Toggle voice mode"""
        if self.app:
            self.app.voice_mode = self.voice_enabled.get()
            self.app.voice.voice_enabled = self.voice_enabled.get()
        status = "enabled" if self.voice_enabled.get() else "disabled"
        self.add_message("system", f"Voice mode {status}")
    
    def toggle_wake_word_mode(self):
        """Toggle wake word mode"""
        if self.app:
            self.app.wake_word_mode = self.wake_word_mode.get()
        status = "enabled" if self.wake_word_mode.get() else "disabled"
        self.add_message("system", f"Wake word mode {status}")
        
        if self.wake_word_mode.get():
            self.add_message("system", f"Say '{self.wake_word}' to activate listening")
            self.start_wake_word_listener()
        
    def change_tts_engine(self):
        """Change TTS engine"""
        if self.app:
            self.app.voice.tts_engine_type = self.tts_engine.get()
            self.app.tts_engine = self.tts_engine.get()
        self.add_message("system", f"TTS engine: {self.tts_engine.get()}")
    
    def start_wake_word_listener(self):
        """Start continuous wake word listening"""
        def listen_loop():
            while self.wake_word_mode.get() and self.voice_enabled.get():
                try:
                    if self.app.voice.listen_for_wake_word(timeout=10):
                        self.message_queue.put(("system", "Wake word detected! Listening for command..."))
                        text = self.app.voice.listen(timeout=10)
                        if text:
                            self.message_queue.put(("voice_input", text))
                        else:
                            self.message_queue.put(("system", "No command received"))
                except Exception as e:
                    self.message_queue.put(("error", f"Wake word error: {e}"))
                    break
        
        if self.wake_word_mode.get():
            thread = threading.Thread(target=listen_loop, daemon=True)
            thread.start()
        
    def add_message(self, sender, message):
        """Add a message to the chat display"""
        self.chat_display.config(state=tk.NORMAL)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if sender == "user":
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "system")
            self.chat_display.insert(tk.END, "You: ", "user")
            self.chat_display.insert(tk.END, f"{message}\n")
        elif sender == "miu":
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "system")
            self.chat_display.insert(tk.END, "Miu: ", "miu")
            self.chat_display.insert(tk.END, f"{message}\n")
        elif sender == "system":
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "system")
            self.chat_display.insert(tk.END, f"{message}\n", "system")
        elif sender == "error":
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "system")
            self.chat_display.insert(tk.END, f"[ERROR] {message}\n", "error")
        elif sender == "success":
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "system")
            self.chat_display.insert(tk.END, f"{message}\n", "success")
        
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
        
    def process_queue(self):
        """Process messages from background threads"""
        try:
            while True:
                msg_type, data = self.message_queue.get_nowait()
                
                if msg_type in ["user", "miu", "system", "error", "success"]:
                    self.add_message(msg_type, data)
                elif msg_type == "connection":
                    if data:
                        self.connection_label.config(text="[+] Connected", foreground=self.success_color)
                    else:
                        self.connection_label.config(text="[-] Disconnected", foreground=self.error_color)
                elif msg_type == "status":
                    self.face_label.config(text=data.get("currentFace", "unknown"))
                    self.command_label.config(text=data.get("currentCommand", "none") or "none")
                    self.robot_status_label.config(text=f"Status: {data.get('currentCommand', 'Idle')}")
                elif msg_type == "voice_input":
                    self.add_message("user", f"[VOICE] {data}")
                    self.input_entry.insert(0, data)
                    self.send_message()
                elif msg_type == "listening_done":
                    self.is_listening = False
                    self.mic_button.config(bg=self.accent_color, text="MIC")
                    
        except queue.Empty:
            pass
        
        self.root.after(100, self.process_queue)


def main():
    """Main entry point"""
    root = tk.Tk()
    app = MiuGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
