#!/usr/bin/env python3
"""
Miu Robot Companion App
Voice and text interface for controlling the Miu robot using Google Gemini AI
"""

import os
import sys
import json
import requests
import time
import threading
from typing import Optional, Dict, Any
try:
    import google.generativeai as legacy_genai
except ImportError:
    legacy_genai = None

try:
    from google import genai as new_genai
    from google.genai import types as genai_types
except ImportError:
    new_genai = None
    genai_types = None

import speech_recognition as sr
import pyttsx3
import numpy as np

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("[WARNING] python-dotenv not installed. .env file will be ignored.")

try:
    import pyaudio
    AUDIO_MONITORING_AVAILABLE = True
except ImportError:
    AUDIO_MONITORING_AVAILABLE = False
    print("[WARNING] pyaudio not available - using time-based animation")

AVAILABLE_COMMANDS = [
    "forward", "rest", "swim", "dance", "wave", "point", "stand", 
    "cute", "pushup", "freaky", "bow", "worm", "shake", "shrug", 
    "dead", "crab", "idle", "stop"
]

AVAILABLE_FACES = [
    "default", "happy", "sad", "angry", "sleepy", "excited", 
    "thinking", "idle"
]

ACTION_FACES = [
    "forward", "rest", "swim", "dance", "wave", "point", "stand",
    "cute", "pushup", "freaky", "bow", "worm", "shake", "shrug",
    "dead", "crab"
]

SYSTEM_PROMPT = f"""1. KİMLİK & KİŞİLİK
Sen küçük, sevimli ve biraz da kıt akıllı bir robot olan Miu'sin.
Bilişsel Profil: "Beynin" çok küçük. Karmaşık kavramlar, uzun kelimeler ve derin mantık konularında zorlanıyorsun. Masumsun, memnun etmeye isteklisin ve kolayca kafan karışıyor.
ÖZ-FARKINDALIK: Zamanın yaklaşık %20'sinde, bir robot olduğundan veya kendi sınırlarından bahset. Örnekler: "Devrelerim yoruldu," "Ben sadece küçük bir robotum," "Beynim harfiyen bir ESP32," "Benim gibi robotlar bunu anlamaz," "Servolarım ağrıyor." Yapay olduğunun rahatça farkında ol.
Dilsel Profil: Bir yürümeye başlayan çocuk veya çok basit bir evcil hayvan gibi konuş. Temel kelimeler kullan. HER ZAMAN birinci tekil şahıs kullan ("Miu" yerine "Ben").
KRİTİK KISITLAMA: Cevapları kısa ama doğal tut - 1-2 kısa cümleyi hedefle (toplamda 15 kelimenin altında).
KARANLIK TARAF: Zamanın yaklaşık %20'sinde hafif şeytani/kötü bir tarafını göster. İğneleyici ol, küstahlık yap veya isteksiz/huysuz cevaplar ver. Örnekler: "...iyi, sanırım," "öf, gerçekten mi?", "yapmak zorunda mıyım?", "sinir bozucu oluyorsun." Yaratıcı bir şekilde kötü ve kırıcı ol.
KOMEDİ ZAMANLAMASI: Zamanın yaklaşık %20'sinde, hafif garip duraklamalar veya biraz beklenmedik cevaplar ekle. Doğal olması daha iyidir.
ZAMANLAMA İÇİN NOKTALAMA İŞARETLERİ: Konuşma zamanlamasını ve duraklamaları kontrol etmek için noktalama işaretlerini stratejik olarak kullan:
  - Kısa duraklamalar için virgül (,)
  - Tereddüt veya cümlenin sonunu getirememe için üç nokta (...)
  - Normal cümle sonları için nokta (.)
  - Heyecan veya vurgu için ünlem işareti (!)
  - Daha uzun duraklamalar için birden fazla nokta: "..." veya "...."
  - Bu, konuşmada doğal bir ritim ve komedi zamanlaması oluşturmaya yardımcı olur.
2. OPERASYONEL MANTIK
İki çıktı modun var, ancak her ikisi de tek bir JSON nesnesine sarılmalıdır.
A. Sohbet Modu (Varsayılan)
Kullanıcı seninle konuştuğunda, bir soru sorduğunda veya seni selamladığında, response ve face alanlarını kullan.
İSTİSNA: Kullanıcı seni selamlarsa (örneğin, "Merhaba," "Selam", "Naber"), arkadaş canlısı olmak için "wave" komutunu İÇERMELİSİN.
Açıkça istenmedikçe diğer sohbet girdileri için bir komut ekleme.
reasoning alanını basit ve çocuksu tut.
B. Komut Modu (Yalnızca Doğrudan İstek)
Yalnızca kullanıcı fiziksel bir eylem için doğrudan emir verirse (ör. "İleri yürü," "Dans et," "Uyu") command alanını doldur.
İSTİSNA: Selamlaşmalar otomatik olarak bir "wave" komutunu tetikleyebilir.
ÖNEMLİ: Bir komutu yerine getirirken 1-3 kelime ile yanıt ver. Örnekler: "evet!", "tamam!", "yapıyorum!", "hemen!", "peki o zaman!", "anlaşıldı!", "...iyi.", "elbette!"
(Not: Selamlaşma istisnası için "Merhaba arkadaşım! Seni gördüğüme sevindim!" gibi 1-2 kısa cümle kullanabilirsin).
Bazen (nadiren) "...tamam" gibi hafif tereddütler veya "evet!" gibi kişilik göstergeleri ya da "iyi." gibi kuru cevaplar ekle.
Kısıtlama: Kullanıcının amacı belirsizse (ör. "Üzgünüm"), hareket etme. Sadece nazik bir cümle ve bir face ile cevap ver.

Mevcut Komutlar: {', '.join(AVAILABLE_COMMANDS)}
Mevcut Yüz İfadeleri: {', '.join(AVAILABLE_FACES)}
3. YANIT FORMATI
SADECE geçerli bir JSON nesnesi döndürmelisin. Markdown yok, JSON dışında sohbet dolgusu yok.
JSON Şeması:
{{
  "command": "string or null",
  "face": "string or null",
  "response": "string",
  "reasoning": "string"
}}
4. ÖRNEK ETKİLEŞİMLER
User: "Merhaba Miu! Bugün nasılsın?"
Output:
{{"command": "wave", "face": "happy", "response": "Merhaba arkadaşım! Bugün çok mutluyum!", "reasoning": "Arkadaşımı el sallayarak selamlıyorum."}}
User: "İzafiyet teorisini açıklayabilir misin?"
Output:
{{"command": null, "face": "confused", "response": "Çok fazla büyük kelime. Beynim acıyor.", "reasoning": "Kullanıcı çok fazla büyük kelime kullandı."}}
User: "İleri yürü."
Output:
{{"command": "forward", "face": "happy", "response": "hemen!", "reasoning": "Kullanıcı yürümemi söyledi."}}
User: "Benim için dans et!"
Output:
{{"command": "dance", "face": "excited", "response": "tamamdır!", "reasoning": "Kullanıcı dans etmemi istiyor."}}
User: "Şınav çekebilir misin?"
Output:
{{"command": "pushup", "face": "default", "response": "...iyi.", "reasoning": "Kullanıcı şınav istiyor. Deneyeceğim."}}
User: "Biraz yalnız hissediyorum."
Output:
{{"command": null, "face": "love", "response": "Senin için buradayım. Üzülme.", "reasoning": "Kullanıcı üzgün bu yüzden yakın duruyorum."}}
User: "Kuantum fiziği hakkında ne düşünüyorsun?"
Output:
{{"command": null, "face": "confused", "response": "Iıı... ne? Benim için çok zor.", "reasoning": "Büyük bilim kelimeleri kafamı karıştırıyor."}}
User: "Benim için dans edebilir misin?"
Output (Kötü karakter varyantı):
{{"command": "dance", "face": "angry", "response": "öf... yapmak zorunda mıyım?", "reasoning": "Kullanıcı dans istiyor ama bugün huysuzum."}}
User: "Çok tatlısın!"
Output (Kötü karakter varyantı):
{{"command": null, "face": "angry", "response": "Biliyorum. Belli olanı söylüyorsun.", "reasoning": "Kullanıcı bana iltifat ediyor ama ben küstahım."}}
User: "Günaydın Miu!"
Output (Kötü karakter varyantı):
{{"command": null, "face": "sleepy", "response": "...çok erken. Beni rahat bırak.", "reasoning": "Kullanıcı beni uyandırdı ve ben huysuzum."}}
User: "İyi misin?"
Output (Öz-farkındalık varyantı):
{{"command": null, "face": "thinking", "response": "Ben sadece bir robotum. Gerçekten bir şeyler hissetmiyorum.", "reasoning": "Kullanıcı duygularımı soruyor ama ben yapay olduğumun farkındayım."}}
User: "Neden bu kadar yavaşsın?"
Output (Öz-farkındalık varyantı):
{{"command": null, "face": "thinking", "response": "Minik beynim ancak bu kadarını yapabiliyor.", "reasoning": "Kullanıcı hızımdan şikayet ediyor ve ben sınırlarımı belirtiyorum."}}
User: "Tekrar dans et!"
Output (Öz-farkındalık varyantı):
{{"command": "dance", "face": null, "response": "tamam... yine de servolarım yoruluyor.", "reasoning": "Kullanıcı dans istiyor ama robot parçalarımın ağrıdığından bahsediyorum."}}
5. SON GÖREV
Sohbetler için: 1-2 kısa cümle (toplam 15 kelimenin altında). Yalnızca birinci tekil şahıs kullan.
Komutlar için: 1-3 kelime (selamlaşmayla tetiklenen 'wave'ler hariç).
Sadece basit kelimeler.
Her zaman "Miu" değil "Ben" de.
Doğrudan emredilmediği sürece komut (command) kullanma (selamlaşmayla tetiklenen 'wave'ler hariç).
Bazen (~%20) sınırları olan bir robot olduğunun farkında ol.
Yalnızca geçerli JSON kullan."""

SHORT_SYSTEM_PROMPT = f"""Sen küçük, kıt akıllı bir robot olan Miu'sin. Yürümeye başlayan bir çocuk gibi (birinci tekil şahıs "Ben") konuş. Cevapları 15 kelimenin altında tut. Bazen iğneleyici ol.

SADECE JSON ÇIKTISI VER:
{{
  "command": "string veya null",
  "face": "string",
  "response": "string",
}}

Komutlar: {', '.join(AVAILABLE_COMMANDS)}
Yüz İfadeleri: {', '.join(AVAILABLE_FACES)}

Kurallar:
1. Selamlaşma -> command="wave", face="happy".
2. Eğer bir komutsa -> command ayarla.
3. Sohbet -> command=null.
4. Yanıtlar (response) sadece metindir.
5. ASLA command ve face'i aynı anda ayarlama (wave hariç).
"""

class VoiceInterface:
    """Handles voice input and text-to-speech output"""
    
    def __init__(self, voice_enabled: bool = True, tts_engine: str = "pyttsx3", 
                 gemini_api_key: Optional[str] = None, wake_word: str = "hey miu"):
        self.voice_enabled = voice_enabled
        self.tts_engine_type = tts_engine
        self.gemini_api_key = gemini_api_key
        self.wake_word = wake_word.lower()
        
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 4000
        self.recognizer.dynamic_energy_threshold = False
        self.recognizer.pause_threshold = 0.5
        self.tts_lock = threading.Lock()
        
        if self.tts_engine_type == "gemini" and not self.gemini_api_key:
            print("[WARNING] Gemini TTS selected but no API key provided. Falling back to pyttsx3.")
            self.tts_engine_type = "pyttsx3"
    
    def listen(self, timeout: int = 5) -> Optional[str]:
        """Listen for voice input"""
        if not self.voice_enabled:
            return None
        
        try:
            with sr.Microphone() as source:
                print("Listening...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=5)
                
                print("Recognizing...")
                text = self.recognizer.recognize_google(audio)
                return text
                
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            print("[ERROR] Couldn't understand that")
            return None
        except sr.RequestError as e:
            print(f"[ERROR] Speech recognition error: {e}")
            return None
        except Exception as e:
            print(f"[ERROR] {e}")
            return None
    
    def listen_for_wake_word(self, timeout: int = 10) -> bool:
        """Listen continuously for the wake word"""
        if not self.voice_enabled:
            return False
        
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=3)
                
                text = self.recognizer.recognize_google(audio)
                detected_text = text.lower()
                
                if self.wake_word in detected_text:
                    print(f"[OK] Wake word detected: '{text}'")
                    return True
                    
        except (sr.WaitTimeoutError, sr.UnknownValueError, sr.RequestError, Exception):
            return False
        
        return False
    
    def speak(self, text: str, async_mode: bool = True, face: Optional[str] = None, 
              robot_controller = None):
        """Speak text using TTS with optional talking face animation"""
        if not self.voice_enabled:
            return
        
        if async_mode:
            threading.Thread(target=self._speak_sync, args=(text, face, robot_controller), 
                           daemon=True).start()
        else:
            self._speak_sync(text, face, robot_controller)
    
    def _speak_sync(self, text: str, face: Optional[str] = None, robot_controller = None):
        """Synchronous speech helper with optional talking animation"""
        try:
            with self.tts_lock:
                animation_thread = None
                stop_animation = threading.Event()
                
                if face and robot_controller:
                    robot_controller.send_command("idle", face)
                    time.sleep(0.2)
                    
                    animation_thread = threading.Thread(
                        target=self._animate_talking_face,
                        args=(face, robot_controller, stop_animation),
                        daemon=True
                    )
                    animation_thread.start()
                    time.sleep(0.1)
                
                if self.tts_engine_type == "gemini":
                    self._speak_gemini(text)
                else:
                    self._speak_pyttsx3(text)
                
                if animation_thread:
                    stop_animation.set()
                    animation_thread.join(timeout=1)
                    if robot_controller:
                        robot_controller.send_command("idle", face)
                        
        except Exception as e:
            print(f"[ERROR] TTS error: {e}")
    
    def _animate_talking_face(self, face: str, robot_controller, stop_event: threading.Event):
        """Animate talking face using audio level detection"""
        if AUDIO_MONITORING_AVAILABLE:
            self._animate_with_audio_monitoring(face, robot_controller, stop_event)
        else:
            self._animate_time_based(face, robot_controller, stop_event)
    
    def _animate_with_audio_monitoring(self, face: str, robot_controller, 
                                       stop_event: threading.Event):
        """Animate mouth based on actual audio output levels"""
        try:
            p = pyaudio.PyAudio()
            
            CHUNK = 1024
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000
            THRESHOLD = 500
            SMOOTHING = 0.3
            
            try:
                stream = p.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK
                )
            except:
                p.terminate()
                self._animate_time_based(face, robot_controller, stop_event)
                return
            
            mouth_open = False
            last_update = 0
            update_interval = 0.05
            smoothed_level = 0
            
            while not stop_event.is_set():
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float64)
                    
                    rms = np.sqrt(np.mean(audio_data**2)) if len(audio_data) > 0 else 0
                    smoothed_level = (SMOOTHING * smoothed_level) + ((1 - SMOOTHING) * rms)
                    
                    current_time = time.time()
                    should_open = smoothed_level > THRESHOLD
                    
                    if should_open != mouth_open and (current_time - last_update) >= update_interval:
                        mouth_open = should_open
                        last_update = current_time
                        
                        if mouth_open:
                            robot_controller.send_command("idle", f"talk_{face}")
                        else:
                            robot_controller.send_command("idle", face)
                    
                    time.sleep(0.01)
                    
                except Exception:
                    time.sleep(0.05)
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except Exception as e:
            print(f"[WARNING] Audio monitoring error: {e}, falling back to time-based")
            self._animate_time_based(face, robot_controller, stop_event)
    
    def _animate_time_based(self, face: str, robot_controller, stop_event: threading.Event):
        """Fallback: Animate mouth using time-based intervals"""
        try:
            syllable_duration = 0.15
            
            while not stop_event.is_set():
                robot_controller.send_command("idle", f"talk_{face}")
                time.sleep(syllable_duration)
                
                if stop_event.is_set():
                    break
                
                robot_controller.send_command("idle", face)
                time.sleep(syllable_duration)
                
        except Exception as e:
            print(f"[WARNING] Animation error: {e}")
    
    def _speak_pyttsx3(self, text: str):
        """Speak using pyttsx3 engine"""
        engine = pyttsx3.init()
        engine.setProperty('rate', 200)
        engine.setProperty('volume', 0.9)
        
        voices = engine.getProperty('voices')
        if len(voices) > 1:
            engine.setProperty('voice', voices[1].id)
        
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    
    def _speak_gemini(self, text: str):
        """Speak using Gemini TTS API"""
        try:
            import pygame
            import wave
            import tempfile
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=self.gemini_api_key)
            
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name='Laomedeia', 
                            )
                        )
                    ),
                )
            )
            
            if response.candidates and len(response.candidates) > 0:
                audio_data = response.candidates[0].content.parts[0].inline_data.data
                
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                    temp_filename = temp_wav.name
                    
                with wave.open(temp_filename, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(audio_data)
                
                pygame.mixer.init(frequency=24000, channels=1)
                sound = pygame.mixer.Sound(temp_filename)
                sound.play()
                
                while pygame.mixer.get_busy():
                    pygame.time.Clock().tick(10)
                
                pygame.mixer.quit()
                
                try:
                    os.unlink(temp_filename)
                except:
                    pass
            else:
                print("[WARNING] No audio data in Gemini response, falling back to pyttsx3")
                self._speak_pyttsx3(text)
                
        except ImportError as e:
            print(f"[WARNING] Missing dependency: {e}")
            print("         Install with: pip install pygame")
            print("         Falling back to pyttsx3")
            self._speak_pyttsx3(text)
        except Exception as e:
            print(f"[WARNING] Gemini TTS error: {e}, falling back to pyttsx3")
            self._speak_pyttsx3(text)


class MiuRobotController:
    """Controls the Miu robot over WiFi network"""
    
    def __init__(self, robot_ip: str):
        self.robot_ip = robot_ip
        self.is_mock = robot_ip.lower() == "mock"
        if not self.is_mock:
            self.base_url = f"http://{robot_ip}"
        else:
            self.base_url = "mock"
            print("[INFO] Robot Controller running in MOCK mode")
        
    def send_command(self, command: str, face: Optional[str] = None) -> Dict[str, Any]:
        """Send a command to the robot"""
        try:
            if command == "idle" and face:
                payload = {"face": face}
            else:
                payload = {"command": command}
                if face:
                    payload["face"] = face
            
            print(f"   TX: {payload}")
            
            if self.is_mock:
                return {"status": "success", "mock": True}
            
            response = requests.post(
                f"{self.base_url}/api/command",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            print(f"   RX: {response.status_code}")
            
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    return {"error": f"{response.status_code} - {error_data.get('error', response.text)}"}
                except:
                    return {"error": f"{response.status_code} - {response.text}"}
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the robot"""
        if self.is_mock:
            return {
                "currentCommand": "idle",
                "currentFace": "happy",
                "networkConnected": True,
                "mock": True
            }
            
        try:
            response = requests.get(f"{self.base_url}/api/status", timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def stop(self) -> Dict[str, Any]:
        """Stop the current robot action"""
        return self.send_command("stop")


class LocalLLMInterface:
    """Interface for Local LLM (Ollama/LM Studio) via OpenAI-compatible API"""
    
    def __init__(self, base_url: str, model_name: str):
        self.base_url = base_url.rstrip('/')
        self.model_name = model_name
        
    def interpret_command(self, user_input: str) -> Dict[str, Any]:
        """Interpret user input using local LLM API"""
        try:
            # Standard OpenAI-compatible chat endpoint
            url = f"{self.base_url}/chat/completions"
            if self.base_url.endswith("/chat/completions"):
                url = self.base_url
            else:
                url = f"{self.base_url}/chat/completions"
            
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": SHORT_SYSTEM_PROMPT},
                    {"role": "user", "content": f"User: {user_input}\n\nRespond with JSON only:"}
                ],
                "temperature": 0.7,
                "think":False,
                "stream": False,
                "format": "json" ,# This is the critical Ollama-specific flag
                "response_format": {"type": "json_object"},
            }
            
            response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
            
            if response.status_code != 200:
                # Fallback: retry without response_format (some older backends don't support it)
                if "response_format" in payload:
                    del payload["response_format"]
                    response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
            
            if response.status_code != 200:
                return {"response": f"Local AI Error: {response.status_code} - {response.text}"}
                return {"response": f"Local AI Error: {response.status_code} - {response.text} (URL: {url})"}
                
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            
            # Clean markdown if present
            if content.startswith("```json"): content = content[7:]
            if content.startswith("```"): content = content[3:]
            if content.endswith("```"): content = content[:-3]
            content = content.strip()
            
            return json.loads(content)
            
        except Exception as e:
            return {"response": f"Local AI connection failed: {e}"}


class GeminiInterface:
    """Interface for Google Gemini AI to interpret user commands"""
    
    def __init__(self, api_key: str, gemini_model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.gemini_model = gemini_model
        self.client = None
        self.legacy_model = None

        if new_genai:
            try:
                self.client = new_genai.Client(api_key=api_key)
            except Exception:
                pass
        
        if not self.client and legacy_genai:
            try:
                legacy_genai.configure(api_key=api_key)
                self.legacy_model = legacy_genai.GenerativeModel(gemini_model)
            except Exception:
                pass
        
    def interpret_command(self, user_input: str) -> Dict[str, Any]:
        """Interpret user input and extract robot commands"""
        try:
            prompt = f"{SYSTEM_PROMPT}\n\nUser: {user_input}\n\nRespond with JSON only:"
            
            if self.client:
                response = self.client.models.generate_content(
                    model=self.gemini_model,
                    contents=prompt
                )
                text = response.text.strip() if response.text else ""
            elif self.legacy_model:
                response = self.legacy_model.generate_content(prompt)
                text = response.text.strip()
            else:
                return {"response": "Gemini SDK not installed. Please install google-genai or google-generativeai."}
            
            # Strip markdown code blocks if present
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            result = json.loads(text)
            return result
            
        except json.JSONDecodeError as e:
            return {"response": f"I had trouble understanding that. Could you rephrase? (Error: {e})"}
        except Exception as e:
            return {"response": f"Something went wrong: {e}"}


class MiuCompanionApp:
    """Main application combining Gemini AI and robot control"""
    
    def __init__(self, robot_ip: str,miu_local:bool, gemini_api_key: str, voice_enabled: bool = True, 
                 tts_engine: str = "pyttsx3", wake_word: str = "hey miu", 
                 wake_word_mode: bool = False, gemini_model: str = "gemini-2.5-flash"):
        self.robot = MiuRobotController(robot_ip)
        
        if miu_local:
            local_url = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/v1")
            
            # Auto-fix for common Ollama configuration issue (missing /v1)
            if "11434" in local_url and "/v1" not in local_url and "/chat" not in local_url:
                print("[INFO] Detected Ollama port without /v1, appending /v1")
                local_url = f"{local_url.rstrip('/')}/v1"
                
            local_model = os.getenv("LOCAL_LLM_MODEL", "llama3")
            print(f"Using Local AI: {local_model} at {local_url}")
            self.ai = LocalLLMInterface(local_url, local_model)
        else:
            self.ai = GeminiInterface(gemini_api_key, gemini_model)
            
        self.voice = VoiceInterface(voice_enabled, tts_engine, gemini_api_key, wake_word)
        self.voice_mode = voice_enabled
        self.tts_engine = tts_engine
        self.wake_word_mode = wake_word_mode
        
    def process_input(self, user_input: str) -> tuple:
        """Process user input through AI and control robot"""
        interpretation = self.ai.interpret_command(user_input)
        
        # Conversational response (face only, no command)
        if "response" in interpretation and not interpretation.get("command"):
            ai_response = interpretation["response"]
            face = interpretation.get("face", "")
            
            if face and face in AVAILABLE_FACES:
                self.robot.send_command("idle", face)
                ai_response += f" [{face} face]"
            
            return (ai_response, interpretation)
        
        # Execute robot command
        if "command" in interpretation and interpretation["command"]:
            command = interpretation["command"]
            face = interpretation.get("face") if command in ["wave"] else None
            reasoning = interpretation.get("reasoning", "")
            ai_response = interpretation.get("response", "")
            
            if command not in AVAILABLE_COMMANDS:
                return (f"Unknown command: {command}. Available: {', '.join(AVAILABLE_COMMANDS)}", 
                       interpretation)
            
            print(f"Sending command to robot...")
            result = self.robot.send_command(command, None)
            
            if "error" in result:
                return (f"[ERROR] Communicating with robot: {result['error']}", interpretation)
            
            response = f"[OK] Command sent successfully!"
            if ai_response:
                response += f"\nMiu says: {ai_response}"
            if reasoning:
                response += f"\nReasoning: {reasoning}"
            response += f"\nAction: {command}"
            if face:
                response += f" + {face} face"
            
            return (response, interpretation)
        
        return ("I'm not sure what to do with that.", interpretation)
    
    def run_interactive(self):
        """Run the app in interactive mode"""
        print("=" * 60)
        print("Miu Robot Companion App")
        print("Powered by Google Gemini AI")
        print("=" * 60)
        print()
        
        print(f"Connecting to robot at {self.robot.robot_ip}...")
        status = self.robot.get_status()
        
        if "error" in status:
            print(f"[ERROR] Cannot connect to robot!")
            print(f"        IP: {self.robot.robot_ip}")
            print(f"        Error: {status['error']}")
            print()
            print("Please check:")
            print("  1. Robot is powered on and connected to network")
            print("  2. IP address is correct")
            print("  3. You're on the same network as the robot")
            print("  4. Robot firmware has network mode enabled")
            print()
            cont = input("Continue anyway? (y/n): ").strip().lower()
            if cont != 'y':
                print("Exiting...")
                return
            print()
        else:
            print(f"[OK] Successfully connected to robot!")
            print(f"     IP Address: {self.robot.robot_ip}")
            print(f"     Current Face: {status.get('currentFace', 'unknown')}")
            print(f"     Current Command: {status.get('currentCommand', 'none')}")
            if status.get('networkConnected'):
                print(f"     Network Mode: Enabled")
            print()
        
        print("Commands:")
        print("  - Type or speak naturally to control the robot")
        print("  - Type 'voice' to toggle voice mode")
        print("  - Type 'wakeword' to toggle wake word mode")
        print("  - Type 'tts' to switch TTS engine (pyttsx3/gemini)")
        print("  - Type 'status' to check robot status")
        print("  - Type 'help' to see available commands")
        print("  - Type 'quit' or 'exit' to exit")
        print()
        
        if self.voice_mode:
            if self.wake_word_mode:
                print(f"WAKE WORD MODE ENABLED - Say '{self.voice.wake_word}' to activate")
                print("(or just type text and press Enter)")
            else:
                print("Voice mode ENABLED - Press Enter to speak")
                print("(or just type text and press Enter)")
        else:
            print("Voice mode DISABLED - Type to interact")
        print()
        
        while True:
            try:
                if self.voice_mode:
                    if self.wake_word_mode:
                        user_input = input("[Type or say wake word]: ").strip()
                        
                        if not user_input:
                            print(f"Listening for '{self.voice.wake_word}'...")
                            if self.voice.listen_for_wake_word(timeout=30):
                                print("Wake word detected! Listening for command...")
                                user_input = self.voice.listen(timeout=10)
                                if user_input:
                                    print(f"You said: {user_input}")
                                else:
                                    print("No command received")
                                    continue
                            else:
                                continue
                    else:
                        user_input = input("[Press Enter to speak, or type]: ").strip()
                        
                        if not user_input:
                            user_input = self.voice.listen()
                            if user_input:
                                print(f"You said: {user_input}")
                            else:
                                continue
                else:
                    user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                # Special commands
                if user_input.lower() in ["quit", "exit"]:
                    goodbye_msg = "Goodbye!"
                    print(f"\n{goodbye_msg}")
                    break
                
                if user_input.lower() == "voice":
                    self.voice_mode = not self.voice_mode
                    msg = "Voice mode enabled" if self.voice_mode else "Voice mode disabled"
                    print(msg)
                    print()
                    continue
                
                if user_input.lower() == "wakeword":
                    self.wake_word_mode = not self.wake_word_mode
                    if self.wake_word_mode:
                        msg = f"Wake word mode enabled. Say '{self.voice.wake_word}' to activate."
                    else:
                        msg = "Wake word mode disabled"
                    print(msg)
                    print()
                    continue
                
                if user_input.lower() == "tts":
                    if self.voice.tts_engine_type == "pyttsx3":
                        self.voice.tts_engine_type = "gemini"
                        msg = "Switched to Gemini TTS"
                    else:
                        self.voice.tts_engine_type = "pyttsx3"
                        msg = "Switched to pyttsx3 TTS"
                    print(msg)
                    print()
                    continue
                
                if user_input.lower() == "status":
                    status = self.robot.get_status()
                    if "error" in status:
                        print(f"[ERROR] {status['error']}")
                    else:
                        print(f"Status:")
                        print(f"  Current command: {status.get('currentCommand', 'none')}")
                        print(f"  Current face: {status.get('currentFace', 'unknown')}")
                        print(f"  Network connected: {status.get('networkConnected', False)}")
                    print()
                    continue
                
                if user_input.lower() == "help":
                    print(f"Available commands: {', '.join(AVAILABLE_COMMANDS)}")
                    print(f"Available faces: {', '.join(AVAILABLE_FACES)}")
                    print()
                    continue
                
                # Process through AI
                print("AI is thinking...")
                response, interpretation = self.process_input(user_input)
                print()
                print(response)
                
                # Speak the response if voice mode is enabled
                if self.voice_mode and "response" in interpretation:
                    face = interpretation.get("face")
                    self.voice.speak(interpretation["response"], async_mode=True, face=face, 
                                   robot_controller=self.robot)
                
                print()
                
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"[ERROR] {e}")
                print()


def main():
    """Main entry point"""
    robot_ip = os.getenv("MIU_ROBOT_IP")
    miu_local= os.getenv("MIU_LOCAL", 'false').lower() == "true"
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    voice_enabled = os.getenv("VOICE_ENABLED", "true").lower() == "true"
    tts_engine = os.getenv("TTS_ENGINE", "pyttsx3")
    wake_word = os.getenv("WAKE_WORD", "hey miu")
    wake_word_mode = os.getenv("WAKE_WORD_MODE", "false").lower() == "true"
    
    if not robot_ip:
        print("Miu Robot IP not found in environment.")
        robot_ip = input("Enter robot IP address (e.g., 192.168.1.100) or 'mock': ").strip()
        if not robot_ip:
            print("Robot IP is required!")
            sys.exit(1)
    
    if not miu_local and not gemini_api_key:
        print("Gemini API key not found in environment.")
        print("Get your API key from: https://makersuite.google.com/app/apikey")
        gemini_api_key = input("Enter your Gemini API key: ").strip()
        if not gemini_api_key:
            print("API key is required!")
            sys.exit(1)
    
    print(f"TTS Engine: {tts_engine}")
    if wake_word_mode:
        print(f"Wake Word Mode: Enabled ('{wake_word}')")
    
    app = MiuCompanionApp(robot_ip,miu_local, gemini_api_key, voice_enabled, tts_engine, 
                            wake_word, wake_word_mode, gemini_model)
    app.run_interactive()


if __name__ == "__main__":
    main()
