function playerApp() {
    return {
        ws: null,
        roomId: '',
        clientId: localStorage.getItem('sympathy_client_id') || 'P-' + Math.random().toString(36).substr(2, 9),

        // Input State
        nameInput: localStorage.getItem('sympathy_player_name') || '',
        answerInput: '',

        // Game State
        hasJoined: false,
        playerName: '',
        phase: 'LOBBY',
        mode: 'SYMPATHY', // New: Game Mode

        vibrate(pattern) {
            if (navigator.vibrate) {
                navigator.vibrate(pattern);
            }
        },

        // Sympathy State
        currentQuestion: '',
        hasAnswered: false,
        myScore: 0,
        myPlayerId: '', // Synced from server state if possible, or matches clientId
        players: {},
        bombOwnerId: null,
        config: { speedStar: true, shuffle: true },
        shuffleRemaining: 0,
        useShuffle: false,

        // Word Wolf State
        myRole: null, // 'VILLAGER' or 'WOLF'
        myTopic: null,
        voteTarget: '',
        topicRevealed: false, // For tap-to-reveal on touch devices

        // Sekai No Mikata State
        sekaiState: null,
        myWordChoices: [],  // 自分用の単語選択肢
        selectedWord: '',   // 選んだ単語
        customAnswer: '',   // 自由入力用
        isReader: false,    // 自分が親かどうか

        // Ito State
        itoState: null,
        numberRevealed: false,  // 自分の数字を表示するかどうか
        showPlayCardConfirm: false,  // カード出し確認モーダル
        winnerId: null,

        // One Night Werewolf State
        werewolfState: null,
        roleRevealed: false,     // 役職表示トグル
        nightInfoRevealed: false, // 夜の情報表示トグル
        seerTarget: '',          // 占い師のターゲット
        seerLocalResult: '',     // 占い師のローカル結果（即時表示用）
        thiefTarget: '',         // 怪盗のターゲット
        werewolfVoteTarget: '',  // 人狼投票ターゲット

        init() {
            // Robust roomId extraction
            const parts = document.location.pathname.split('/');
            this.roomId = parts[parts.length - 1] || parts[parts.length - 2];
            console.log("Initialized PlayerApp. RoomID:", this.roomId, "ClientID:", this.clientId);

            // Persist ID
            if (!localStorage.getItem('sympathy_client_id')) {
                localStorage.setItem('sympathy_client_id', this.clientId);
            }
            this.myPlayerId = this.clientId;
            this.connectWebSocket();
        },

        connectWebSocket() {
            const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
            const url = `${proto}://${window.location.host}/ws/${this.roomId}/${this.clientId}`;
            console.log("Connecting to WS:", url);

            this.ws = new WebSocket(url);

            this.ws.onopen = () => { console.log("WS Connected"); };

            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    if (message.type === 'STATE_UPDATE') {
                        this.updateState(message.data);
                    } else if (message.type === 'WEREWOLF_PEEK_RESULT') {
                        this.handlePeekResult(message.data);
                    }
                } catch (e) {
                    console.error("WS Message Error:", e);
                }
            };

            this.ws.onclose = () => {
                console.log("WS Disconnected");
                setTimeout(() => this.connectWebSocket(), 3000);
            };
        },

        handlePeekResult(data) {
            const result = data.result;
            const target = data.target;

            const roleNames = {
                'villager': '村人',
                'werewolf': '人狼',
                'seer': '占い師',
                'thief': '怪盗',
                'madman': '村人'
            };

            const roleName = roleNames[result] || result || "不明";

            if (target.startsWith("graveyard_")) {
                const index = parseInt(target.split('_')[1]);
                this.seerLocalResult = `墓地${index + 1}枚目: ${roleName}`;
            } else {
                const player = this.players[target];
                const playerName = player ? player.name : "???";
                this.seerLocalResult = `${playerName}: ${roleName}`;
            }
        },

        updateState(data) {
            // console.log("State Update:", data);
            const oldPhase = this.phase;
            const oldBombOwnerId = this.bombOwnerId;
            const oldRole = this.myRole;

            this.phase = data.phase;
            this.mode = data.mode; // Sync Mode
            this.currentQuestion = data.current_question || '';
            this.players = data.players || {};
            this.bombOwnerId = data.bomb_owner_id;

            // HAPTIC FEEDBACK HOOKS
            // 1. Phase Change (Start Round)
            if (this.phase !== oldPhase) {
                if (this.phase === 'ANSWERING' || this.phase === 'DESCRIPTION') {
                    this.vibrate(500); // Game Start
                } else if (this.phase === 'RESULT') {
                    this.vibrate([100, 50, 100]); // Result
                }
            }

            // 2. Bomb Received
            if (this.bombOwnerId === this.clientId && this.bombOwnerId !== oldBombOwnerId) {
                this.vibrate([200, 100, 200, 100, 500]); // Heavy Warning
            }
            this.config = {
                speedStar: data.config_speed_star,
                shuffle: data.config_shuffle
            };

            // Check my status in the room
            const me = this.players[this.clientId];
            if (me) {
                this.hasJoined = true;
                this.playerName = me.name;
                this.myScore = me.score;
                this.hasAnswered = me.has_answered;
                this.shuffleRemaining = me.shuffle_remaining;

                // Sync inputs if needed
                if (this.phase === 'RESULT' && this.mode === 'SYMPATHY') { this.answerInput = ''; }

                // Word Wolf State Sync
                if (this.mode === 'WORD_WOLF' && data.word_wolf_state) {
                    const wwState = data.word_wolf_state;
                    const isWolf = wwState.wolf_ids.includes(this.clientId);
                    this.myRole = isWolf ? 'WOLF' : 'VILLAGER';

                    // 3. Wolf Notification
                    if (this.myRole === 'WOLF' && this.myRole !== oldRole) {
                        this.vibrate([50, 50, 50, 50, 500]); // Secret signal
                    }

                    // Topic
                    if (wwState.topics && wwState.topics[this.clientId]) { this.myTopic = wwState.topics[this.clientId]; }

                    // Setup Vote Target Reset if new game
                    if (this.phase === 'LOBBY') { this.voteTarget = ''; }
                }

                // Sekai No Mikata State Sync
                if (this.mode === 'SEKAI_NO_MIKATA' && data.sekai_state) {
                    this.sekaiState = data.sekai_state;
                    this.isReader = this.sekaiState.current_reader_id === this.clientId;

                    // 自分用の単語選択肢を取得
                    if (this.sekaiState.word_choices && this.sekaiState.word_choices[this.clientId]) {
                        this.myWordChoices = this.sekaiState.word_choices[this.clientId];
                    }

                    // 新しいラウンドになったら入力をリセット
                    if (this.phase === 'ANSWERING' && !this.hasAnswered) {
                        this.selectedWord = '';
                        this.customAnswer = '';
                    }
                }

                // Ito State Sync
                if (this.mode === 'ITO' && data.ito_state) {
                    this.itoState = data.ito_state;

                    // 新しいステージになったらリセット
                    if (this.phase === 'INSTRUCTION' || (this.phase === 'ANSWERING' && !this.hasAnswered)) {
                        this.showPlayCardConfirm = false;
                    }
                }

                // One Night Werewolf State Sync
                const oldWerewolfState = this.werewolfState;
                if (this.mode === 'ONE_NIGHT_WEREWOLF' && data.werewolf_state) {
                    this.werewolfState = data.werewolf_state;

                    // 新しいゲームになったらリセット
                    if (this.phase === 'INSTRUCTION') {
                        this.roleRevealed = false;
                        this.seerTarget = '';
                        this.seerLocalResult = '';
                        this.thiefTarget = '';
                        this.werewolfVoteTarget = '';
                        this.nightInfoRevealed = false;
                    }

                    // 自分の番になったら振動
                    if (oldWerewolfState && this.werewolfState) {
                        const oldNightPhase = oldWerewolfState.night_phase;
                        const newNightPhase = this.werewolfState.night_phase;
                        if (oldNightPhase !== newNightPhase) {
                            const myRole = this.myWerewolfRole;
                            if (
                                (newNightPhase === 'werewolf' && myRole === 'werewolf') ||
                                (newNightPhase === 'seer' && myRole === 'seer') ||
                                (newNightPhase === 'thief' && myRole === 'thief')
                            ) {
                                this.vibrate([200, 100, 200]); // Your turn!
                            }
                        }
                    }
                }

                // WinnerId
                this.winnerId = data.winner_id;

            } else {
                // Not in room list yet
                if (this.hasJoined) {
                    alert("ゲームが終了されました。ロビーに戻ります。");
                    this.hasJoined = false;
                    this.answerInput = '';
                    this.myScore = 0;
                    this.hasAnswered = false;
                    this.voteTarget = '';
                }
                this.hasJoined = false;
            }
        },

        sendMessage(type, data = {}) {
            console.log("[DEBUG] sendMessage called:", type, data, "readyState:", this.ws?.readyState);
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type, data }));
                console.log("[DEBUG] sendMessage: sent successfully");
            } else {
                console.warn("[DEBUG] WS not open. Cannot send:", type, "readyState:", this.ws?.readyState);
            }
        },

        joinGame() {
            console.log("[DEBUG] joinGame called. Name:", this.nameInput, "WS readyState:", this.ws?.readyState);
            if (!this.nameInput) {
                console.log("[DEBUG] joinGame: nameInput is empty, returning");
                return;
            }
            localStorage.setItem('sympathy_player_name', this.nameInput);
            this.sendMessage('JOIN', { name: this.nameInput });
            this.playerName = this.nameInput;
            console.log("[DEBUG] joinGame: JOIN message sent");
        },

        submitAnswer() {
            if (!this.answerInput) return;
            this.sendMessage('SUBMIT_ANSWER', {
                text: this.answerInput,
                use_shuffle: this.useShuffle
            });
            this.hasAnswered = true;
            this.useShuffle = false;
        },

        submitVote() {
            if (!this.voteTarget) return;
            this.sendMessage('VOTE_WOLF', {
                target_player_id: this.voteTarget
            });
            // optimistic state? Maybe wait for server state update to disable button
            this.hasAnswered = true; // Recycle this flag for "Has Voted" in simple UI
        },

        // Sekai No Mikata: 回答を送信
        submitSekaiAnswer() {
            const text = this.selectedWord || this.customAnswer;
            if (!text) return;
            this.sendMessage('SEKAI_SUBMIT_ANSWER', { text: text });
            this.hasAnswered = true;
        },

        // 単語を選択
        selectWord(word) {
            this.selectedWord = word;
            this.customAnswer = '';  // 選択したらカスタム入力はクリア
        },

        get myRank() {
            const sorted = Object.values(this.players).sort((a, b) => b.score - a.score);
            const index = sorted.findIndex(p => p.player_id === this.clientId);
            return index + 1;
        },

        // Sekai: 親の名前を取得
        get sekaiReaderName() {
            if (!this.sekaiState || !this.sekaiState.current_reader_id) return '';
            const player = this.players[this.sekaiState.current_reader_id];
            return player ? player.name : '';
        },

        // Ito: カードを出す
        playItoCard() {
            this.showPlayCardConfirm = false;
            this.sendMessage('ITO_PLAY_CARD', {});
            this.hasAnswered = true;
        },

        // Ito: 自分の数字を取得
        get myNumber() {
            if (!this.itoState || !this.itoState.player_numbers) return '?';
            return this.itoState.player_numbers[this.clientId] || '?';
        },

        // ===== One Night Werewolf =====

        // 自分の役職を取得（元の役職）
        get myWerewolfRole() {
            if (!this.werewolfState || !this.werewolfState.original_roles) {
                console.log('[DEBUG] myWerewolfRole: werewolfState or original_roles is null');
                return null;
            }
            const role = this.werewolfState.original_roles[this.clientId];
            console.log('[DEBUG] myWerewolfRole:', role, 'clientId:', this.clientId, 'original_roles:', this.werewolfState.original_roles);
            return role || null;
        },

        // 自分の番かどうか
        get isMyNightTurn() {
            if (!this.werewolfState) return false;
            const phase = this.werewolfState.night_phase;
            const role = this.myWerewolfRole;
            const result = (
                (phase === 'werewolf' && role === 'werewolf') ||
                (phase === 'seer' && role === 'seer') ||
                (phase === 'thief' && role === 'thief')
            );
            console.log('[DEBUG] isMyNightTurn:', result, 'night_phase:', phase, 'role:', role);
            return result;
        },

        // 人狼: 仲間の人狼情報
        get werewolfPartnerInfo() {
            if (!this.werewolfState || this.myWerewolfRole !== 'werewolf') return '';
            const wolfIds = Object.entries(this.werewolfState.original_roles)
                .filter(([pid, role]) => role === 'werewolf' && pid !== this.clientId)
                .map(([pid]) => pid);
            if (wolfIds.length === 0) return 'あなたは一人狼です（仲間なし）';
            const partnerNames = wolfIds.map(pid => this.players[pid]?.name || '???');
            return '仲間の人狼: ' + partnerNames.join(', ');
        },

        // 人狼: 確認完了
        werewolfConfirm() {
            this.sendMessage('WEREWOLF_NIGHT_ACTION', {
                action: 'werewolf_confirm',
                target: ''
            });
        },

        // 占い師: 対象をタップして即時結果を表示（サーバーに問い合わせ）
        seerPeek(target) {
            console.log('[DEBUG] seerPeek called with target:', target);
            this.seerTarget = target;
            this.seerLocalResult = "確認中...";

            this.sendMessage('WEREWOLF_PEEK', {
                target: target
            });
        },

        // 占い師: 行動終了（サーバーに通知）
        seerConfirm() {
            this.sendMessage('WEREWOLF_NIGHT_ACTION', {
                action: 'seer_look',
                target: this.seerTarget || 'none'
            });
        },

        // 怪盗: 交換
        thiefSwap(target) {
            this.sendMessage('WEREWOLF_NIGHT_ACTION', {
                action: 'thief_swap',
                target: target
            });
        },

        // 投票
        submitWerewolfVote() {
            if (!this.werewolfVoteTarget) return;
            this.sendMessage('WEREWOLF_VOTE', {
                target_player_id: this.werewolfVoteTarget
            });
            this.hasAnswered = true;
        }
    }
}
