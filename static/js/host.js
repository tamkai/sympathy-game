class SoundManager {
    constructor() {
        this.ctx = null;
        this.buffers = {};
        this.sounds = {
            'join': 'join.mp3',
            'start': 'start.mp3',
            'tick': 'tick.mp3',
            'timeup': 'timeup.mp3',
            'vote': 'vote.mp3',
            'reveal': 'reveal.mp3',
            'decision': 'decision.mp3',
            'result': 'result.mp3'
        };
        this.enabled = false;
    }

    init() {
        if (this.ctx) return;
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.ctx = new AudioContext();
            this.enabled = true;
            this.loadAll();
            console.log("Audio Context Initialized");
        } catch (e) {
            console.error("Audio Init Failed", e);
        }
    }

    async loadAll() {
        for (const [key, file] of Object.entries(this.sounds)) {
            try {
                const response = await fetch('/static/sounds/' + file);
                if (response.ok) {
                    const arrayBuffer = await response.arrayBuffer();
                    this.ctx.decodeAudioData(arrayBuffer, (decodedBuffer) => {
                        this.buffers[key] = decodedBuffer;
                    }, (e) => console.warn("Decode Error " + file, e));
                }
            } catch (e) {
                // Silent fail if file missing (expected initially)
            }
        }
    }

    play(key) {
        if (!this.enabled || !this.ctx || !this.buffers[key]) return;
        try {
            const source = this.ctx.createBufferSource();
            source.buffer = this.buffers[key];
            source.connect(this.ctx.destination);
            source.start(0);
        } catch (e) {
            console.error("Play Error", e);
        }
    }
}

function hostApp(networkIp) {
    return {
        sounds: new SoundManager(),
        initAudio() {
            this.sounds.init();
        },
        ws: null,
        roomId: '',
        clientId: 'HOST-' + Math.random().toString(36).substr(2, 9),

        // Game State
        phase: 'LOBBY',
        mode: 'SYMPATHY',

        // Host Selection State
        selectedMode: 'SYMPATHY',

        players: {},
        answers: {},
        currentQuestion: '',
        bombOwnerId: null,
        shuffleTriggered: false,
        winnerId: null,
        speedStarId: null,
        wordWolfState: null,
        sekaiState: null,  // Sekai No Mikata State

        config: {
            speedStar: true,
            shuffle: true,
            discussionTime: 180
        },

        // Computed / UI State
        joinUrl: '',
        showResetModal: false,

        init() {
            // Robust roomId extraction
            const parts = document.location.pathname.split('/');
            this.roomId = parts[parts.length - 1] || parts[parts.length - 2];

            // Use origin for production (Render, etc.) or local network IP for local dev
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                // Local development - use network IP for smartphone access
                if (networkIp && networkIp !== '127.0.0.1') {
                    const protocol = window.location.protocol;
                    const port = window.location.port ? ':' + window.location.port : '';
                    this.joinUrl = protocol + '//' + networkIp + port + "/play/" + this.roomId;
                } else {
                    this.joinUrl = window.location.origin + "/play/" + this.roomId;
                }
            } else {
                // Production - always use the current origin
                this.joinUrl = window.location.origin + "/play/" + this.roomId;
            }

            this.connectWebSocket();
            this.generateQRCode();
        },

        connectWebSocket() {
            const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
            this.ws = new WebSocket(`${proto}://${window.location.host}/ws/${this.roomId}/${this.clientId}`);

            this.ws.onopen = () => {
                console.log("Connected to WS");
            };

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
                console.log("Disconnected");
                setTimeout(() => this.connectWebSocket(), 3000);
            };
        },

        updateState(data) {
            const oldPhase = this.phase;
            const oldPlayerCount = Object.keys(this.players).length;
            const oldAnswerCount = Object.keys(this.answers).length;

            this.phase = data.phase;
            this.mode = data.mode;
            this.players = data.players || {};
            this.answers = data.answers || {};

            // SOUND TRIGGERS
            // 1. Phase Change
            if (this.phase !== oldPhase) {
                if (this.phase === 'ANSWERING' || this.phase === 'DESCRIPTION') {
                    // Only silence for Word Wolf Description (Game Start), play for Discussion
                    if (this.mode === 'WORD_WOLF' && this.phase === 'DESCRIPTION') {
                        // Silent
                    } else {
                        this.sounds.play('start');
                    }
                } else if (this.phase === 'RESULT') {
                    this.sounds.play('reveal');
                } else if (this.phase === 'JUDGING') {
                    if (this.mode !== 'SYMPATHY') {
                        this.sounds.play('decision');
                    } else {
                        this.sounds.play('result');
                    }
                }
            }

            // 2. Player Join
            if (Object.keys(this.players).length > oldPlayerCount) {
                this.sounds.play('join');
            }

            // 3. Answer/Vote
            if (Object.keys(this.answers).length > oldAnswerCount) {
                this.sounds.play('vote');
            }
            this.currentQuestion = data.current_question || '';
            this.bombOwnerId = data.bomb_owner_id;
            this.shuffleTriggered = data.shuffle_triggered_in_round;
            this.winnerId = data.winner_id;
            this.speedStarId = data.speed_star_id;
            this.wordWolfState = data.word_wolf_state;
            this.sekaiState = data.sekai_state;

            this.config = {
                speedStar: data.config_speed_star,
                shuffle: data.config_shuffle,
                discussionTime: data.config_discussion_time
            };

            if (this.phase === 'LOBBY' && oldPhase !== 'LOBBY') {
                this.generateQRCode();
            }
        },

        sendMessage(type, data = {}) {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type, data }));
            }
        },

        // --- Actions ---

        toggleConfig(key) {
            this.config[key] = !this.config[key];
            this.sendMessage('UPDATE_CONFIG', {
                type: key === 'speedStar' ? 'speed_star' : 'shuffle',
                value: this.config[key]
            });
        },

        updateDiscussionTime(delta) {
            let newTime = this.config.discussionTime + delta;
            if (newTime < 60) newTime = 60;
            if (newTime > 600) newTime = 600;

            this.config.discussionTime = newTime;
            this.sendMessage('UPDATE_CONFIG', {
                type: 'discussion_time',
                value: newTime
            });
        },

        startGame() {
            this.sendMessage('START_GAME', { mode: this.selectedMode });
        },

        startRound() {
            this.sendMessage('NEXT_ROUND');
        },

        startWordWolfDiscussion() {
            this.sendMessage('START_DISCUSSION');
        },

        finishAnswering() {
            this.sendMessage('SKIP_TO_JUDGING');
        },

        finalizeJudging() {
            this.sendMessage('FINISH_JUDGING');
        },

        finishVoting() {
            this.sendMessage('FINISH_JUDGING');
        },

        nextRound() {
            this.sendMessage('NEXT_ROUND');
        },

        resetGame() {
            this.sendMessage('RESET_GAME');
            this.showResetModal = false;
        },

        updateConfig(key, value) {
            this.config[key] = value;
            this.sendMessage('UPDATE_CONFIG', {
                speed_star: this.config.speedStar,
                shuffle: this.config.shuffle
            });
        },

        // --- Sekai No Mikata Actions ---
        sekaiSelectAnswer(answerId) {
            this.sendMessage('SEKAI_SELECT_ANSWER', { answer_id: answerId });
        },

        sekaiNextRound() {
            this.sendMessage('SEKAI_NEXT_ROUND');
        },

        // Helper to get current reader name
        get sekaiReaderName() {
            if (!this.sekaiState || !this.sekaiState.current_reader_id) return '';
            const player = this.players[this.sekaiState.current_reader_id];
            return player ? player.name : '';
        },

        // Helper to get selected answer details
        get sekaiSelectedAnswer() {
            if (!this.sekaiState || !this.sekaiState.selected_answer_id) return null;
            return this.sekaiState.all_answers_for_display.find(
                a => a.answer_id === this.sekaiState.selected_answer_id
            );
        },

        // --- Drag & Drop ---
        // (Keeping existing logic streamlined)

        onDragStart(event, answerId) {
            event.dataTransfer.setData('text/plain', answerId);
            event.dataTransfer.effectAllowed = 'move';
        },

        onDragOver(event) {
            event.preventDefault();
        },

        onDrop(event) {
            const answerId = event.dataTransfer.getData('text/plain');
            const dropZone = event.target.closest('[data-group-id]');
            if (dropZone && answerId) {
                const targetGroupId = dropZone.dataset.groupId;
                this.sendMessage('UPDATE_GROUPING', {
                    answers: { [answerId]: { group_id: targetGroupId } }
                });
            }
        },

        // Touch logic omitted for brevity in replacement (keeping core working)
        // Recopying Touch logic because partial replacement removes it otherwise!
        // Wait, replace_file_content replaces range.
        // I should include touch logic if I replace the whole file or large chunk.
        // I am replacing from line 1 to 375 (Whole File).
        // I MUST include Touch Logic.

        // Touch support state
        touchDragAnswerId: null,
        touchStartX: 0,
        touchStartY: 0,

        onTouchStart(event, answerId) {
            this.touchDragAnswerId = answerId;
            const touch = event.touches[0];
            this.touchStartX = touch.clientX;
            this.touchStartY = touch.clientY;
            if (event.target && event.target.classList) {
                event.target.classList.add('opacity-50', 'scale-105');
            }
        },

        onTouchMove(event) {
            if (!this.touchDragAnswerId) return;
            event.preventDefault();
        },

        onTouchEnd(event) {
            if (!this.touchDragAnswerId) return;
            const touch = event.changedTouches[0];
            const dropElement = document.elementFromPoint(touch.clientX, touch.clientY);
            const dropZone = dropElement?.closest('[data-group-id]');
            const groupingBoard = dropElement?.closest('#grouping-board');

            if (dropZone && this.touchDragAnswerId) {
                // Dropped on a group - move to that group
                const targetGroupId = dropZone.dataset.groupId;
                if (targetGroupId !== this.answers[this.touchDragAnswerId]?.group_id) {
                    this.sendMessage('UPDATE_GROUPING', {
                        answers: { [this.touchDragAnswerId]: { group_id: targetGroupId } }
                    });
                }
            } else if (groupingBoard && this.touchDragAnswerId) {
                // Dropped outside any group but inside the board - ungroup (create own group)
                this.sendMessage('UPDATE_GROUPING', {
                    answers: { [this.touchDragAnswerId]: { group_id: this.touchDragAnswerId } }
                });
            }
            document.querySelectorAll('.opacity-50').forEach(el => el.classList.remove('opacity-50', 'scale-105'));
            this.touchDragAnswerId = null;
        },

        onDropUngroup(event) {
            const answerId = event.dataTransfer.getData('text/plain');
            if (answerId && this.answers[answerId]) {
                this.sendMessage('UPDATE_GROUPING', { answers: { [answerId]: { group_id: answerId } } });
            }
        },

        onTouchEndUngroup(event) {
            if (!this.touchDragAnswerId) return;
            const touch = event.changedTouches[0];
            const dropElement = document.elementFromPoint(touch.clientX, touch.clientY);
            const dropZone = dropElement?.closest('[data-group-id]');
            if (!dropZone && this.touchDragAnswerId) {
                this.sendMessage('UPDATE_GROUPING', { answers: { [this.touchDragAnswerId]: { group_id: this.touchDragAnswerId } } });
            }
            document.querySelectorAll('.opacity-50').forEach(el => el.classList.remove('opacity-50', 'scale-105'));
            this.touchDragAnswerId = null;
        },


        // --- Computeds ---

        generateQRCode() {
            setTimeout(() => {
                const container = document.getElementById("qrcode");
                if (container && typeof QRCode !== 'undefined') {
                    container.innerHTML = "";
                    try {
                        new QRCode(container, {
                            text: this.joinUrl,
                            width: 128,
                            height: 128
                        });
                    } catch (e) { console.error("QRCode Error", e); }
                }
            }, 100);
        },

        get answerProgress() {
            const total = Object.keys(this.players).length;
            if (total === 0) return 0;
            return (this.answeredCount / total) * 100;
        },

        get answeredCount() {
            return Object.values(this.players).filter(p => p.has_answered).length;
        },

        get groups() {
            const groupsMap = {};
            Object.values(this.answers).forEach(ans => {
                if (!groupsMap[ans.group_id]) {
                    groupsMap[ans.group_id] = { id: ans.group_id, answers: [] };
                }
                groupsMap[ans.group_id].answers.push(ans);
            });
            return Object.values(groupsMap);
        },

        get sortedPlayers() {
            return Object.values(this.players).sort((a, b) => b.score - a.score);
        },

        get resultStats() {
            // Sympathy
            if (this.mode === 'SYMPATHY') {
                const groups = this.groups;
                if (groups.length === 0) {
                    return { majorityAnswer: '回答なし', majorityCount: 0, minorityPlayerName: 'なし' };
                }

                let maxCount = 0;
                let majorityGroup = null;
                groups.forEach(g => {
                    if (g.answers.length > maxCount) {
                        maxCount = g.answers.length;
                        majorityGroup = g;
                    }
                });

                const majorityAnswer = majorityGroup && majorityGroup.answers.length > 1
                    ? majorityGroup.answers[0].raw_text
                    : '特になし';

                const bombOwner = this.players[this.bombOwnerId];
                const minorityPlayerName = bombOwner ? bombOwner.name : 'なし';

                const speedStarPlayer = this.players[this.speedStarId];
                const speedStarName = speedStarPlayer ? speedStarPlayer.name : null;

                return { majorityAnswer, majorityCount: maxCount, minorityPlayerName, speedStarName };
            }
            // Word Wolf
            else if (this.mode === 'WORD_WOLF' && this.wordWolfState) {
                return {
                    wolfWon: this.wordWolfState.wolf_won,
                    wolfName: this.wordWolfState.wolf_name,
                    winningReason: this.wordWolfState.winning_reason,
                    majorityTopic: this.wordWolfState.majority_topic,
                    minorityTopic: this.wordWolfState.minority_topic
                };
            }
            return {};
        }
    }
}
