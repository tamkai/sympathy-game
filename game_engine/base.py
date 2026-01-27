import csv
from typing import TYPE_CHECKING

from models import Room, Phase, GameMode

if TYPE_CHECKING:
    from .sympathy import SympathyGame
    from .word_wolf import WordWolfGame
    from .sekai import SekaiGame
    from .ito import ItoGame
    from .werewolf import WerewolfGame


class GameEngine:
    def __init__(self):
        self.questions: list[str] = []
        self.word_wolf_topics: list[dict] = []
        self.sekai_questions: list[str] = []
        self.sekai_words: list[str] = []
        self.ito_topics: list[str] = []
        self.load_data()

        # 各ゲームモジュールを初期化
        from .sympathy import SympathyGame
        from .word_wolf import WordWolfGame
        from .sekai import SekaiGame
        from .ito import ItoGame
        from .werewolf import WerewolfGame

        self.sympathy = SympathyGame(self)
        self.word_wolf = WordWolfGame(self)
        self.sekai = SekaiGame(self)
        self.ito = ItoGame(self)
        self.werewolf = WerewolfGame(self)

    def load_data(self):
        # Load Questions
        try:
            with open("questions.csv", "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.questions = [row["question"] for row in reader]
        except FileNotFoundError:
            print("Warning: questions.csv not found. Using default questions.")
            self.questions = ["好きな食べ物は？", "無人島に持っていくなら？", "子供の頃の夢は？"]

        # Load Word Wolf Topics
        try:
            with open("word_wolf_topics.csv", "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.word_wolf_topics = [{"majority": row["majority"], "minority": row["minority"]} for row in reader]
        except FileNotFoundError:
            print("Warning: word_wolf_topics.csv not found.")
            self.word_wolf_topics = [{"majority": "りんご", "minority": "なし"}]

        # Load Sekai No Mikata Questions
        try:
            with open("sekai_questions.csv", "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.sekai_questions = [row["question"] for row in reader]
        except FileNotFoundError:
            print("Warning: sekai_questions.csv not found. Using defaults.")
            self.sekai_questions = [
                "＿＿＿が足りないから今日は早く帰ります",
                "「＿＿＿」これが私の座右の銘です",
            ]

        # Load Sekai No Mikata Words
        try:
            with open("sekai_words.csv", "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.sekai_words = [row["word"] for row in reader]
        except FileNotFoundError:
            print("Warning: sekai_words.csv not found. Using defaults.")
            self.sekai_words = [
                "愛", "お金", "時間", "友情", "睡眠", "カレー", "猫", "上司",
            ]

        # Load ito Topics
        try:
            with open("ito_topics.csv", "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.ito_topics = [row["topic"] for row in reader]
        except FileNotFoundError:
            print("Warning: ito_topics.csv not found. Using defaults.")
            self.ito_topics = [
                "怖いもの", "かわいいもの", "おいしいもの", "高いもの",
            ]

    def process_message(self, room: Room, client_id: str, msg_type: str, payload: dict) -> bool:
        """
        Process the message and update room state.
        Returns True if state should be broadcasted.
        """
        # 共通メッセージ処理
        if msg_type == "JOIN":
            name = payload.get("name", "Unknown")
            room.add_player(client_id, name)
            return True

        if msg_type == "START_GAME":
            mode_str = payload.get("mode", "SYMPATHY")
            self.start_game(room, mode_str)
            return True

        if msg_type == "UPDATE_CONFIG":
            self.update_config(room, payload)
            return True

        if msg_type == "RESET_GAME":
            room.reset_game()
            room.phase = Phase.LOBBY
            return True

        # ゲームモード別メッセージ処理
        if room.mode == GameMode.SYMPATHY:
            return self.sympathy.process_message(room, client_id, msg_type, payload)
        elif room.mode == GameMode.WORD_WOLF:
            return self.word_wolf.process_message(room, client_id, msg_type, payload)
        elif room.mode == GameMode.SEKAI_NO_MIKATA:
            return self.sekai.process_message(room, client_id, msg_type, payload)
        elif room.mode == GameMode.ITO:
            return self.ito.process_message(room, client_id, msg_type, payload)
        elif room.mode == GameMode.ONE_NIGHT_WEREWOLF:
            return self.werewolf.process_message(room, client_id, msg_type, payload)

        return False

    def start_game(self, room: Room, mode_str: str):
        room.mode = GameMode(mode_str)
        if room.mode == GameMode.SYMPATHY:
            room.phase = Phase.INSTRUCTION
            room.reset_round()
        elif room.mode == GameMode.WORD_WOLF:
            room.phase = Phase.DESCRIPTION
            self.word_wolf.setup(room)
        elif room.mode == GameMode.SEKAI_NO_MIKATA:
            self.sekai.setup(room)
        elif room.mode == GameMode.ITO:
            self.ito.setup(room)
        elif room.mode == GameMode.ONE_NIGHT_WEREWOLF:
            self.werewolf.setup(room)

    def update_config(self, room: Room, payload: dict):
        config_type = payload.get("type")
        value = payload.get("value")

        if config_type == "speed_star" and value is not None:
            room.config_speed_star = value
        elif config_type == "shuffle" and value is not None:
            room.config_shuffle = value
        elif config_type == "discussion_time" and value is not None:
            room.config_discussion_time = value
        elif config_type == "ito_coop" and value is not None:
            room.config_ito_coop = value
            if room.ito_state:
                room.ito_state.is_coop_mode = value
        elif config_type == "ito_close_call" and value is not None:
            room.config_ito_close_call = value
            if room.ito_state:
                room.ito_state.close_call_enabled = value
        elif config_type == "werewolf_madman" and value is not None:
            room.config_werewolf_madman = value
