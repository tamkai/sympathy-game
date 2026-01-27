import random
import time
from typing import TYPE_CHECKING

from models import Room, Phase, WordWolfState

if TYPE_CHECKING:
    from .base import GameEngine


class WordWolfGame:
    def __init__(self, engine: 'GameEngine'):
        self.engine = engine

    def process_message(self, room: Room, client_id: str, msg_type: str, payload: dict) -> bool:
        """WordWolfゲームのメッセージ処理"""
        if msg_type == "START_DISCUSSION":
            room.phase = Phase.ANSWERING
            return True

        elif msg_type == "SKIP_TO_JUDGING":
            room.phase = Phase.JUDGING
            return True

        elif msg_type == "VOTE_WOLF":
            target_player_id = payload.get("target_player_id")
            return self.vote_wolf(room, client_id, target_player_id)

        elif msg_type == "FINISH_JUDGING":
            self.finish_judging(room)
            return True

        elif msg_type == "NEXT_ROUND":
            self.next_round(room)
            return True

        return False

    def setup(self, room: Room):
        """WordWolfの初期化・配役"""
        # Topics
        majority_topic = "Topic A"
        minority_topic = "Topic B"
        try:
            if self.engine.word_wolf_topics:
                topic_pair = random.choice(self.engine.word_wolf_topics)
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

    def vote_wolf(self, room: Room, client_id: str, target_player_id: str) -> bool:
        if room.word_wolf_state:
            if target_player_id and target_player_id in room.players:
                room.word_wolf_state.votes[client_id] = target_player_id

                if client_id in room.players:
                    room.players[client_id].has_answered = True

                if len(room.word_wolf_state.votes) == len(room.players):
                    room.word_wolf_state.calculate_vote_results(room.players)
                    room.phase = Phase.RESULT
                return True
        return False

    def finish_judging(self, room: Room):
        if room.word_wolf_state:
            room.word_wolf_state.calculate_vote_results(room.players)
        room.phase = Phase.RESULT

    def next_round(self, room: Room):
        room.reset_round()
        room.phase = Phase.DESCRIPTION
        self.setup(room)
