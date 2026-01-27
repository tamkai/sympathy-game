import random
import time
from typing import Dict, List, TYPE_CHECKING

from models import Room, Phase, WerewolfState, WerewolfRole, WerewolfNightPhase

if TYPE_CHECKING:
    from .base import GameEngine


class WerewolfGame:
    def __init__(self, engine: 'GameEngine'):
        self.engine = engine

    def process_message(self, room: Room, client_id: str, msg_type: str, payload: dict) -> bool:
        """ワンナイト人狼のメッセージ処理"""
        if msg_type == "WEREWOLF_START_NIGHT":
            return self.start_night(room)

        elif msg_type == "WEREWOLF_ADVANCE_NIGHT":
            return self.advance_night(room)

        elif msg_type == "WEREWOLF_NIGHT_ACTION":
            action = payload.get("action", "")
            target = payload.get("target", "")
            return self.night_action(room, client_id, action, target)

        elif msg_type == "WEREWOLF_START_DISCUSSION":
            return self.start_discussion(room)

        elif msg_type == "WEREWOLF_VOTE":
            target_id = payload.get("target_player_id", "")
            return self.vote(room, client_id, target_id)

        elif msg_type == "WEREWOLF_FINISH_VOTING":
            return self.finish_voting(room)

        return False

    def setup(self, room: Room):
        """ワンナイト人狼の初期化・配役"""
        player_ids = list(room.players.keys())
        num_players = len(player_ids)

        if num_players < 3:
            return  # 最低3人必要

        # プレイヤー数 + 2 枚のカードを準備
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

    def start_night(self, room: Room) -> bool:
        """夜フェーズを開始（まず全員目を閉じる）"""
        if not room.werewolf_state:
            return False

        state = room.werewolf_state
        state.night_phase = WerewolfNightPhase.CLOSING_EYES
        room.phase = Phase.ANSWERING  # ANSWERINGを夜フェーズとして使用
        return True

    def advance_night(self, room: Room) -> bool:
        """夜フェーズを次に進める（自動進行）"""
        if not room.werewolf_state:
            return False

        state = room.werewolf_state

        if state.night_phase == WerewolfNightPhase.CLOSING_EYES:
            state.night_phase = WerewolfNightPhase.WEREWOLF
            state.night_actions_done = {}
        elif state.night_phase == WerewolfNightPhase.WEREWOLF:
            state.night_phase = WerewolfNightPhase.SEER
            state.night_actions_done = {}
        elif state.night_phase == WerewolfNightPhase.SEER:
            state.night_phase = WerewolfNightPhase.THIEF
            state.night_actions_done = {}
        elif state.night_phase == WerewolfNightPhase.THIEF:
            state.night_phase = WerewolfNightPhase.DONE

        return True

    def night_action(self, room: Room, client_id: str, action: str, target: str) -> bool:
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
                try:
                    idx = int(target.split("_")[1])
                    if 0 <= idx < len(state.graveyard):
                        role = state.graveyard[idx]
                        role_name = self._get_seer_result_name(role)
                        state.night_info[client_id] = f"墓地のカード{idx + 1}: {role_name}"
                        state.seer_target = "graveyard"
                        state.seer_graveyard_index = idx
                except (ValueError, IndexError):
                    return False
            else:
                if target not in state.current_roles:
                    return False
                target_role = state.current_roles[target]
                target_name = room.players[target].name if target in room.players else "???"
                role_name = self._get_seer_result_name(target_role)
                state.night_info[client_id] = f"{target_name}の役職: {role_name}"
                state.seer_target = target

            state.night_actions_done[client_id] = True
            return True

        # 怪盗の行動
        elif action == "thief_swap":
            if player_role != WerewolfRole.THIEF:
                return False

            if target == "skip":
                state.night_info[client_id] = "交換しませんでした。あなたは怪盗のままです。"
                state.thief_swapped = False
            else:
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
        if role == WerewolfRole.MADMAN:
            return "村人"
        return self._get_role_name(role)

    def start_discussion(self, room: Room) -> bool:
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

    def vote(self, room: Room, client_id: str, target_id: str) -> bool:
        """投票する"""
        if not room.werewolf_state:
            return False

        state = room.werewolf_state

        # 平和村投票は特別扱い
        if target_id == "PEACE_VILLAGE":
            state.votes[client_id] = target_id
            if client_id in room.players:
                room.players[client_id].has_answered = True
            return True

        if not target_id or target_id not in room.players:
            return False

        # 自分に投票はできない
        if target_id == client_id:
            return False

        state.votes[client_id] = target_id

        if client_id in room.players:
            room.players[client_id].has_answered = True

        return True

    def finish_voting(self, room: Room) -> bool:
        """投票を締め切って結果を計算"""
        if not room.werewolf_state:
            return False

        state = room.werewolf_state
        state.calculate_vote_results(room.players)

        room.phase = Phase.RESULT
        return True
