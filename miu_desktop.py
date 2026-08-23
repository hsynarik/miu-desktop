#!/usr/bin/env python3
import os
import sys
import time
import math
import cv2
import requests
import pyaudio
import speech_recognition as sr
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QTextEdit, QGridLayout, QFrame, QSizePolicy,
    QStackedWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtGui import QImage, QPixmap, QColor, QPalette, QFont
from PyQt5.QtWebEngineWidgets import QWebEngineView

# Companion app imports
from miu_companion import MiuCompanionApp

class CameraThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    capture_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.cap = None
        self.trigger_capture = False
        
    def run(self):
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap or not self.cap.isOpened():
                print("[CameraThread] No camera found or failed to open.")
                return
            self.running = True
            while self.running and self.cap.isOpened():
                ret, cv_img = self.cap.read()
                if ret:
                    cv_img = cv2.flip(cv_img, 1)
                    
                    if self.trigger_capture:
                        self.trigger_capture = False
                        if not os.path.exists("photos"):
                            os.makedirs("photos")
                        filename = f"photos/miu_photo_{int(time.time())}.jpg"
                        cv2.imwrite(filename, cv_img)
                        self.capture_signal.emit(filename)
                    
                    rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_image.shape
                    bytes_per_line = ch * w
                    convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                    self.change_pixmap_signal.emit(convert_to_Qt_format)
                time.sleep(0.03) # ~30 fps
        except Exception as e:
            print(f"[CameraThread] Error: {e}")
        finally:
            if self.cap and self.cap.isOpened():
                self.cap.release()
            
    def stop(self):
        self.running = False
        self.wait(2000)
        if self.cap and self.cap.isOpened():
            self.cap.release()

class PartyThread(QThread):
    beat_signal = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.running = False
        
    def run(self):
        self.running = True
        CHUNK = 1024
        RATE = 44100
        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)
            last_beat = 0
            while self.running:
                data = stream.read(CHUNK, exception_on_overflow=False)
                count = len(data)/2
                import struct
                format = "%dh" % (count)
                shorts = struct.unpack(format, data)
                sum_squares = 0.0
                for sample in shorts:
                    n = sample * (1.0/32768)
                    sum_squares += n*n
                rms = math.sqrt(sum_squares / count) * 10000 
                
                if rms > 800:
                    now = time.time()
                    if now - last_beat > 0.5:
                        last_beat = now
                        self.beat_signal.emit()
        except Exception as e:
            print("Party Mode Error:", e)
        finally:
            if 'stream' in locals():
                stream.stop_stream()
                stream.close()
            p.terminate()

    def stop(self):
        self.running = False
        self.wait()

class ChatWorker(QThread):
    response_signal = pyqtSignal(str, str)
    def __init__(self, app_backend, text):
        super().__init__()
        self.app_backend = app_backend
        self.text = text
        
    def run(self):
        try:
            response, command = self.app_backend.process_input(self.text)
            
            # command might be a dict e.g. {"command": "wave"}
            if isinstance(command, dict):
                command = command.get("command", "") or command.get("action", "") or str(command)
                
            self.response_signal.emit(response, command if command else "")
        except Exception as e:
            self.response_signal.emit(f"Hata: {e}", "")

class MiuMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Miu Arch GUI")
        self.setGeometry(100, 100, 1600, 900)
        
        self.robot_ip = os.getenv("MIU_ROBOT_IP", "192.168.4.1")
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.app_backend = None
        
        # Threads
        self.cam_thread = None
        self.party_thread = None
        
        # Thread references to prevent GC crashes
        self.active_workers = []
        
        # Polling Timer for Touch Shutter
        self.touch_timer = QTimer(self)
        self.touch_timer.timeout.connect(self.poll_touch)
        
        self.setup_ui()
        self.apply_theme()
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- LEFT PANEL (50%) ---
        self.left_panel = QFrame()
        self.left_panel.setStyleSheet("background-color: #09041c;")
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(15)
        
        # 1. Camera View (Fixed Size to prevent expanding)
        self.lbl_camera = QLabel("Kamera Kapalı")
        self.lbl_camera.setAlignment(Qt.AlignCenter)
        self.lbl_camera.setStyleSheet("background-color: #11092b; color: #e9d5ff; border: 2px solid #a855f7; border-radius: 10px;")
        self.lbl_camera.setFixedSize(640, 360) # Fixed 16:9 ratio size
        
        # Center the camera
        cam_layout = QHBoxLayout()
        cam_layout.addStretch()
        cam_layout.addWidget(self.lbl_camera)
        cam_layout.addStretch()
        left_layout.addLayout(cam_layout)
        
        # 3. Control Buttons
        btn_layout = QGridLayout()
        btn_layout.setSpacing(10)
        
        self.btn_cam = self.create_button("Kamera Aç", "#38bdf8", self.toggle_camera)
        self.btn_party = self.create_button("Parti Modu", "#a855f7", self.toggle_party)
        
        btn_layout.addWidget(self.btn_cam, 0, 0)
        btn_layout.addWidget(self.btn_party, 0, 1)
        
        left_layout.addLayout(btn_layout)
        
        # 4. Chat Log (Text Edit)
        self.chat_log = QTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_log.setStyleSheet("background-color: #000000; color: #4ade80; font-family: Consolas; font-size: 13px; border-radius: 5px; padding: 5px;")
        self.chat_log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chat_log.setMinimumHeight(150)
        left_layout.addWidget(self.chat_log)
        
        # 5. AI Text Input
        chat_input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Yapay zekaya yazıyla mesaj gönderin...")
        self.chat_input.setStyleSheet("background-color: #11092b; color: white; padding: 10px; border-radius: 5px; font-size: 14px;")
        self.chat_input.returnPressed.connect(self.send_text_to_ai)
        
        self.btn_send_chat = QPushButton("Gönder")
        self.btn_send_chat.setCursor(Qt.PointingHandCursor)
        self.btn_send_chat.setStyleSheet("background-color: #a855f7; color: white; padding: 10px; border-radius: 5px; font-weight: bold;")
        self.btn_send_chat.clicked.connect(self.send_text_to_ai)
        
        chat_input_layout.addWidget(self.chat_input)
        chat_input_layout.addWidget(self.btn_send_chat)
        left_layout.addLayout(chat_input_layout)
        
        # --- RIGHT PANEL (50%) ---
        self.right_panel = QFrame()
        self.right_panel.setStyleSheet("background-color: #09041c;")
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.right_stack = QStackedWidget()
        right_layout.addWidget(self.right_stack)
        
        # Stack Page 1: Connection Screen
        self.page_connect = QWidget()
        conn_vbox = QVBoxLayout(self.page_connect)
        conn_vbox.setAlignment(Qt.AlignCenter)
        
        lbl_welcome = QLabel("Miu Captive Portal")
        lbl_welcome.setStyleSheet("color: #38bdf8; font-size: 28px; font-weight: bold; margin-bottom: 10px;")
        lbl_welcome.setAlignment(Qt.AlignCenter)
        
        self.ip_input = QLineEdit(self.robot_ip)
        self.ip_input.setPlaceholderText("Robotun IP Adresi (Örn: 192.168.4.1)")
        self.ip_input.setStyleSheet("background-color: #11092b; color: #bae6fd; padding: 15px; border-radius: 8px; font-size: 16px;")
        self.ip_input.setMinimumWidth(350)
        self.ip_input.setAlignment(Qt.AlignCenter)
        
        self.btn_connect = QPushButton("Ağa Bağlan")
        self.btn_connect.setCursor(Qt.PointingHandCursor)
        self.btn_connect.setStyleSheet("background-color: #a855f7; color: white; padding: 15px; border-radius: 8px; font-weight: bold; font-size: 16px; margin-top: 10px;")
        self.btn_connect.setMinimumWidth(200)
        self.btn_connect.clicked.connect(self.connect_miu)
        
        conn_vbox.addWidget(lbl_welcome)
        conn_vbox.addWidget(self.ip_input)
        conn_vbox.addWidget(self.btn_connect, alignment=Qt.AlignCenter)
        
        # Stack Page 2: WebView
        self.page_web = QWidget()
        web_layout = QVBoxLayout(self.page_web)
        web_layout.setContentsMargins(0, 0, 0, 0)
        
        self.web_view = QWebEngineView()
        self.web_view.page().setBackgroundColor(QColor("#09041c")) # Fix white flash
        web_layout.addWidget(self.web_view)
        
        self.right_stack.addWidget(self.page_connect)
        self.right_stack.addWidget(self.page_web)
        
        # Add to main layout (Stretch ratios 1:1)
        main_layout.addWidget(self.left_panel, 1)
        main_layout.addWidget(self.right_panel, 1)
        
        self.log("Miu Arch GUI başlatıldı. IP adresini girip Bağlan'a tıklayın.")

    def create_button(self, text, bg_color, callback):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"background-color: {bg_color}; color: white; font-weight: bold; padding: 15px; border-radius: 8px; font-size: 14px;")
        btn.clicked.connect(callback)
        return btn

    def apply_theme(self):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#09041c"))
        self.setPalette(palette)

    def log(self, text):
        self.chat_log.append(f"> {text}")
        scrollbar = self.chat_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def connect_miu(self):
        ip = self.ip_input.text().strip()
        if not ip:
            self.log("Hata: IP adresi boş olamaz.")
            return
        
        self.robot_ip = ip
        self.log(f"Bağlanılıyor: {ip}...")
        
        # Init Backend
        self.app_backend = MiuCompanionApp(
            robot_ip=self.robot_ip,
            miu_local=False,
            gemini_api_key=self.api_key,
            voice_enabled=True,
            tts_engine="pyttsx3"
        )
        
        # Load Web View
        self.web_view.setUrl(QUrl(f"http://{ip}/"))
        self.web_view.loadFinished.connect(self.inject_css)
        self.right_stack.setCurrentWidget(self.page_web)
        self.log("Web portalı yüklendi.")
        
        # Start Touch Shutter Polling
        if not self.touch_timer.isActive():
            self.touch_timer.start(500) # Poll every 500ms

    def inject_css(self):
        # Fix black rectangle glitch on buttons without disabling GPU
        js = """
        var style = document.createElement('style');
        style.innerHTML = '* { outline: none !important; -webkit-tap-highlight-color: transparent !important; } ::-webkit-scrollbar { display: none !important; }';
        document.head.appendChild(style);
        """
        self.web_view.page().runJavaScript(js)

    def send_cmd(self, pose):
        if not self.robot_ip: return
        try:
            requests.get(f"http://{self.robot_ip}/cmd?pose={pose}", timeout=2)
            self.log(f"Komut: {pose}")
        except:
            pass

    # --- CAMERA ---
    def toggle_camera(self):
        if self.cam_thread and self.cam_thread.running:
            self.cam_thread.stop()
            self.cam_thread = None
            self.btn_cam.setText("Kamera Aç")
            self.btn_cam.setStyleSheet("background-color: #38bdf8; color: white; font-weight: bold; padding: 15px; border-radius: 8px; font-size: 14px;")
            self.lbl_camera.clear()
            self.lbl_camera.setText("Kamera Kapalı")
            self.log("Kamera durduruldu.")
        else:
            self.cam_thread = CameraThread()
            self.cam_thread.change_pixmap_signal.connect(self.update_image)
            self.cam_thread.capture_signal.connect(self.photo_captured)
            self.cam_thread.start()
            self.btn_cam.setText("Kamerayı Kapat")
            self.btn_cam.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 15px; border-radius: 8px; font-size: 14px;")
            self.log("Kamera başlatıldı.")

    def update_image(self, qt_img):
        # Scale image to label size
        pixmap = QPixmap.fromImage(qt_img).scaled(self.lbl_camera.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.lbl_camera.setPixmap(pixmap)

    def photo_captured(self, filename):
        self.log(f"📸 Sensör tetikledi! Fotoğraf çekildi: {filename}")
        self.lbl_camera.setStyleSheet("background-color: white; border: 2px solid white; border-radius: 10px;")
        QTimer.singleShot(100, lambda: self.lbl_camera.setStyleSheet("background-color: #11092b; color: #e9d5ff; border: 2px solid #a855f7; border-radius: 10px;"))

    def poll_touch(self):
        if not self.robot_ip: return
        try:
            r = requests.get(f"http://{self.robot_ip}/getTouchStatus", timeout=1)
            if r.status_code == 200:
                data = r.json()
                if data.get("touched") and self.cam_thread and self.cam_thread.running:
                    self.log("Touch sensörü tetiklendi! Fotoğraf çekiliyor...")
                    self.cam_thread.trigger_capture = True
        except:
            pass

    # --- PARTY MODE ---
    def toggle_party(self):
        if self.party_thread and self.party_thread.running:
            self.party_thread.stop()
            self.party_thread = None
            self.btn_party.setText("Parti Modu")
            self.btn_party.setStyleSheet("background-color: #a855f7; color: white; font-weight: bold; padding: 15px; border-radius: 8px; font-size: 14px;")
            self.log("Parti Modu Kapatıldı.")
            try: requests.get(f"http://{self.robot_ip}/setSettings?autonomousMode=true", timeout=2)
            except: pass
        else:
            self.party_thread = PartyThread()
            self.party_thread.beat_signal.connect(self.on_beat_detected)
            self.party_thread.start()
            self.btn_party.setText("Parti Kapat")
            self.btn_party.setStyleSheet("background-color: #ff5722; color: white; font-weight: bold; padding: 15px; border-radius: 8px; font-size: 14px;")
            self.log("Parti Modu Aktif! (Ortam sesi dinleniyor...)")
            try: requests.get(f"http://{self.robot_ip}/setSettings?autonomousMode=false", timeout=2)
            except: pass

    def on_beat_detected(self):
        pose = "dance" if time.time() % 2 < 1 else "nod"
        self.send_cmd(pose)

    def send_text_to_ai(self):
        text = self.chat_input.text().strip()
        if not text:
            return
        self.chat_input.clear()
        self.log(f"Sen (Metin): {text}")
        if not self.app_backend:
            self.log("Önce robot IP'si girip bağlanın.")
            return
        
        worker = ChatWorker(self.app_backend, text)
        worker.response_signal.connect(self.on_chat_response)
        
        # Prevent GC
        self.active_workers.append(worker)
        worker.finished.connect(lambda w=worker: self.active_workers.remove(w) if w in self.active_workers else None)
        
        worker.start()

    def on_chat_response(self, response, command):
        self.log(f"Miu: {response}")
        if command:
            self.send_cmd(command)

    def closeEvent(self, event):
        if self.cam_thread: self.cam_thread.stop()
        if self.party_thread: self.party_thread.stop()
        event.accept()

if __name__ == "__main__":
    # Electron (Chromium) fixes for Linux
    sys.argv.append("--ignore-gpu-blocklist")
    sys.argv.append("--enable-gpu-rasterization")
    sys.argv.append("--enable-zero-copy")
    sys.argv.append("--disable-gpu-driver-bug-workarounds")
    app = QApplication(sys.argv)
    window = MiuMainWindow()
    window.show()
    sys.exit(app.exec_())
