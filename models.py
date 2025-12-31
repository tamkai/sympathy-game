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
    ONE_NIGHT_WEREWOLF = "ONE_NIGHT_WEREWOLF"


class WerewolfRole(str, Enum):
    """ワンナイト人狼の役職"""
    VILLAGER = "villager"      # 村人
    WEREWOLF = "werewolf"      # 人狼
    SEER = "seer"              # 占い師
    THIEF = "thief"            # 怪盗
    MADMAN = "madman"          # 狂人（人狼陣営だが占い結果は人間）


class WerewolfNightPhase(str, Enum):
    """夜フェーズの進行状態"""
    WAITING = "waiting"        # 開始待ち
    CLOSING_EYES = "closing_eyes"  # 全員目を閉じる
    WEREWOLF = "werewolf"      # 人狼の確認
    SEER = "seer"              # 占い師の行動
    THIEF = "thief"            # 怪盗の行動
    DONE = "done"              # 夜フェーズ完了


class WerewolfState(BaseModel):
    """ワンナイト人狼のゲーム状態"""
    # 配役（初期配布時）
    original_roles: Dict[str, WerewolfRole] = {}  # player_id -> 役職
    graveyard: List[WerewolfRole] = []            # 墓地の2枚

    # 現在の役職（怪盗の交換後）
    current_roles: Dict[str, WerewolfRole] = {}   # player_id -> 役職

    # 夜アクション結果（各プレイヤーが見た情報）
    night_info: Dict[str, str] = {}  # player_id -> 見た情報（表示用テキスト）

    # 夜フェーズ進行
    night_phase: WerewolfNightPhase = WerewolfNightPhase.WAITING
    night_actions_done: Dict[str, bool] = {}  # player_id -> 行動完了したか

    # 占い師のアクション記録
    seer_target: Optional[str] = None  # 占った対象（player_idまたは"graveyard"）
    seer_graveyard_index: Optional[int] = None  # 墓地を見た場合のインデックス

    # 怪盗のアクション記録
    thief_target: Optional[str] = None  # 交換対象のplayer_id（交換しない場合はNone）
    thief_swapped: bool = False  # 交換したか

    # 投票
    votes: Dict[str, str] = {}  # voter_id -> target_id

    # 議論時間
    discussion_end_time: float = 0.0

    # 結果
    executed_player_ids: List[str] = []  # 処刑されたプレイヤーID（複数可能）
    executed_player_id: Optional[str] = None  # 後方互換用
    village_won: bool = False
    is_peace_village: bool = False  # 平和村（人狼不在）
    peace_vote_succeeded: bool = False  # 平和村投票が成功したか
    no_execution: bool = False  # 処刑なし（全員バラバラ）
    winning_reason: str = ""

    def get_werewolf_ids(self) -> List[str]:
        """現在の人狼プレイヤーIDを取得"""
        return [pid for pid, role in self.current_roles.items() if role == WerewolfRole.WEREWOLF]

    def get_madman_ids(self) -> List[str]:
        """現在の狂人プレイヤーIDを取得"""
        return [pid for pid, role in self.current_roles.items() if role == WerewolfRole.MADMAN]

    def get_werewolf_team_ids(self) -> List[str]:
        """人狼陣営（人狼+狂人）のプレイヤーIDを取得"""
        return [pid for pid, role in self.current_roles.items()
                if role in (WerewolfRole.WEREWOLF, WerewolfRole.MADMAN)]

    def calculate_vote_results(self, players_dict: Dict[str, Any]):
        """投票結果を計算"""
        # 投票集計（平和村投票を含む）
        vote_counts: Dict[str, int] = {}
        peace_votes = 0
        for target in self.votes.values():
            if target == "PEACE_VILLAGE":
                peace_votes += 1
            else:
                vote_counts[target] = vote_counts.get(target, 0) + 1

        # 現在の人狼を取得
        werewolf_ids = self.get_werewolf_ids()
        madman_ids = self.get_madman_ids()

        # 実際に人狼がいない場合
        if not werewolf_ids:
            self.is_peace_village = True

        # 投票がない場合
        total_votes = len(self.votes)
        if total_votes == 0:
            if not werewolf_ids:
                self.village_won = True
                self.winning_reason = "平和村！人狼はいませんでした。全員の勝利！"
            else:
                self.village_won = False
                werewolf_names = [players_dict[wid].name for wid in werewolf_ids if wid in players_dict]
                self.winning_reason = f"人狼陣営の勝利！投票がありませんでした。人狼は{', '.join(werewolf_names)}でした！"
            return

        # 全員バラバラの場合（全員が1票ずつ、かつ平和村票も含めてバラバラ）
        all_counts = list(vote_counts.values()) + ([peace_votes] if peace_votes > 0 else [])
        if all_counts and max(all_counts) == 1:
            self.no_execution = True
            if not werewolf_ids:
                # 平和村で全員バラバラ → 全員勝利
                self.village_won = True
                self.winning_reason = "処刑なし！平和村でした。全員の勝利！"
            else:
                # 人狼がいるのに処刑なし → 人狼の勝利
                self.village_won = False
                werewolf_names = [players_dict[wid].name for wid in werewolf_ids if wid in players_dict]
                self.winning_reason = f"人狼陣営の勝利！処刑される人がいませんでした。人狼は{', '.join(werewolf_names)}でした！"
            return

        # 最多票を取得（平和村票も含める）
        max_player_votes = max(vote_counts.values()) if vote_counts else 0
        max_votes = max(max_player_votes, peace_votes)

        # 平和村が最多票の場合
        if peace_votes == max_votes and (not vote_counts or peace_votes >= max_player_votes):
            self.peace_vote_succeeded = True
            if not werewolf_ids:
                # 平和村投票が当たり！
                self.village_won = True
                self.winning_reason = "平和村を願う投票が正解！人狼はいませんでした。全員の勝利！"
            else:
                # 平和村投票だが実際には人狼がいた
                self.village_won = False
                werewolf_names = [players_dict[wid].name for wid in werewolf_ids if wid in players_dict]
                self.winning_reason = f"人狼陣営の勝利！平和村を願いましたが、人狼は{', '.join(werewolf_names)}でした！"
            return

        # 最多票のプレイヤーを取得
        most_voted_ids = [pid for pid, count in vote_counts.items() if count == max_votes]

        # 同数の場合は全員処刑
        self.executed_player_ids = most_voted_ids
        self.executed_player_id = most_voted_ids[0]  # 後方互換用

        # 処刑者の中に人狼がいるかチェック
        executed_werewolves = [pid for pid in most_voted_ids if pid in werewolf_ids]

        if executed_werewolves:
            # 人狼が処刑された → 村人の勝利
            self.village_won = True
            executed_names = [players_dict[pid].name for pid in most_voted_ids if pid in players_dict]
            if len(most_voted_ids) > 1:
                self.winning_reason = f"村人陣営の勝利！{', '.join(executed_names)}が処刑され、人狼が含まれていました！"
            else:
                self.winning_reason = f"村人陣営の勝利！{executed_names[0]}は人狼でした！"
        else:
            # 人狼が処刑されなかった
            self.village_won = False
            executed_names = [players_dict[pid].name for pid in most_voted_ids if pid in players_dict]
            werewolf_names = [players_dict[wid].name for wid in werewolf_ids if wid in players_dict]

            if self.is_peace_village:
                # 平和村なのに処刑してしまった
                if len(most_voted_ids) > 1:
                    self.winning_reason = f"残念！{', '.join(executed_names)}が処刑されましたが、実は平和村でした..."
                else:
                    self.winning_reason = f"残念！{executed_names[0]}を処刑しましたが、実は平和村でした..."
            else:
                # 人狼がいるのに見逃した
                if len(most_voted_ids) > 1:
                    base_msg = f"人狼陣営の勝利！{', '.join(executed_names)}が処刑されましたが、人狼ではありませんでした。"
                else:
                    base_msg = f"人狼陣営の勝利！{executed_names[0]}は人狼ではありませんでした。"

                if madman_ids:
                    madman_names = [players_dict[mid].name for mid in madman_ids if mid in players_dict]
                    self.winning_reason = f"{base_msg}人狼は{', '.join(werewolf_names)}、狂人は{', '.join(madman_names)}でした！"
                else:
                    self.winning_reason = f"{base_msg}人狼は{', '.join(werewolf_names)}でした！"

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

    # One Night Werewolf State
    werewolf_state: Optional[WerewolfState] = None

    # Common State
    players: Dict[str, Player] = Field(default_factory=dict)
    winner_id: Optional[str] = None
    
    # Config
    config_speed_star: bool = True
    config_shuffle: bool = True
    config_discussion_time: int = 180 # Seconds (Default 3 mins)
    config_ito_coop: bool = True  # itoの協力モード
    config_ito_close_call: bool = False  # itoのギリギリ成功演出
    config_werewolf_madman: bool = True  # ワンナイト人狼の狂人（4人以上で有効）
    
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
