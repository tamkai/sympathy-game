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
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type, data }));
            } else {
                console.warn("WS not open. Cannot send:", type);
            }
        },

        joinGame() {
            console.log("Join Game Clicked. Name:", this.nameInput);
            if (!this.nameInput) return;
            localStorage.setItem('sympathy_player_name', this.nameInput);
            this.sendMessage('JOIN', { name: this.nameInput });
            this.playerName = this.nameInput;
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

        get myRank() {
            const sorted = Object.values(this.players).sort((a, b) => b.score - a.score);
            const index = sorted.findIndex(p => p.player_id === this.clientId);
            return index + 1;
        }
    }
}
