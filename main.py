"""
Audio Booster - 批量音频放大器
Kivy Android App
"""

import os
import threading
from pathlib import Path

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import (
    StringProperty, NumericProperty, BooleanProperty
)
from kivy.clock import Clock
from kivy.utils import platform

if platform == 'android':
    from android.permissions import request_permissions, Permission

from audio_processor import AudioProcessor, SUPPORTED_EXTS

KV = '''
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<ScreenManager>:
    MainScreen:
    SettingsScreen:
    ResultScreen:

<MainScreen>:
    name: 'main'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(16)
        spacing: dp(12)

        # ── 标题栏 ──
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            canvas.before:
                Color:
                    rgba: 0.13, 0.59, 0.95, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(12)]
            Label:
                text: 'Audio Booster'
                font_size: sp(22)
                bold: True
                color: 1, 1, 1, 1

        # ── 输入目录 ──
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(8)
            canvas.before:
                Color:
                    rgba: 0.95, 0.95, 0.95, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(8)]
            Label:
                text: root.input_dir_display
                font_size: sp(13)
                color: 0.3, 0.3, 0.3, 1
                text_size: self.size
                halign: 'left'
                valign: 'center'
                padding: [dp(12), 0]
            Button:
                text: 'Select'
                size_hint_x: None
                width: dp(80)
                background_color: 0.13, 0.59, 0.95, 1
                background_normal: ''
                on_release: root.choose_input_dir()
                font_size: sp(14)

        # ── 倍数滑块 ──
        BoxLayout:
            size_hint_y: None
            height: dp(100)
            orientation: 'vertical'
            spacing: dp(4)
            canvas.before:
                Color:
                    rgba: 1, 1, 1, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(8)]
                Color:
                    rgba: 0.9, 0.9, 0.9, 1
                Line:
                    rounded_rectangle: [self.x, self.y, self.width, self.height, dp(8)]
                    width: 1
            BoxLayout:
                size_hint_y: None
                height: dp(32)
                padding: [dp(12), 0]
                Label:
                    text: 'Multiplier'
                    font_size: sp(15)
                    bold: True
                    color: 0.2, 0.2, 0.2, 1
                    halign: 'left'
                    text_size: self.size
                    valign: 'center'
                Label:
                    text: root.multiplier_display
                    font_size: sp(20)
                    bold: True
                    color: 0.13, 0.59, 0.95, 1
                    size_hint_x: None
                    width: dp(80)
            Slider:
                id: multiplier_slider
                min: 0.5
                max: 10.0
                value: root.multiplier
                step: 0.1
                size_hint_y: None
                height: dp(40)
                padding: [dp(12), 0]
                on_value: root.multiplier = round(self.value, 1)
            BoxLayout:
                size_hint_y: None
                height: dp(20)
                padding: [dp(12), 0]
                Label:
                    text: '0.5x'
                    font_size: sp(11)
                    color: 0.6, 0.6, 0.6, 1
                    halign: 'left'
                    text_size: self.size
                    valign: 'center'
                Label:
                    text: '10x'
                    font_size: sp(11)
                    color: 0.6, 0.6, 0.6, 1
                    halign: 'right'
                    text_size: self.size
                    valign: 'center'

        # ── 处理模式 ──
        BoxLayout:
            size_hint_y: None
            height: dp(110)
            orientation: 'vertical'
            spacing: dp(6)
            canvas.before:
                Color:
                    rgba: 1, 1, 1, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(8)]
                Color:
                    rgba: 0.9, 0.9, 0.9, 1
                Line:
                    rounded_rectangle: [self.x, self.y, self.width, self.height, dp(8)]
                    width: 1
            Label:
                text: 'Mode'
                font_size: sp(15)
                bold: True
                color: 0.2, 0.2, 0.2, 1
                size_hint_y: None
                height: dp(30)
                halign: 'left'
                text_size: self.size
                valign: 'center'
                padding: [dp(12), 0]
            BoxLayout:
                spacing: dp(8)
                padding: [dp(8), 0]
                ModeButton:
                    text: 'Smart'
                    active: root.mode == 'smart'
                    on_release: root.mode = 'smart'
                ModeButton:
                    text: 'Direct'
                    active: root.mode == 'direct'
                    on_release: root.mode = 'direct'
                ModeButton:
                    text: 'Peak'
                    active: root.mode == 'peak'
                    on_release: root.mode = 'peak'

        # ── 输出格式 ──
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(8)
            canvas.before:
                Color:
                    rgba: 1, 1, 1, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(8)]
                Color:
                    rgba: 0.9, 0.9, 0.9, 1
                Line:
                    rounded_rectangle: [self.x, self.y, self.width, self.height, dp(8)]
                    width: 1
            Label:
                text: 'Output'
                font_size: sp(14)
                color: 0.3, 0.3, 0.3, 1
                size_hint_x: None
                width: dp(80)
                padding: [dp(12), 0]
            Spinner:
                text: root.output_format
                values: ['same', 'mp3', 'wav', 'flac', 'ogg']
                size_hint_x: None
                width: dp(120)
                on_text: root.output_format = self.text
                background_color: 0.13, 0.59, 0.95, 0.15
                background_normal: ''
                color: 0.13, 0.59, 0.95, 1

        # ── 进度条 ──
        BoxLayout:
            size_hint_y: None
            height: dp(50)
            orientation: 'vertical'
            spacing: dp(4)
            opacity: 1 if root.processing else 0
            Label:
                text: root.progress_text
                font_size: sp(12)
                color: 0.4, 0.4, 0.4, 1
                size_hint_y: None
                height: dp(20)
            ProgressBar:
                value: root.progress
                max: 100
                size_hint_y: None
                height: dp(8)

        Widget:
            size_hint_y: 0.3

        # ── 开始按钮 ──
        Button:
            text: 'Start Batch Amplify' if not root.processing else 'Processing...'
            size_hint_y: None
            height: dp(56)
            background_color: (0.13, 0.59, 0.95, 1) if not root.processing else (0.6, 0.6, 0.6, 1)
            background_normal: ''
            font_size: sp(18)
            bold: True
            on_release: root.start_processing() if not root.processing else None
            canvas.before:
                Color:
                    rgba: self.background_color
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(12)]

        # ── 底部按钮 ──
        BoxLayout:
            size_hint_y: None
            height: dp(44)
            spacing: dp(8)
            Button:
                text: 'Settings'
                background_color: 0.9, 0.9, 0.9, 1
                background_normal: ''
                color: 0.3, 0.3, 0.3, 1
                font_size: sp(14)
                on_release: app.root.current = 'settings'
                canvas.before:
                    Color:
                        rgba: self.background_color
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(8)]
            Button:
                text: 'Results'
                background_color: 0.9, 0.9, 0.9, 1
                background_normal: ''
                color: 0.3, 0.3, 0.3, 1
                font_size: sp(14)
                on_release: app.root.current = 'result'
                canvas.before:
                    Color:
                        rgba: self.background_color
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(8)]

<ModeButton@Button>:
    active: False
    background_color: (0.13, 0.59, 0.95, 0.2) if self.active else (0.95, 0.95, 0.95, 1)
    background_normal: ''
    color: (0.13, 0.59, 0.95, 1) if self.active else (0.4, 0.4, 0.4, 1)
    font_size: sp(13)
    bold: self.active
    canvas.before:
        Color:
            rgba: self.background_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(8)]
        Color:
            rgba: (0.13, 0.59, 0.95, 1) if self.active else (0.85, 0.85, 0.85, 1)
        Line:
            rounded_rectangle: [self.x, self.y, self.width, self.height, dp(8)]
            width: 1.5 if self.active else 1


<SettingsScreen>:
    name: 'settings'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(16)
        spacing: dp(12)

        BoxLayout:
            size_hint_y: None
            height: dp(48)
            Button:
                text: '< Back'
                size_hint_x: None
                width: dp(80)
                background_color: 0.9, 0.9, 0.9, 1
                background_normal: ''
                on_release: app.root.current = 'main'
            Label:
                text: 'Settings'
                font_size: sp(20)
                bold: True

        BoxLayout:
            size_hint_y: None
            height: dp(80)
            orientation: 'vertical'
            canvas.before:
                Color:
                    rgba: 1, 1, 1, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(8)]
            Label:
                text: 'Max peak: ' + str(root.max_peak_db) + ' dBFS'
                font_size: sp(14)
                color: 0.3, 0.3, 0.3, 1
            Slider:
                min: -6
                max: 0
                value: root.max_peak_db
                step: 0.5
                on_value: root.max_peak_db = round(self.value, 1)

        BoxLayout:
            size_hint_y: None
            height: dp(60)
            orientation: 'vertical'
            canvas.before:
                Color:
                    rgba: 1, 1, 1, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(8)]
            Label:
                text: 'MP3 bitrate: ' + root.bitrate
                font_size: sp(14)
                color: 0.3, 0.3, 0.3, 1
            Spinner:
                text: root.bitrate
                values: ['128k', '192k', '256k', '320k']
                on_text: root.bitrate = self.text

        Widget:

<ResultScreen>:
    name: 'result'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(16)
        spacing: dp(12)

        BoxLayout:
            size_hint_y: None
            height: dp(48)
            Button:
                text: '< Back'
                size_hint_x: None
                width: dp(80)
                background_color: 0.9, 0.9, 0.9, 1
                background_normal: ''
                on_release: app.root.current = 'main'
            Label:
                text: 'Results'
                font_size: sp(20)
                bold: True

        ScrollView:
            Label:
                text: root.result_text
                font_size: sp(13)
                text_size: self.width, None
                size_hint_y: None
                height: self.texture_size[1]
                color: 0.2, 0.2, 0.2, 1
                halign: 'left'
                valign: 'top'
                padding: [dp(8), dp(8)]
'''


class MainScreen(Screen):
    multiplier = NumericProperty(2.0)
    multiplier_display = StringProperty('2.0x')
    mode = StringProperty('smart')
    output_format = StringProperty('same')
    input_dir = StringProperty('')
    input_dir_display = StringProperty('Tap Select to choose folder')
    processing = BooleanProperty(False)
    progress = NumericProperty(0)
    progress_text = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.processor = AudioProcessor()
        self.bind(multiplier=self._update_display)

    def _update_display(self, *args):
        self.multiplier_display = f'{self.multiplier:.1f}x'

    def choose_input_dir(self):
        if platform == 'android':
            from android.filechooser import choose_folder
            choose_folder(callback=self._on_folder_chosen)
        else:
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                folder = filedialog.askdirectory(title="Select audio folder")
                root.destroy()
                if folder:
                    self._set_input_dir(folder)
            except Exception:
                pass

    def _on_folder_chosen(self, *args):
        if args and args[0]:
            self._set_input_dir(args[0])

    def _set_input_dir(self, path):
        self.input_dir = path
        name = Path(path).name or path
        count = sum(1 for f in Path(path).iterdir()
                    if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS)
        self.input_dir_display = f'{name} ({count} files)'

    def start_processing(self):
        if not self.input_dir or self.processing:
            return

        self.processing = True
        self.progress = 0
        self.progress_text = 'Preparing...'

        out_fmt = None if self.output_format == 'same' else self.output_format

        app = App.get_running_app()
        bitrate = app.settings.get('bitrate', '192k')

        def run():
            def progress_cb(pct, fname, msg):
                Clock.schedule_once(lambda dt: self._update_progress(pct, msg), 0)

            results = self.processor.process_batch(
                input_dir=self.input_dir,
                output_dir=os.path.join(self.input_dir, 'amplified_output'),
                multiplier=self.multiplier,
                mode=self.mode,
                output_format=out_fmt,
                bitrate=bitrate,
                callback=progress_cb
            )
            Clock.schedule_once(lambda dt: self._on_done(results), 0)

        threading.Thread(target=run, daemon=True).start()

    def _update_progress(self, pct, text):
        self.progress = pct * 100
        self.progress_text = text

    def _on_done(self, results):
        self.processing = False
        self.progress = 100
        self.progress_text = 'All done!'
        result_screen = self.manager.get_screen('result')
        result_screen.update_results(results)


class SettingsScreen(Screen):
    max_peak_db = NumericProperty(-1.0)
    bitrate = StringProperty('192k')

    def on_max_peak_db(self, *args):
        app = App.get_running_app()
        if app:
            app.settings['max_peak_db'] = self.max_peak_db

    def on_bitrate(self, *args):
        app = App.get_running_app()
        if app:
            app.settings['bitrate'] = self.bitrate


class ResultScreen(Screen):
    result_text = StringProperty('No results yet.\nResults will appear here after processing.')

    def update_results(self, results):
        if not results:
            return

        lines = ['=== Processing Report ===', '']
        success = sum(1 for r in results if r['status'] == 'success')
        failed = sum(1 for r in results if r['status'] == 'error')
        lines.append(f'Success: {success}  Failed: {failed}')
        lines.append('')

        for r in results:
            name = Path(r['input']).name
            if r['status'] == 'success':
                peak_b = r.get('peak_before_db', 0)
                peak_a = r.get('peak_after_db', 0)
                rms_b = r.get('rms_before_db', 0)
                rms_a = r.get('rms_after_db', 0)
                lines.append(f'[OK] {name}')
                lines.append(f'  Peak: {peak_b:.1f} -> {peak_a:.1f} dBFS')
                lines.append(f'  RMS:  {rms_b:.1f} -> {rms_a:.1f} dBFS')
                if r.get('clipping_risk'):
                    lines.append(f'  [WARN] near clipping')
                lines.append('')
            else:
                lines.append(f'[FAIL] {name}')
                lines.append(f'  Error: {r.get("error", "unknown")}')
                lines.append('')

        self.result_text = '\n'.join(lines)


class AudioBoosterApp(App):
    settings = {}

    def build(self):
        self.title = 'Audio Booster'
        Builder.load_string(KV)
        sm = ScreenManager()
        sm.add_widget(MainScreen())
        sm.add_widget(SettingsScreen())
        sm.add_widget(ResultScreen())
        return sm

    def on_start(self):
        if platform == 'android':
            request_permissions([
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
            ])


if __name__ == '__main__':
    AudioBoosterApp().run()
