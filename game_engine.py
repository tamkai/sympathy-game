
import random
import time
import csv
import uuid
from typing import Dict, List, Optional
from models import Room, Player, Phase, GameMode, WordWolfState, Answer

class GameEngine:
    def __init__(self):
        self.questions = []
        self.word_wolf_topics = []
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
            available_questions = [q for q in self.questions if q not in room.used_questions]
            
            if not available_questions:
                 room.used_questions = set()
                 available_questions = self.questions
            
            new_q = random.choice(available_questions)
            room.current_question = new_q
            room.used_questions.add(new_q)
            
            room.phase = Phase.ANSWERING
            
        elif room.mode == GameMode.WORD_WOLF:
            room.phase = Phase.DESCRIPTION
            self.setup_word_wolf(room)
