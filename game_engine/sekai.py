import random
import uuid
from typing import TYPE_CHECKING

from models import Room, Phase, SekaiNoMikataState, SekaiAnswer

if TYPE_CHECKING:
    from .base import GameEngine


class SekaiGame:
    def __init__(self, engine: 'GameEngine'):
        self.engine = engine

    def process_message(self, room: Room, client_id: str, msg_type: str, payload: dict) -> bool:
        """セカイノミカタのメッセージ処理"""
        if msg_type == "SEKAI_SUBMIT_ANSWER":
            text = payload.get("text", "")
            return self.submit_answer(room, client_id, text)

        elif msg_type == "SEKAI_SELECT_ANSWER":
            answer_id = payload.get("answer_id", "")
            return self.select_answer(room, client_id, answer_id)

        elif msg_type == "SEKAI_NEXT_ROUND":
            self.next_round(room)
            return True

        return False

    def setup(self, room: Room):
        """セカイノミカタの初期化"""
        player_ids = list(room.players.keys())
        if not player_ids:
            return

        # スコアをリセット
        for player in room.players.values():
            player.score = 0

        # 勝者をリセット
        room.winner_id = None

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
        self._start_round(room)

    def _start_round(self, room: Room):
        """セカイノミカタの新ラウンド開始"""
        if not room.sekai_state:
            return

        state = room.sekai_state

        # 親を設定
        state.current_reader_id = state.reader_order[state.current_reader_index]

        # お題を選択（使用済みを避ける）
        available_questions = [q for q in self.engine.sekai_questions if q not in state.used_questions]
        if not available_questions:
            state.used_questions = []
            available_questions = self.engine.sekai_questions

        state.current_question = random.choice(available_questions)
        state.used_questions.append(state.current_question)

        # 各プレイヤー（親以外）に単語の選択肢を配布（偏り防止）
        state.word_choices = {}

        # 使用可能な単語を取得（使用済みを避ける）
        available_words = [w for w in self.engine.sekai_words if w not in state.used_words]

        # 使用済みが多すぎたらリセット（残り50個未満で）
        if len(available_words) < 50:
            state.used_words = []
            available_words = self.engine.sekai_words.copy()

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

    def submit_answer(self, room: Room, client_id: str, text: str) -> bool:
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
            self._prepare_judging(room)

        return True

    def _prepare_judging(self, room: Room):
        """セカイノミカタの判定フェーズを準備"""
        if not room.sekai_state:
            return

        state = room.sekai_state

        # ダミー回答を追加（山札から2枚、4人以上は1枚）
        num_dummies = 2 if len(room.players) <= 3 else 1
        dummy_words = random.sample(self.engine.sekai_words, min(num_dummies, len(self.engine.sekai_words)))

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

    def select_answer(self, room: Room, client_id: str, answer_id: str) -> bool:
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

    def next_round(self, room: Room):
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
        self._start_round(room)
