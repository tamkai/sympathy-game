import random
from typing import TYPE_CHECKING

from models import Room, Phase, ItoState, ItoPlayedCard

if TYPE_CHECKING:
    from .base import GameEngine


class ItoGame:
    def __init__(self, engine: 'GameEngine'):
        self.engine = engine

    def process_message(self, room: Room, client_id: str, msg_type: str, payload: dict) -> bool:
        """itoゲームのメッセージ処理"""
        if msg_type == "ITO_PLAY_CARD":
            return self.play_card(room, client_id)

        elif msg_type == "ITO_NEXT_STAGE":
            self.next_stage(room)
            return True

        elif msg_type == "ITO_SHOW_RESULT":
            room.phase = Phase.RESULT
            return True

        elif msg_type == "NEXT_ROUND":
            # INSTRUCTIONからANSWERINGへの遷移
            room.phase = Phase.ANSWERING
            return True

        return False

    def setup(self, room: Room):
        """itoゲームの初期化"""
        player_ids = list(room.players.keys())
        if not player_ids:
            return

        # お題を選択
        available_topics = [t for t in self.engine.ito_topics if t not in (room.ito_state.used_topics if room.ito_state else [])]
        if not available_topics:
            available_topics = self.engine.ito_topics.copy()

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

    def play_card(self, room: Room, client_id: str) -> bool:
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

    def next_stage(self, room: Room):
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
        available_topics = [t for t in self.engine.ito_topics if t not in state.used_topics]
        if not available_topics:
            state.used_topics = []
            available_topics = self.engine.ito_topics.copy()

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
