import random
import time
import uuid
from typing import TYPE_CHECKING

from models import Room, Phase, GameMode, Answer

if TYPE_CHECKING:
    from .base import GameEngine


class SympathyGame:
    def __init__(self, engine: 'GameEngine'):
        self.engine = engine

    def process_message(self, room: Room, client_id: str, msg_type: str, payload: dict) -> bool:
        """Sympathyゲームのメッセージ処理"""
        if msg_type == "START_ROUND":
            room.phase = Phase.ANSWERING
            return True

        elif msg_type == "SUBMIT_ANSWER":
            text = payload.get("text", "")
            use_shuffle = payload.get("use_shuffle", False)
            return self.submit_answer(room, client_id, text, use_shuffle)

        elif msg_type == "SKIP_TO_JUDGING":
            self.skip_to_judging(room)
            return True

        elif msg_type == "UPDATE_GROUPING":
            updates = payload.get("answers", {})
            for ans_id, data in updates.items():
                if ans_id in room.answers:
                    room.answers[ans_id].group_id = data.get("group_id", ans_id)
            return True

        elif msg_type == "FINISH_JUDGING":
            self.finish_judging(room)
            return True

        elif msg_type == "NEXT_ROUND":
            self.next_round(room)
            return True

        return False

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

    def finish_judging(self, room: Room):
        try:
            room.calculate_results()
        except Exception as e:
            print(f"Error calculating results: {e}")
        room.phase = Phase.RESULT

    def next_round(self, room: Room):
        room.reset_round()

        available_questions = [q for q in self.engine.questions if q not in room.used_questions]

        if not available_questions:
            room.used_questions = set()
            available_questions = self.engine.questions

        new_q = random.choice(available_questions)
        room.current_question = new_q
        room.used_questions.add(new_q)

        room.phase = Phase.ANSWERING
