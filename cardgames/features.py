"""Session, preferences and training controls shared by all four games."""
import copy
import queue
import threading
import tkinter as tk
from tkinter import ttk
from . import catalog, cardart, i18n, training, ui
from .session import SessionStore
from .preferences import Preferences, SPEEDS


class AppFeatures:
    def init_features(self):
        folder = self.records.path.parent
        self.preferences = Preferences(folder / 'preferences.json')
        self.sessions = SessionStore(folder / 'session.json')
        self.language = self.preferences.data['language']
        self.speed = self.preferences.data['speed']
        self.deck_style = self.preferences.data['deck']
        self.game_kind = self.preferences.data['game']
        spec = catalog.spec_for(self.game_kind)
        level = self.preferences.data['difficulty']
        self.difficulty = level if level in spec.levels else 'normal'
        target = self.preferences.data['target']
        self.target = target if target in spec.targets else spec.default_target
        self.sort_mode = self.preferences.data['sort']
        self._worker_token = 0
        self._worker_poll = None
        self._worker_busy = False
        self._last_preference_state = None
        self._training_used = False
        self.toolbar = tk.Frame(self, bg=ui.PANEL_BG)
        self.toolbar.pack(fill='x')
        self.feature_buttons = []
        for label, command in [('Resume game', self.resume_game),
                               ('Hint', self.show_hint), ('Review', self.show_review),
                               ('Settings', self.show_settings)]:
            button = tk.Button(self.toolbar, command=command, takefocus=True,
                               highlightthickness=0)
            button.pack(side='left', padx=4, pady=3)
            self.feature_buttons.append((label, button))
        self.training_label = tk.Label(self.toolbar, bg=ui.PANEL_BG, fg=ui.ACCENT)
        self.training_label.pack(side="right", padx=12)
        self.update_feature_labels()

    def tr(self, text):
        if text in (self.player, str(self.records.path), str(self.records.text_path)):
            return text
        return i18n.translate(text, self.language, self.deck_style == "italian")

    def update_feature_labels(self):
        for label, button in self.feature_buttons:
            enabled = True
            if label == 'Resume game':
                enabled = self.state == 'menu' and self.sessions.path.exists() and self.overlay is None
            elif label == 'Hint':
                enabled = self.state == 'human' and self.overlay is None
            elif label == 'Review':
                enabled = self.state != 'menu' and self.game is not None and self.overlay is None
            button.configure(text=self.tr(label), state='normal' if enabled else 'disabled')
        self.training_label.configure(text=self.tr('Training') if self._training_used and self.state != 'menu' else '')
        cardart.DECK = self.deck_style

    def delay(self, milliseconds):
        return max(1, round(milliseconds * SPEEDS[self.speed]))

    def save_preferences(self):
        data = self.preferences.data
        data.update(language=self.language, speed=self.speed, deck=self.deck_style,
                    game=self.game_kind, difficulty=self.difficulty,
                    target=self.target, sort=self.sort_mode)
        state = tuple(data.items())
        if state != self._last_preference_state:
            try:
                self.preferences.save()
                self._last_preference_state = state
            except OSError as exc:
                self.status_text = f'Cannot save settings: {exc}'

    def checkpoint(self):
        if self.state == 'menu' or self.game is None:
            return
        try:
            if self.game.game_over and self._recorded and (
                    self.game_kind == 'briscola' or self.match.over):
                self.sessions.clear()
                return
            self.sessions.save({
                'game': self.game, 'game_kind': self.game_kind,
                'match': self.match if self.game_kind != 'briscola' else None,
                'player': self.player, 'difficulty': self.difficulty,
                'target': self.target, 'next_leader': self.next_leader,
                'recorded': self._recorded, 'log_lines': self.log_lines,
                'training_used': self._training_used,
                'sort_mode': self.sort_mode})
        except (OSError, ValueError) as exc:
            self.status_text = f'Cannot save game: {exc}'

    def resume_game(self):
        try:
            saved = self.sessions.load()
        except ValueError as exc:
            self.show_overlay(self.tr('Resume game'), self.tr(str(exc)))
            return
        if saved is None:
            self.show_overlay('Resume game', 'No saved game is available.')
            return
        self._cancel_pending()
        self.overlay = None
        self.game = saved['game']
        self.game_kind = saved['game_kind']
        self.match = saved['match']
        self.player = saved['player']
        self.difficulty = saved['difficulty']
        self.target = saved['target']
        self.next_leader = saved['next_leader']
        self._recorded = saved['recorded']
        self.log_lines = saved['log_lines']
        self.sort_mode = saved.get('sort_mode', 'suit')
        self._training_used = saved.get('training_used', False)
        self._new_match = False
        self.hover.clear()
        self.selected.clear()
        self.table_pick.clear()
        self.hovered = None
        self.hand_first = 0
        self.hand_hidden = False
        self._anim_offset = None
        self.records.set_player(self.player)
        if self.game_kind == 'briscola':
            self._advance()
        elif self.game_kind == 'tressette':
            self.tressette_advance()
        else:
            self.after_move()

    def show_hint(self):
        if self.overlay is not None:
            return
        if self.state != 'human' or self.game is None:
            self.show_overlay('Hint', 'Wait for your turn to request a hint.')
            return
        self._training_used = True
        self.show_overlay('Hint', training.suggest(self.game_kind, self.game)
                          + '\n\nTraining game: this match will not affect your statistics.')

    def show_review(self):
        if self.overlay is not None:
            return
        history = getattr(self.game, 'history', [])
        if history:
            result = history[-1]
            who = 'You' if result.winner == 0 else 'The computer'
            value = getattr(result, 'points', getattr(result, 'thirds', 0))
            units = 'thirds' if self.game_kind == 'tressette' else 'points'
            body = (f'{result.lead[1]} / {result.follow[1]}\n'
                    f'{who} takes the trick: +{value} {units}.')
        elif self.log_lines:
            body = '\n'.join(' '.join(line) for line in self.log_lines[:8])
        else:
            body = 'No completed moves to review yet.'
        self.show_overlay('Review', body)

    def show_settings(self):
        if getattr(self, '_settings_window', None) is not None:
            self._settings_window.lift()
            return
        window = tk.Toplevel(self)
        self._settings_window = window
        window.title(self.tr('Settings'))
        variables = {}
        choices = {
            'language': [('Italiano', 'it'), ('English', 'en')],
            'speed': [('Slow', 'slow'), ('Normal', 'normal'), ('Fast', 'fast')],
            'deck_style': [('French suits', 'french'), ('Italian suits', 'italian')]}
        for row, (key, options) in enumerate(choices.items()):
            label = {'language': 'Language', 'speed': 'Animation speed',
                     'deck_style': 'Cards'}[key]
            ttk.Label(window, text=self.tr(label)).grid(row=row, column=0, padx=16, pady=10, sticky='w')
            labels = [self.tr(label) for label, _ in options]
            current = next(i for i, (_, value) in enumerate(options) if value == getattr(self, key))
            box = ttk.Combobox(window, values=labels, state='readonly', width=22)
            box.current(current)
            box.grid(row=row, column=1, padx=16, pady=10)
            variables[key] = (box, options)
        def close():
            self._settings_window = None
            window.destroy()
        def apply():
            for key, (box, options) in variables.items():
                setattr(self, key, options[box.current()][1])
            self.update_feature_labels()
            self.save_preferences()
            self.render()
            if self.stats_window is not None:
                self._close_stats_window()
                self.show_statistics()
            close()
        ttk.Button(window, text=self.tr('Save'), command=apply).grid(row=3, column=1, padx=16, pady=16, sticky='e')
        window.protocol('WM_DELETE_WINDOW', close)
        window.bind('<Escape>', lambda _: close())

    def cancel_worker(self):
        self._worker_token += 1
        self._worker_busy = False
        if self._worker_poll is not None:
            self.after_cancel(self._worker_poll)
            self._worker_poll = None

    def compute_ai(self, choose, apply):
        """Workers only see a copy; polling and all Tk calls stay on the UI thread."""
        if self._worker_busy:
            return
        self._pending = None
        self._worker_busy = True
        token = self._worker_token
        original = self.game
        snapshot = copy.deepcopy(original)
        mailbox = queue.Queue()
        def work():
            try:
                mailbox.put((True, choose(snapshot)))
            except Exception as exc:
                mailbox.put((False, exc))
        def poll():
            self._worker_poll = None
            if token != self._worker_token or original is not self.game:
                return
            try:
                ok, result = mailbox.get_nowait()
            except queue.Empty:
                self._worker_poll = self.after(10, poll)
                return
            self._worker_busy = False
            if ok:
                apply(result)
            else:
                self.report_callback_exception(type(result), result, result.__traceback__)
        threading.Thread(target=work, daemon=True, name='cardgames-ai').start()
        self._worker_poll = self.after(10, poll)
