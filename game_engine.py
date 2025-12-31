
import random
import time
import csv
import uuid
from typing import Dict, List, Optional
from models import Room, Player, Phase, GameMode, WordWolfState, Answer, SekaiNoMikataState, SekaiAnswer, ItoState, ItoPlayedCard, WerewolfState, WerewolfRole, WerewolfNightPhase

class GameEngine:
    def __init__(self):
        self.questions = []
        self.word_wolf_topics = []
        self.sekai_questions = []  # お題（空欄付き）
        self.sekai_words = []  # 単語リスト
        self.ito_topics = []  # itoのお題
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

        # Load ito Topics
        try:
            with open("ito_topics.csv", "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.ito_topics = [row["topic"] for row in reader]
        except FileNotFoundError:
            print("Warning: ito_topics.csv not found. Using defaults.")
            self.ito_topics = [
                "怖いもの", "かわいいもの", "おいしいもの", "高いもの",
                "人気のある芸能人", "強い動物", "大きいもの"
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

        # ito Messages
        elif msg_type == "ITO_PLAY_CARD":
            if self.ito_play_card(room, client_id):
                should_broadcast = True

        elif msg_type == "ITO_NEXT_STAGE":
            self.ito_next_stage(room)
            should_broadcast = True

        elif msg_type == "ITO_SHOW_RESULT":
            room.phase = Phase.RESULT
            should_broadcast = True

        # One Night Werewolf Messages
        elif msg_type == "WEREWOLF_START_NIGHT":
            if self.werewolf_start_night(room):
                should_broadcast = True

        elif msg_type == "WEREWOLF_ADVANCE_NIGHT":
            if self.werewolf_advance_night(room):
                should_broadcast = True

        elif msg_type == "WEREWOLF_NIGHT_ACTION":
            action = payload.get("action", "")
            target = payload.get("target", "")
            if self.werewolf_night_action(room, client_id, action, target):
                should_broadcast = True

        elif msg_type == "WEREWOLF_START_DISCUSSION":
            if self.werewolf_start_discussion(room):
                should_broadcast = True

        elif msg_type == "WEREWOLF_VOTE":
            target_id = payload.get("target_player_id", "")
            if self.werewolf_vote(room, client_id, target_id):
                should_broadcast = True

        elif msg_type == "WEREWOLF_FINISH_VOTING":
            if self.werewolf_finish_voting(room):
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
        elif room.mode == GameMode.ITO:
            self.setup_ito(room)
        elif room.mode == GameMode.ONE_NIGHT_WEREWOLF:
            self.setup_werewolf(room)

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

        elif room.mode == GameMode.ITO:
            # INSTRUCTIONからANSWERINGへの遷移
            room.phase = Phase.ANSWERING

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

    # =====================
    # ito Logic
    # =====================

    def setup_ito(self, room: Room):
        """itoゲームの初期化"""
        player_ids = list(room.players.keys())
        if not player_ids:
            return

        # お題を選択
        available_topics = [t for t in self.ito_topics if t not in (room.ito_state.used_topics if room.ito_state else [])]
        if not available_topics:
            available_topics = self.ito_topics.copy()

        topic = random.choice(available_topics)

        # 各プレイヤーに1〜100の数字をランダム配布（重複なし）
        numbers = random.sample(range(1, 101), len(player_ids))
        player_numbers = {pid: num for pid, num in zip(player_ids, numbers)}

        room.ito_state = ItoState(
            is_coop_mode=room.config_ito_coop,
            close_call_enabled=room.config_ito_close_call,
            current_topic=topic,
            used_topics=[topic],
            player_numbers=player_numbers,
            played_cards=[],
            last_played_number=0,
            stage=1,
            life=3,
            is_failed=False,
            stage_cleared=False,
            game_cleared=False,
            game_over=False
        )

        # プレイヤーの回答状態をリセット
        for p in room.players.values():
            p.has_answered = False

        room.phase = Phase.INSTRUCTION  # まずルール説明を表示

    def ito_play_card(self, room: Room, client_id: str) -> bool:
        """itoでカードを出す"""
        if not room.ito_state:
            return False

        state = room.ito_state
        player = room.players.get(client_id)

        if not player:
            return False

        # 既にカードを出している場合は無視
        if player.has_answered:
            return False

        # このプレイヤーの数字を取得
        player_number = state.player_numbers.get(client_id)
        if player_number is None:
            return False

        # カードを出す
        order = len(state.played_cards) + 1

        # 失敗判定：
        # 1. 直前に出されたカードより小さい数字を出した場合
        # 2. まだ出していないプレイヤーの中に、今出した数字より小さい数字を持っている人がいる場合
        is_failed = player_number < state.last_played_number

        if not is_failed:
            # 残りのプレイヤー（まだカードを出していない人）の数字をチェック
            for pid, pnum in state.player_numbers.items():
                if pid == client_id:
                    continue  # 自分自身はスキップ
                other_player = room.players.get(pid)
                if other_player and not other_player.has_answered:
                    # まだ出していないプレイヤーで、自分より小さい数字を持っている人がいる
                    if pnum < player_number:
                        is_failed = True
                        break

        played_card = ItoPlayedCard(
            player_id=client_id,
            player_name=player.name,
            number=player_number,
            order=order,
            is_failed=is_failed
        )
        state.played_cards.append(played_card)
        player.has_answered = True

        # 失敗判定
        if is_failed:
            state.is_failed = True
            if state.is_coop_mode:
                # 協力モード: ライフ減少
                state.life -= 1
                if state.life <= 0:
                    state.game_over = True
                    room.phase = Phase.RESULT
                    return True

        # 最後に出された数字を更新
        state.last_played_number = player_number

        # 全員がカードを出したかチェック
        all_played = all(p.has_answered for p in room.players.values())

        if all_played:
            if state.is_coop_mode:
                # 協力モード
                if state.is_failed:
                    # 失敗してもライフが残っている場合
                    pass  # 次のステージへ進める状態
                else:
                    # ステージクリア
                    state.stage_cleared = True
                    if state.stage >= 3:
                        # 全ステージクリア
                        state.game_cleared = True
                room.phase = Phase.RESULT
            else:
                # 通常モード: 1ラウンドで終了
                state.stage_cleared = not state.is_failed
                room.phase = Phase.RESULT

        return True

    def ito_next_stage(self, room: Room):
        """itoの次のステージへ"""
        if not room.ito_state:
            return

        state = room.ito_state

        # ゲームオーバーまたはゲームクリアの場合は何もしない
        if state.game_over or state.game_cleared:
            return

        # 成功時のみステージをインクリメント（失敗時は同じステージをやり直し）
        if state.stage_cleared:
            state.stage += 1
            # ライフ回復（ステージクリア時、上限3）
            if state.life < 3:
                state.life += 1

            # 3ステージクリアでゲームクリア
            if state.stage > 3:
                state.game_cleared = True
                room.phase = Phase.RESULT
                return

        # お題を選択（新しいお題）
        available_topics = [t for t in self.ito_topics if t not in state.used_topics]
        if not available_topics:
            state.used_topics = []
            available_topics = self.ito_topics.copy()

        topic = random.choice(available_topics)
        state.used_topics.append(topic)
        state.current_topic = topic

        # 新しい数字を配布
        player_ids = list(room.players.keys())
        numbers = random.sample(range(1, 101), len(player_ids))
        state.player_numbers = {pid: num for pid, num in zip(player_ids, numbers)}

        # 状態をリセット
        state.played_cards = []
        state.last_played_number = 0
        state.is_failed = False
        state.stage_cleared = False

        # プレイヤーの回答状態をリセット
        for p in room.players.values():
            p.has_answered = False

        room.phase = Phase.ANSWERING

    # ============================
    # One Night Werewolf Logic
    # ============================

    def setup_werewolf(self, room: Room):
        """ワンナイト人狼の初期化・配役"""
        player_ids = list(room.players.keys())
        num_players = len(player_ids)

        if num_players < 3:
            return  # 最低3人必要

        # プレイヤー数 + 2 枚のカードを準備
        # 人数別の推奨配役:
        # 3人: 人狼2, 村人1, 占い師1, 怪盗1 (計5枚)
        # 4人以上: 人狼2, 狂人1, 村人(n-2), 占い師1, 怪盗1 (計n+2枚)
        # 例: 4人 → 人狼2, 狂人1, 村人1, 占い師1, 怪盗1 (計6枚)
        # 例: 5人 → 人狼2, 狂人1, 村人2, 占い師1, 怪盗1 (計7枚)

        total_cards = num_players + 2
        cards: List[WerewolfRole] = []

        # 必ず入れる役職
        cards.append(WerewolfRole.WEREWOLF)
        cards.append(WerewolfRole.WEREWOLF)
        cards.append(WerewolfRole.SEER)
        cards.append(WerewolfRole.THIEF)

        # 4人以上かつ狂人設定がONの場合は狂人を追加
        if num_players >= 4 and room.config_werewolf_madman:
            cards.append(WerewolfRole.MADMAN)

        # 残りは村人で埋める
        remaining = total_cards - len(cards)
        for _ in range(remaining):
            cards.append(WerewolfRole.VILLAGER)

        # シャッフルして配布
        random.shuffle(cards)

        # プレイヤーに配布
        original_roles: Dict[str, WerewolfRole] = {}
        for i, pid in enumerate(player_ids):
            original_roles[pid] = cards[i]

        # 残り2枚は墓地へ
        graveyard = cards[num_players:]

        # 初期状態 = 現在状態（怪盗交換前）
        current_roles = original_roles.copy()

        room.werewolf_state = WerewolfState(
            original_roles=original_roles,
            graveyard=graveyard,
            current_roles=current_roles,
            night_info={},
            night_phase=WerewolfNightPhase.WAITING,
            night_actions_done={},
            votes={},
            discussion_end_time=0.0,
        )

        # プレイヤーの状態リセット
        for p in room.players.values():
            p.has_answered = False

        room.phase = Phase.INSTRUCTION  # まず役職確認画面

    def werewolf_start_night(self, room: Room) -> bool:
        """夜フェーズを開始（まず全員目を閉じる）"""
        if not room.werewolf_state:
            return False

        state = room.werewolf_state
        state.night_phase = WerewolfNightPhase.CLOSING_EYES
        room.phase = Phase.ANSWERING  # ANSWERINGを夜フェーズとして使用
        return True

    def werewolf_advance_night(self, room: Room) -> bool:
        """夜フェーズを次に進める（自動進行）"""
        if not room.werewolf_state:
            return False

        state = room.werewolf_state

        if state.night_phase == WerewolfNightPhase.CLOSING_EYES:
            # 目を閉じる → 人狼
            state.night_phase = WerewolfNightPhase.WEREWOLF
            state.night_actions_done = {}  # リセット
        elif state.night_phase == WerewolfNightPhase.WEREWOLF:
            # 人狼 → 占い師
            state.night_phase = WerewolfNightPhase.SEER
            state.night_actions_done = {}  # リセット
        elif state.night_phase == WerewolfNightPhase.SEER:
            # 占い師 → 怪盗
            state.night_phase = WerewolfNightPhase.THIEF
            state.night_actions_done = {}  # リセット
        elif state.night_phase == WerewolfNightPhase.THIEF:
            # 怪盗 → 夜終了
            state.night_phase = WerewolfNightPhase.DONE

        return True

    def werewolf_night_action(self, room: Room, client_id: str, action: str, target: str) -> bool:
        """夜の行動を実行"""
        if not room.werewolf_state:
            return False

        state = room.werewolf_state
        player_role = state.original_roles.get(client_id)

        if not player_role:
            return False

        # 人狼の確認（自動で仲間を見る）
        if action == "werewolf_confirm":
            if player_role != WerewolfRole.WEREWOLF:
                return False

            # 仲間の人狼を確認
            werewolf_ids = [pid for pid, role in state.original_roles.items() if role == WerewolfRole.WEREWOLF]
            partner_ids = [pid for pid in werewolf_ids if pid != client_id]

            if partner_ids:
                partner_names = [room.players[pid].name for pid in partner_ids if pid in room.players]
                state.night_info[client_id] = f"仲間の人狼: {', '.join(partner_names)}"
            else:
                state.night_info[client_id] = "あなたは一人狼です（仲間なし）"

            state.night_actions_done[client_id] = True
            return True

        # 占い師の行動
        elif action == "seer_look":
            if player_role != WerewolfRole.SEER:
                return False

            if target.startswith("graveyard_"):
                # 墓地を見る
                try:
                    idx = int(target.split("_")[1])
                    if 0 <= idx < len(state.graveyard):
                        role = state.graveyard[idx]
                        role_name = self._get_seer_result_name(role)  # 狂人は村人として表示
                        state.night_info[client_id] = f"墓地のカード{idx + 1}: {role_name}"
                        state.seer_target = "graveyard"
                        state.seer_graveyard_index = idx
                except (ValueError, IndexError):
                    return False
            else:
                # プレイヤーを占う
                if target not in state.current_roles:
                    return False
                target_role = state.current_roles[target]
                target_name = room.players[target].name if target in room.players else "???"
                role_name = self._get_seer_result_name(target_role)  # 狂人は村人として表示
                state.night_info[client_id] = f"{target_name}の役職: {role_name}"
                state.seer_target = target

            state.night_actions_done[client_id] = True
            return True

        # 怪盗の行動
        elif action == "thief_swap":
            if player_role != WerewolfRole.THIEF:
                return False

            if target == "skip":
                # 交換しない
                state.night_info[client_id] = "交換しませんでした。あなたは怪盗のままです。"
                state.thief_swapped = False
            else:
                # 交換する
                if target not in state.current_roles:
                    return False

                target_role = state.current_roles[target]
                target_name = room.players[target].name if target in room.players else "???"

                # 役職を交換
                state.current_roles[client_id] = target_role
                state.current_roles[target] = WerewolfRole.THIEF

                role_name = self._get_role_name(target_role)
                state.night_info[client_id] = f"{target_name}と交換しました。あなたは{role_name}になりました！"
                state.thief_target = target
                state.thief_swapped = True

            state.night_actions_done[client_id] = True
            return True

        return False

    def _get_role_name(self, role: WerewolfRole) -> str:
        """役職の日本語名を取得"""
        names = {
            WerewolfRole.VILLAGER: "村人",
            WerewolfRole.WEREWOLF: "人狼",
            WerewolfRole.SEER: "占い師",
            WerewolfRole.THIEF: "怪盗",
            WerewolfRole.MADMAN: "狂人",
        }
        return names.get(role, "不明")

    def _get_seer_result_name(self, role: WerewolfRole) -> str:
        """占い師の占い結果用の役職名を取得（狂人は村人として表示）"""
        # 狂人は占い結果では「村人」として表示される
        if role == WerewolfRole.MADMAN:
            return "村人"
        return self._get_role_name(role)

    def werewolf_start_discussion(self, room: Room) -> bool:
        """議論フェーズを開始"""
        if not room.werewolf_state:
            return False

        state = room.werewolf_state
        state.night_phase = WerewolfNightPhase.DONE
        state.discussion_end_time = time.time() + room.config_discussion_time

        # プレイヤーの投票状態をリセット
        for p in room.players.values():
            p.has_answered = False

        room.phase = Phase.JUDGING  # JUDGINGを議論・投票フェーズとして使用
        return True

    def werewolf_vote(self, room: Room, client_id: str, target_id: str) -> bool:
        """投票する"""
        if not room.werewolf_state:
            return False

        state = room.werewolf_state

        if not target_id or target_id not in room.players:
            return False

        # 自分に投票はできない
        if target_id == client_id:
            return False

        state.votes[client_id] = target_id

        if client_id in room.players:
            room.players[client_id].has_answered = True

        return True

    def werewolf_finish_voting(self, room: Room) -> bool:
        """投票を締め切って結果を計算"""
        if not room.werewolf_state:
            return False

        state = room.werewolf_state

        # 結果を計算
        state.calculate_vote_results(room.players)

        room.phase = Phase.RESULT
        return True
