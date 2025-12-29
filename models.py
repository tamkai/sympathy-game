from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import uuid

class Phase(str, Enum):
    LOBBY = "LOBBY"
    INSTRUCTION = "INSTRUCTION"
    ANSWERING = "ANSWERING"
    JUDGING = "JUDGING"
    RESULT = "RESULT"
    DESCRIPTION = "DESCRIPTION"

class Player(BaseModel):
    player_id: str
    name: str
    score: int = 0
    has_answered: bool = False
    is_connected: bool = True
    shuffle_remaining: int = 1 # One-time use

class Answer(BaseModel):
    answer_id: str
    player_id: str
    player_name: str
    raw_text: str
    normalized_text: str
    group_id: str
    timestamp: float = 0.0
    used_shuffle: bool = False

class GameMode(str, Enum):
    SYMPATHY = "SYMPATHY"
    WORD_WOLF = "WORD_WOLF"
    SEKAI_NO_MIKATA = "SEKAI_NO_MIKATA"
    ITO = "ITO"

class WordWolfState(BaseModel):
    wolf_ids: List[str] = []
    topics: Dict[str, str] = {} # player_id -> topic
    votes: Dict[str, str] = {} # voter_id -> target_id
    discussion_end_time: float = 0.0
    
    # Result Data
    wolf_won: bool = False
    winning_reason: str = ""
    wolf_name: str = ""
    majority_topic: str = ""
    minority_topic: str = ""

    def calculate_vote_results(self, players_dict: Dict[str, Any]):
        # Tally votes
        vote_counts: Dict[str, int] = {}
        for target in self.votes.values():
            vote_counts[target] = vote_counts.get(target, 0) + 1
            
        if not vote_counts:
            # No votes?
            self.wolf_won = True
            self.winning_reason = "No votes cast."
            return

        # Find most voted
        max_votes = max(vote_counts.values())
        most_voted_ids = [pid for pid, count in vote_counts.items() if count == max_votes]
        
        # Win Condition:
        # If Wolf is among most voted -> Citizens Win
        # Else -> Wolf Wins
        
        wolf_caught = False
        for pid in most_voted_ids:
            if pid in self.wolf_ids:
                wolf_caught = True
                break
        
        # Set basics
        wolf_id = self.wolf_ids[0] if self.wolf_ids else "Unknown"
        self.wolf_name = players_dict[wolf_id].name if wolf_id in players_dict else "Unknown"
        
        # Determine Topic names (just grab from first villager/wolf)
        self.minority_topic = self.topics.get(wolf_id, "???")
        # Find a non-wolf topic
        for pid, topic in self.topics.items():
            if pid not in self.wolf_ids:
                self.majority_topic = topic
                break
        
        if wolf_caught:
            self.wolf_won = False
            self.winning_reason = "市民がウルフを見事に見破りました！"
        else:
            self.wolf_won = True
            self.winning_reason = "ウルフは正体を隠し通しました！"

class SekaiAnswer(BaseModel):
    """セカイノミカタの回答"""
    answer_id: str
    player_id: str
    player_name: str
    text: str
    is_dummy: bool = False  # ダミー（山札）かどうか

class SekaiNoMikataState(BaseModel):
    """セカイノミカタ（私の世界の見方風）のゲーム状態"""
    current_reader_id: Optional[str] = None  # 親（読み手）のID
    reader_order: List[str] = []  # 親の順番
    current_reader_index: int = 0

    current_question: str = ""  # 現在のお題（空欄付き）
    word_choices: Dict[str, List[str]] = {}  # player_id -> 選択肢の単語リスト

    submitted_answers: Dict[str, SekaiAnswer] = {}  # answer_id -> SekaiAnswer
    dummy_answers: List[SekaiAnswer] = []  # ダミー回答（山札から）

    all_answers_for_display: List[SekaiAnswer] = []  # シャッフル後の全回答（表示用）

    selected_answer_id: Optional[str] = None  # 親が選んだ回答のID
    round_number: int = 1
    winning_score: int = 5  # 勝利に必要な得点

    used_questions: List[str] = []  # 使用済みお題
    used_words: List[str] = []  # 使用済み単語（偏り防止）

class ItoPlayedCard(BaseModel):
    """itoで出されたカード"""
    player_id: str
    player_name: str
    number: int
    order: int  # 何番目に出されたか
    is_failed: bool = False  # このカードで失敗したか

class ItoState(BaseModel):
    """itoゲームの状態"""
    # ゲーム設定
    is_coop_mode: bool = True  # True: 協力モード（クモノイト）, False: 通常モード
    close_call_enabled: bool = False  # ギリギリ成功演出

    # お題
    current_topic: str = ""
    used_topics: List[str] = []

    # 各プレイヤーの数字 (player_id -> number)
    player_numbers: Dict[str, int] = {}

    # 出されたカード履歴
    played_cards: List[ItoPlayedCard] = []
    last_played_number: int = 0  # 最後に出されたカードの数字

    # ゲーム進行
    stage: int = 1  # 現在のステージ（1-3）
    life: int = 3  # 残りライフ
    is_failed: bool = False  # 現在のステージで失敗したか

    # 結果
    stage_cleared: bool = False  # 現在のステージをクリアしたか
    game_cleared: bool = False  # 全ステージクリアしたか
    game_over: bool = False  # ゲームオーバーか

class Room(BaseModel):
    room_id: str
    phase: Phase = Phase.LOBBY
    mode: GameMode = GameMode.SYMPATHY
    
    # Sympathy State
    current_question: Optional[str] = None
    answers: Dict[str, Answer] = Field(default_factory=dict)
    
    # Word Wolf State
    word_wolf_state: Optional[WordWolfState] = None

    # Sekai No Mikata State
    sekai_state: Optional[SekaiNoMikataState] = None

    # Ito State
    ito_state: Optional[ItoState] = None

    # Common State
    players: Dict[str, Player] = Field(default_factory=dict)
    winner_id: Optional[str] = None
    
    # Config
    config_speed_star: bool = True
    config_shuffle: bool = True
    config_discussion_time: int = 180 # Seconds (Default 3 mins)
    config_ito_coop: bool = True  # itoの協力モード
    config_ito_close_call: bool = False  # itoのギリギリ成功演出
    
    # Sympathy Specific State
    shuffle_triggered_in_round: bool = False
    speed_star_id: Optional[str] = None
    
    # Track used questions properly with default_factory
    used_questions: set = Field(default_factory=set)
    bomb_owner_id: Optional[str] = None

    def add_player(self, player_id: str, name: str) -> Player:
        if player_id in self.players:
            # Reconnection logic could go here, for now just update name if needed
            self.players[player_id].name = name
            self.players[player_id].is_connected = True
        else:
            new_player = Player(player_id=player_id, name=name)
            self.players[player_id] = new_player
        return self.players[player_id]

    def remove_player(self, player_id: str):
        if player_id in self.players:
            self.players[player_id].is_connected = False
            # Optional: remove completely if in LOBBY
            # del self.players[player_id]


    def reset_round(self):
        self.answers = {}
        self.shuffle_triggered_in_round = False
        for p in self.players.values():
            p.has_answered = False

    def reset_game(self):
        self.phase = Phase.LOBBY
        self.current_question = None
        self.bomb_owner_id = None
        self.shuffle_triggered_in_round = False
        self.players = {}     # Clear all players
        self.answers = {}     # Clear all answers
        self.used_questions = set() # Reset question history logic

    def calculate_results(self):

        # 1. Group answers
        groups: Dict[str, List[Answer]] = {}
        for ans in self.answers.values():
            if ans.group_id not in groups:
                groups[ans.group_id] = []
            groups[ans.group_id].append(ans)
        
        if not groups:
            return

        # 2. Find Majority (Largest Group)
        max_count = 0
        majority_group_ids = []
        for gid, items in groups.items():
            count = len(items)
            if count > max_count:
                max_count = count
                majority_group_ids = [gid]
            elif count == max_count:
                majority_group_ids.append(gid)
        
        # Award points to majority
        # Note: If everyone is distinct (max_count=1), maybe no one gets points? Or everyone?
        # Let's say: Majority must be size > 1 to get points, or just max_size is enough.
        # Rule: "Coordinate with others". If alone, no points.
        self.speed_star_id = None  # Reset for this round
        if max_count > 1:
            # Track the overall fastest among all majority groups
            overall_earliest_time = float('inf')
            overall_speed_star_id = None
            
            for gid in majority_group_ids:
                for ans in groups[gid]:
                    if ans.player_id in self.players:
                        self.players[ans.player_id].score += 1
                    
                    # Track Fastest
                    if self.config_speed_star and ans.timestamp > 0 and ans.timestamp < overall_earliest_time:
                        overall_earliest_time = ans.timestamp
                        overall_speed_star_id = ans.player_id
            
            # Award Speed Star Bonus (+1) to the fastest
            if overall_speed_star_id and overall_speed_star_id in self.players:
                self.players[overall_speed_star_id].score += 1
                self.speed_star_id = overall_speed_star_id

        # 3. Find Minority (Group size == 1) -> Bomb (Penalty)
        minority_players = []
        for gid, items in groups.items():
            if len(items) == 1:
                ans = items[0]
                minority_players.append(ans.player_id)
        
        if minority_players:
            # Assign Bomb to one of them.
            # If current bomb owner is in the list, they keep it?
            # Or just pick the last one / random one.
            # Simple logic: If current owner is in candidates, keep. Else pick new.
            if self.bomb_owner_id in minority_players:
                pass # Keep bomb
            else:
                import random
                self.bomb_owner_id = random.choice(minority_players)

        # 4. Check Victory Condition (8+ pts without bomb)
        self.winner_id = None
        for player in self.players.values():
            if player.score >= 8 and player.player_id != self.bomb_owner_id:
                self.winner_id = player.player_id
                break

# Global state storage (In-Memory for MVP)
rooms: Dict[str, Room] = {}

def get_or_create_room(room_id: str) -> Room:
    if room_id not in rooms:
        rooms[room_id] = Room(room_id=room_id)
    return rooms[room_id]
