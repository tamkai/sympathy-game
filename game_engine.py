
import random
import time
import csv
import uuid
from typing import Dict, List, Optional
from models import Room, Player, Phase, GameMode, WordWolfState, Answer, SekaiNoMikataState, SekaiAnswer

class GameEngine:
    def __init__(self):
        self.questions = []
        self.word_wolf_topics = []
        self.sekai_questions = []  # お題（空欄付き）
        self.sekai_words = []  # 単語リスト
        self.load_data()

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
                "朝起きて最初にすることは＿＿＿",
                "デートで絶対に行きたくない場所は＿＿＿",
                "もし総理大臣になったら最初に＿＿＿する"
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
                "深夜のコンビニ", "推しのグッズ", "おばあちゃんの知恵袋", "世界平和",
                "チョコレート", "二度寝", "WiFi", "エナジードリンク", "筋肉",
                "優しさ", "勇気", "納豆", "マヨネーズ", "宇宙", "謎の生命体",
                "AIの反乱", "タイムマシン", "バナナの皮", "心の余裕", "推し活",
                "青春", "黒歴史", "初恋", "最後の晩餐", "永遠の命"
            ]

    def process_message(self, room: Room, client_id: str, msg_type: str, payload: dict) -> bool:
        """
        Process the message and update room state.
        Returns True if state should be broadcasted.
        """
        should_broadcast = False

        if msg_type == "JOIN":
            name = payload.get("name", "Unknown")
            room.add_player(client_id, name)
            should_broadcast = True

        elif msg_type == "START_GAME":
            mode_str = payload.get("mode", "SYMPATHY")
            self.start_game(room, mode_str)
            should_broadcast = True

        elif msg_type == "START_ROUND":
            if room.mode == GameMode.SYMPATHY:
                room.phase = Phase.ANSWERING
                should_broadcast = True

        elif msg_type == "START_DISCUSSION":
            if room.mode == GameMode.WORD_WOLF:
                room.phase = Phase.ANSWERING
                should_broadcast = True

        elif msg_type == "UPDATE_CONFIG":
            self.update_config(room, payload)
            should_broadcast = True

        elif msg_type == "SUBMIT_ANSWER":
            text = payload.get("text", "")
            use_shuffle = payload.get("use_shuffle", False)
            if self.submit_answer(room, client_id, text, use_shuffle):
                should_broadcast = True

        elif msg_type == "SKIP_TO_JUDGING":
            self.skip_to_judging(room)
            should_broadcast = True

        elif msg_type == "UPDATE_GROUPING":
            updates = payload.get("answers", {})
            for ans_id, data in updates.items():
                if ans_id in room.answers:
                    room.answers[ans_id].group_id = data.get("group_id", ans_id)
            should_broadcast = True

        elif msg_type == "FINISH_JUDGING":
            self.finish_judging(room)
            should_broadcast = True

        elif msg_type == "VOTE_WOLF":
            target_player_id = payload.get("target_player_id")
            if self.vote_wolf(room, client_id, target_player_id):
                should_broadcast = True

        elif msg_type == "NEXT_ROUND":
            self.next_round(room)
            should_broadcast = True

        elif msg_type == "RESET_GAME":
            room.reset_game()
            room.phase = Phase.LOBBY
            should_broadcast = True

        # Sekai No Mikata Messages
        elif msg_type == "SEKAI_SUBMIT_ANSWER":
            text = payload.get("text", "")
            if self.sekai_submit_answer(room, client_id, text):
                should_broadcast = True

        elif msg_type == "SEKAI_SELECT_ANSWER":
            answer_id = payload.get("answer_id", "")
            if self.sekai_select_answer(room, client_id, answer_id):
                should_broadcast = True

        elif msg_type == "SEKAI_NEXT_ROUND":
            self.sekai_next_round(room)
            should_broadcast = True

        return should_broadcast

    def start_game(self, room: Room, mode_str: str):
        room.mode = GameMode(mode_str)
        if room.mode == GameMode.SYMPATHY:
            room.phase = Phase.INSTRUCTION
            room.reset_round() # Ensure fresh start
            # Pick initial question logic duplicated from next_round usually?
            # Or wait for NEXT_ROUND call?
            # Original code did INSTRUCTION only.
        elif room.mode == GameMode.WORD_WOLF:
            room.phase = Phase.DESCRIPTION
            self.setup_word_wolf(room)
        elif room.mode == GameMode.SEKAI_NO_MIKATA:
            self.setup_sekai_no_mikata(room)

    def setup_word_wolf(self, room: Room):
        # Topics
        majority_topic = "Topic A"
        minority_topic = "Topic B"
        try:
            if self.word_wolf_topics:
                topic_pair = random.choice(self.word_wolf_topics)
                majority_topic = topic_pair.get("majority", "A")
                minority_topic = topic_pair.get("minority", "B")
        except Exception as e:
            print(f"Topic error: {e}")

        # Assign Roles
        player_ids = list(room.players.keys())
        wolf_ids = []
        if player_ids:
            try:
                # 1 Wolf
                wolf_ids = random.sample(player_ids, 1)
            except ValueError:
                wolf_ids = [player_ids[0]]
        
        room.word_wolf_state = WordWolfState(
            wolf_ids=wolf_ids,
            topics={},
            discussion_end_time=time.time() + room.config_discussion_time,
            votes={}
        )
        
        for pid in player_ids:
            if pid in wolf_ids:
                room.word_wolf_state.topics[pid] = minority_topic
            else:
                room.word_wolf_state.topics[pid] = majority_topic

    def update_config(self, room: Room, payload: dict):
        config_type = payload.get("type")
        value = payload.get("value")
        
        if config_type == "speed_star" and value is not None:
            room.config_speed_star = value
        elif config_type == "shuffle" and value is not None:
            room.config_shuffle = value
        elif config_type == "discussion_time" and value is not None:
            room.config_discussion_time = value

    def submit_answer(self, room: Room, client_id: str, text: str, use_shuffle: bool) -> bool:
        if not text:
            return False
        player = room.players.get(client_id)
        if not player:
            return False

        player.has_answered = True
        
        # Handle Shuffle Usage
        did_use_shuffle = False
        if use_shuffle and room.config_shuffle and player.shuffle_remaining > 0:
            player.shuffle_remaining -= 1
            room.shuffle_triggered_in_round = True
            did_use_shuffle = True

        ans_id = str(uuid.uuid4())
        room.answers[ans_id] = Answer(
            answer_id=ans_id,
            player_id=client_id,
            player_name=player.name,
            raw_text=text,
            normalized_text=text.strip(),
            group_id=ans_id,
            timestamp=time.time(),
            used_shuffle=did_use_shuffle
        )
        return True

    def skip_to_judging(self, room: Room):
        if room.mode == GameMode.SYMPATHY:
            # SHUFFLE LOGIC
            if room.shuffle_triggered_in_round:
                all_texts = [a.raw_text for a in room.answers.values()]
                random.shuffle(all_texts)
                sub_keys = list(room.answers.keys())
                for i, key in enumerate(sub_keys):
                    if i < len(all_texts):
                        room.answers[key].raw_text = all_texts[i]
                        room.answers[key].normalized_text = all_texts[i].strip()

            # AUTO-GROUPING
            text_to_group_id = {}
            for ans_id, answer in room.answers.items():
                norm_text = answer.normalized_text.lower()
                if norm_text in text_to_group_id:
                    answer.group_id = text_to_group_id[norm_text]
                else:
                    text_to_group_id[norm_text] = ans_id
                    answer.group_id = ans_id
            
            room.phase = Phase.JUDGING
            
        elif room.mode == GameMode.WORD_WOLF:
            room.phase = Phase.JUDGING

    def finish_judging(self, room: Room):
        if room.mode == GameMode.SYMPATHY:
            try:
                room.calculate_results()
            except Exception as e:
                print(f"Error calculating results: {e}")
            room.phase = Phase.RESULT
        elif room.mode == GameMode.WORD_WOLF:
             if room.word_wolf_state:
                room.word_wolf_state.calculate_vote_results(room.players)
             room.phase = Phase.RESULT

    def vote_wolf(self, room: Room, client_id: str, target_player_id: str) -> bool:
        if room.mode == GameMode.WORD_WOLF and room.word_wolf_state:
            if target_player_id and target_player_id in room.players:
                room.word_wolf_state.votes[client_id] = target_player_id
                
                if client_id in room.players:
                    room.players[client_id].has_answered = True
                
                if len(room.word_wolf_state.votes) == len(room.players):
                    room.word_wolf_state.calculate_vote_results(room.players)
                    room.phase = Phase.RESULT
                return True
        return False

    def next_round(self, room: Room):
        room.reset_round()
        
        if room.mode == GameMode.SYMPATHY:
            # Use Sekai Words instead of Questions
            source_list = self.sekai_words if self.sekai_words else self.questions
            
            available_questions = [q for q in source_list if q not in room.used_questions]
            
            if not available_questions:
                 room.used_questions = set()
                 available_questions = source_list
            
            new_q = random.choice(available_questions)
            room.current_question = new_q
            room.used_questions.add(new_q)
            
            room.phase = Phase.ANSWERING

        elif room.mode == GameMode.WORD_WOLF:
            room.phase = Phase.DESCRIPTION
            self.setup_word_wolf(room)

    # =====================
    # Sekai No Mikata Logic
    # =====================

    def setup_sekai_no_mikata(self, room: Room):
        """セカイノミカタの初期化"""
        player_ids = list(room.players.keys())
        if not player_ids:
            return

        # 親の順番をシャッフル
        reader_order = player_ids.copy()
        random.shuffle(reader_order)

        room.sekai_state = SekaiNoMikataState(
            reader_order=reader_order,
            current_reader_index=0,
            current_reader_id=reader_order[0],
            round_number=1,
            winning_score=5 if len(player_ids) <= 4 else 3
        )

        # 最初のラウンドを開始
        self._sekai_start_round(room)

    def _sekai_start_round(self, room: Room):
        """セカイノミカタの新ラウンド開始"""
        if not room.sekai_state:
            return

        state = room.sekai_state

        # 親を設定
        state.current_reader_id = state.reader_order[state.current_reader_index]

        # お題を選択（使用済みを避ける）
        available_questions = [q for q in self.sekai_questions if q not in state.used_questions]
        if not available_questions:
            state.used_questions = []
            available_questions = self.sekai_questions

        state.current_question = random.choice(available_questions)
        state.used_questions.append(state.current_question)

        # 各プレイヤー（親以外）に単語の選択肢を配布（偏り防止）
        state.word_choices = {}

        # 使用可能な単語を取得（使用済みを避ける）
        available_words = [w for w in self.sekai_words if w not in state.used_words]

        # 使用済みが多すぎたらリセット（残り50個未満で）
        if len(available_words) < 50:
            state.used_words = []
            available_words = self.sekai_words.copy()

        # このラウンドで配布する単語を管理
        round_used_words = []

        for pid in room.players.keys():
            if pid != state.current_reader_id:
                # まだこのラウンドで使われていない単語から選択
                pool = [w for w in available_words if w not in round_used_words]

                # プールが足りなければリセット
                if len(pool) < 8:
                    pool = available_words.copy()

                # 8個の単語をランダムに選択
                choices = random.sample(pool, min(8, len(pool)))
                state.word_choices[pid] = choices

                # このラウンドで使用済みにする
                round_used_words.extend(choices)

        # 使用済み単語を記録
        state.used_words.extend(round_used_words)

        # 回答をリセット
        state.submitted_answers = {}
        state.dummy_answers = []
        state.all_answers_for_display = []
        state.selected_answer_id = None

        # プレイヤーの回答状態をリセット
        for p in room.players.values():
            p.has_answered = False

        # 親は自動的に「回答済み」にする（回答しないため）
        if state.current_reader_id in room.players:
            room.players[state.current_reader_id].has_answered = True

        room.phase = Phase.ANSWERING

    def sekai_submit_answer(self, room: Room, client_id: str, text: str) -> bool:
        """セカイノミカタの回答を提出"""
        if not room.sekai_state or not text:
            return False

        state = room.sekai_state
        player = room.players.get(client_id)

        if not player or client_id == state.current_reader_id:
            return False  # 親は回答できない

        if player.has_answered:
            return False  # 既に回答済み

        # 回答を作成
        ans_id = str(uuid.uuid4())
        answer = SekaiAnswer(
            answer_id=ans_id,
            player_id=client_id,
            player_name=player.name,
            text=text,
            is_dummy=False
        )
        state.submitted_answers[ans_id] = answer
        player.has_answered = True

        # 全員回答したか確認
        all_answered = all(
            p.has_answered for pid, p in room.players.items()
        )

        if all_answered:
            self._sekai_prepare_judging(room)

        return True

    def _sekai_prepare_judging(self, room: Room):
        """セカイノミカタの判定フェーズを準備"""
        if not room.sekai_state:
            return

        state = room.sekai_state

        # ダミー回答を追加（山札から2枚、4人以上は1枚）
        num_dummies = 2 if len(room.players) <= 3 else 1
        dummy_words = random.sample(self.sekai_words, min(num_dummies, len(self.sekai_words)))

        for word in dummy_words:
            ans_id = str(uuid.uuid4())
            dummy = SekaiAnswer(
                answer_id=ans_id,
                player_id="DUMMY",
                player_name="山札",
                text=word,
                is_dummy=True
            )
            state.dummy_answers.append(dummy)

        # 全回答をまとめてシャッフル
        all_answers = list(state.submitted_answers.values()) + state.dummy_answers
        random.shuffle(all_answers)
        state.all_answers_for_display = all_answers

        room.phase = Phase.JUDGING

    def sekai_select_answer(self, room: Room, client_id: str, answer_id: str) -> bool:
        """親が回答を選択（ホストからも選択可能）"""
        if not room.sekai_state:
            return False

        state = room.sekai_state

        # 親またはホストが選択可能
        is_host = client_id.startswith('HOST-')
        if not is_host and client_id != state.current_reader_id:
            return False

        # 回答が存在するか確認
        selected_answer = None
        for ans in state.all_answers_for_display:
            if ans.answer_id == answer_id:
                selected_answer = ans
                break

        if not selected_answer:
            return False

        state.selected_answer_id = answer_id

        # 得点計算
        if selected_answer.is_dummy:
            # ダミーを選んだ → 全員にマイナス1点（親も含む）
            for p in room.players.values():
                p.score = max(0, p.score - 1)
        else:
            # プレイヤーの回答を選んだ → そのプレイヤーに1点
            if selected_answer.player_id in room.players:
                room.players[selected_answer.player_id].score += 1

        # 勝者チェック
        for p in room.players.values():
            if p.score >= state.winning_score:
                room.winner_id = p.player_id
                break

        room.phase = Phase.RESULT
        return True

    def sekai_next_round(self, room: Room):
        """セカイノミカタの次のラウンドへ"""
        if not room.sekai_state:
            return

        state = room.sekai_state

        # 勝者がいたらゲーム終了（LOBBYには戻さない、RESULTのまま）
        if room.winner_id:
            return

        # 親を次の人に
        state.current_reader_index = (state.current_reader_index + 1) % len(state.reader_order)
        state.round_number += 1

        # 新しいラウンドを開始
        self._sekai_start_round(room)
