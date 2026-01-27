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

    def get_view(self, viewer_id: str) -> dict:
        """
        Create a sanitized view of the room state for a specific viewer.
        Hides secret information like Werewolf roles, other players' cards, etc.
        """
        # Base full dump (deep copy via pydantic serialization to avoid mutation)
        data = self.model_dump()
        is_host = viewer_id.startswith("HOST")

        # --- Sanitize Word Wolf State ---
        if self.mode == GameMode.WORD_WOLF and self.word_wolf_state:
            ww_state = self.word_wolf_state
            
            # Hide votes during discussion
            if self.phase != Phase.RESULT:
                data['word_wolf_state']['votes'] = {}
            
            # Hide Topics and Wolf IDs
            # Logic:
            # - Host: Can see everything? Let's say yes for now to debug/monitor.
            # - Player: Can only see their own topic. CANNOT see wolf_ids.
            
            if not is_host:
                # Sanitize Topics
                client_topic = ww_state.topics.get(viewer_id)
                data['word_wolf_state']['topics'] = {viewer_id: client_topic} if client_topic else {}
                
                # Sanitize Wolf IDs (Secrets!)
                # Players only know if THEY are the wolf. They don't get the full wolf_ids list.
                # Actually, client logic uses `wolf_ids.includes(myClientId)` to determine role.
                # So we can send `wolf_ids` efficiently BUT it MUST NOT contain others.
                
                if viewer_id in ww_state.wolf_ids:
                    # I am a wolf. I know I am a wolf.
                    data['word_wolf_state']['wolf_ids'] = [viewer_id]
                else:
                    # I am a villager. I see empty wolf_ids list from server.
                    data['word_wolf_state']['wolf_ids'] = []

        # --- Sanitize Sekai No Mikata State ---
        if self.mode == GameMode.SEKAI_NO_MIKATA and self.sekai_state:
            # Hide other players' word choices
            if not is_host:
                user_choices = self.sekai_state.word_choices.get(viewer_id, [])
                data['sekai_state']['word_choices'] = {viewer_id: user_choices}

            # Hide who served which answer during Judging
            # In Phase.ANSWERING: Hide answers completely? No, we show progress.
            # In Phase.JUDGING: Show answers but hide `player_id` (so we don't know who wrote what).
            # But wait, Sekai logic: "Nominate your favorite". You shouldn't know who wrote it.
            # `all_answers_for_display` is heavily used.
            
            if self.phase == Phase.JUDGING:
                # Hide player names/ids in the display list
                sanitized_list = []
                for ans in data['sekai_state']['all_answers_for_display']:
                    # Clone dict to avoid mutating original
                    safe_ans = ans.copy()
                    safe_ans['player_id'] = "HIDDEN"
                    safe_ans['player_name'] = "???"
                    # Keep is_dummy? Maybe hide that too if we want perfect bluffing.
                    # But usually "Mountain Deck" is a known entity or not?
                    # Let's keep is_dummy strictly hidden if we want players to guess.
                    # Current rules: Just pick the best answer.
                    sanitized_list.append(safe_ans)
                data['sekai_state']['all_answers_for_display'] = sanitized_list

        # --- Sanitize Ito State ---
        if self.mode == GameMode.ITO and self.ito_state:
            # Hide other players' numbers!
            if not is_host:
                my_number = self.ito_state.player_numbers.get(viewer_id)
                data['ito_state']['player_numbers'] = {viewer_id: my_number} if my_number else {}

        # --- Sanitize One Night Werewolf State ---
        if self.mode == GameMode.ONE_NIGHT_WEREWOLF and self.werewolf_state:
            wf_state = self.werewolf_state
            
            # Hide Original Roles (The most critical part)
            # Host can see all? Maybe.
            if not is_host:
                 # Only show MY role
                my_role = wf_state.original_roles.get(viewer_id)
                data['werewolf_state']['original_roles'] = {viewer_id: my_role} if my_role else {}
                
                # Hide Graveyard completely
                data['werewolf_state']['graveyard'] = []
                
                # Hide Current Roles (Thief results etc)
                data['werewolf_state']['current_roles'] = {}

                # Hide Night Info - but show MY OWN night info
                my_night_info = wf_state.night_info.get(viewer_id)
                data['werewolf_state']['night_info'] = {viewer_id: my_night_info} if my_night_info else {}

                # Hide Individual Votes during voting phase (show only count or nothing?)
                # Usually voting is simultaneous.
                if self.phase != Phase.RESULT:
                     data['werewolf_state']['votes'] = {}

                # Special Case: Werewolves can see other Werewolves
                # But we handled that in client logic? `werewolfPartnerInfo` needs data.
                if my_role == WerewolfRole.WEREWOLF:
                    # Provide partner info specifically
                    # We can inject a synthetic "partners" field or just expose those IDs in `original_roles`
                    # Exposing in `original_roles` is cleaner so client logic works.
                    partners = {pid: role for pid, role in wf_state.original_roles.items() if role == WerewolfRole.WEREWOLF}
                    data['werewolf_state']['original_roles'].update(partners)

        # --- Sanitize Sympathy Answers (Bluffing Phase) ---
        if self.mode == GameMode.SYMPATHY:
            # During ANSWERING: Hide answers from others (but we need to know WHO answered)
            # `has_answered` in Player model covers the status.
            # `answers` dict contains the text.
            
            if self.phase == Phase.ANSWERING:
                # Clear all answer texts
                data['answers'] = {}

            # During JUDGING: We need to see texts to group them.
            # But DO WE need to see WHO wrote what?
            # Sympathy rules: "Guess who wrote what" or just "Group same meanings"?
            # Actually Sympathy is "Synchronize with others".
            # If I see "Apple" and I know "Tamkai" wrote it, I might join.
            # The game UI shows cards.
            # Let's keep Sympathy open for now as it's cooperative-ish.
            pass

        return data

    def handle_seer_peek(self, client_id: str, target: str) -> str:
        """
        Handle a Seer's request to peek at a card.
        Returns the role name string.
        """
        print(f"[DEBUG] handle_seer_peek called: client_id={client_id}, target={target}")
        if self.mode != GameMode.ONE_NIGHT_WEREWOLF or not self.werewolf_state:
            print(f"[DEBUG] handle_seer_peek: wrong mode or no werewolf_state")
            return ""

        roles = self.werewolf_state.original_roles
        print(f"[DEBUG] handle_seer_peek: original_roles={roles}")

        # Verify requester is Seer
        if roles.get(client_id) != WerewolfRole.SEER:
            print(f"[DEBUG] handle_seer_peek: client is not seer, their role={roles.get(client_id)}")
            return ""

        # Target: "graveyard_0" or "player_id"
        if target.startswith("graveyard_"):
            try:
                idx = int(target.split("_")[1])
                card = self.werewolf_state.graveyard[idx]
                return card.value # "villager", "werewolf" etc
            except:
                return ""
        else:
            # Target is a player
            role = roles.get(target)
            if role:
                # Madness check: Madman looks like Villager to Seer?
                # Usually Seer sees EXACT role in One Night Werewolf?
                # Rules vary. Let's assume standard One Night: You see the role card.
                # If using "Madman sees as Villager" rule:
                # if role == WerewolfRole.MADMAN: return WerewolfRole.VILLAGER.value
                return role.value
        return ""

# Global state storage (In-Memory for MVP)
rooms: Dict[str, Room] = {}

def get_or_create_room(room_id: str) -> Room:
    if room_id not in rooms:
        rooms[room_id] = Room(room_id=room_id)
    return rooms[room_id]
