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
            'result': 'result.mp3',
            // ワンナイト人狼の夜フェーズ音声
            'night_closing_eyes': 'closing_eyes.wav',
            'night_werewolf': 'werewolf.wav',
            'night_seer': 'seer.wav',
            'night_thief': 'thief.wav',
            'night_done': 'done.wav',
            'were_reveal': 'were_reveal.mp3'
        };
        this.enabled = false;
        this.activeSources = [];  // 再生中の音源を追跡
        this.pendingTimers = [];  // 待機中のタイマーを追跡
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

    play(key, onEnded = null) {
        if (!this.enabled || !this.ctx) {
            // オーディオが無効な場合は5秒後にコールバック
            if (onEnded) {
                const timerId = setTimeout(onEnded, 5000);
                this.pendingTimers.push(timerId);
            }
            return;
        }

        // バッファがまだロードされていない場合は待機してリトライ
        if (!this.buffers[key]) {
            console.log("Buffer not ready for", key, "- waiting...");
            let retryCount = 0;
            const maxRetries = 20; // 最大2秒待機
            const checkBuffer = () => {
                retryCount++;
                if (this.buffers[key]) {
                    // バッファが準備できた
                    this.play(key, onEnded);
                } else if (retryCount >= maxRetries) {
                    // タイムアウト - 5秒後にコールバック
                    console.warn("Buffer load timeout for", key);
                    if (onEnded) {
                        const timerId = setTimeout(onEnded, 5000);
                        this.pendingTimers.push(timerId);
                    }
                } else {
                    // 100ms後に再チェック
                    const timerId = setTimeout(checkBuffer, 100);
                    this.pendingTimers.push(timerId);
                }
            };
            const timerId = setTimeout(checkBuffer, 100);
            this.pendingTimers.push(timerId);
            return;
        }

        try {
            const source = this.ctx.createBufferSource();
            source.buffer = this.buffers[key];
            source.connect(this.ctx.destination);

            // 再生終了時にリストから削除
            source.onended = () => {
                const index = this.activeSources.indexOf(source);
                if (index > -1) {
                    this.activeSources.splice(index, 1);
                }
                if (onEnded) onEnded();
            };

            source.start(0);
            this.activeSources.push(source);  // 再生中リストに追加
        } catch (e) {
            console.error("Play Error", e);
            if (onEnded) {
                const timerId = setTimeout(onEnded, 5000);
                this.pendingTimers.push(timerId);
            }
        }
    }

    // すべての再生を停止
    stopAll() {
        // 再生中の音源を停止
        for (const source of this.activeSources) {
            try {
                source.stop();
            } catch (e) {
                // すでに停止している場合は無視
            }
        }
        this.activeSources = [];

        // 待機中のタイマーをクリア
        for (const timerId of this.pendingTimers) {
            clearTimeout(timerId);
        }
        this.pendingTimers = [];
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
        itoState: null,    // Ito State
        werewolfState: null, // One Night Werewolf State
        showItoFailedOverlay: false,  // ito失敗演出用
        showItoSuccessOverlay: false,  // ito成功演出用
        discussionTimeRemaining: 0, // 議論残り時間
        discussionTimer: null,  // 議論タイマー
        nightCountdown: 0,  // 夜フェーズカウントダウン
        nightCountdownTimer: null,  // 夜フェーズカウントダウンタイマー
        lastNightPhase: null,  // 前回の夜フェーズ（自動TTS用）

        config: {
            speedStar: true,
            shuffle: true,
            discussionTime: 180,
            itoCoop: true,
            itoCloseCall: false,
            werewolfMadman: true
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

            // ページリロード/離脱時にクリーンアップ
            window.addEventListener('beforeunload', () => {
                this.cleanup();
            });
        },

        // クリーンアップ処理
        cleanup() {
            // 音声再生を停止
            this.sounds.stopAll();

            // 夜フェーズカウントダウンタイマーを停止
            if (this.nightCountdownTimer) {
                clearInterval(this.nightCountdownTimer);
                this.nightCountdownTimer = null;
            }

            // 議論タイマーを停止
            if (this.discussionTimer) {
                clearInterval(this.discussionTimer);
                this.discussionTimer = null;
            }
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
                    // ワンナイト人狼は専用の結果発表音
                    if (this.mode === 'ONE_NIGHT_WEREWOLF') {
                        this.sounds.play('were_reveal');
                    } else {
                        this.sounds.play('reveal');
                    }
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

            // ito失敗検知
            const oldItoState = this.itoState;
            this.itoState = data.ito_state;

            // カードが出された瞬間を検知
            if (this.itoState && oldItoState) {
                const oldCardCount = oldItoState.played_cards?.length || 0;
                const newCardCount = this.itoState.played_cards?.length || 0;
                const oldFailedCount = oldItoState.played_cards?.filter(c => c.is_failed).length || 0;
                const newFailedCount = this.itoState.played_cards?.filter(c => c.is_failed).length || 0;

                if (newFailedCount > oldFailedCount) {
                    // 失敗カードが新たに出された
                    this.showItoFailedOverlay = true;
                    this.sounds.play('timeup'); // 失敗音
                    setTimeout(() => {
                        this.showItoFailedOverlay = false;
                    }, 2000);
                } else if (newCardCount > oldCardCount && newFailedCount === oldFailedCount) {
                    // 成功カードが出された（カードは増えたが失敗は増えてない）
                    this.showItoSuccessOverlay = true;
                    this.sounds.play('reveal'); // 成功音
                    setTimeout(() => {
                        this.showItoSuccessOverlay = false;
                    }, 1500);
                }
            }

            this.config = {
                speedStar: data.config_speed_star,
                shuffle: data.config_shuffle,
                discussionTime: data.config_discussion_time,
                itoCoop: data.config_ito_coop ?? true,
                itoCloseCall: data.config_ito_close_call ?? false,
                werewolfMadman: data.config_werewolf_madman ?? true
            };

            // Werewolf State
            const oldWerewolfState = this.werewolfState;
            this.werewolfState = data.werewolf_state;

            // 夜フェーズの自動音声再生
            if (this.mode === 'ONE_NIGHT_WEREWOLF' && this.werewolfState) {
                const currentNightPhase = this.werewolfState.night_phase;
                if (currentNightPhase !== this.lastNightPhase) {
                    this.lastNightPhase = currentNightPhase;
                    // フェーズが変わったら自動で音声を再生
                    this.autoPlayNightAudio(currentNightPhase);
                }

                // 行動完了時にカウントダウンを5秒にリセット
                if (oldWerewolfState && this.werewolfState.night_actions_done) {
                    const oldActionsDone = oldWerewolfState.night_actions_done || {};
                    const newActionsDone = this.werewolfState.night_actions_done;
                    // 新しく行動完了した人がいる場合
                    const newlyDone = Object.keys(newActionsDone).some(pid => !oldActionsDone[pid]);
                    if (newlyDone && this.nightCountdownTimer && this.nightCountdown > 5) {
                        // カウントダウンを5秒にリセット
                        this.nightCountdown = 5;
                    }
                }
            }

            // 議論タイマーの開始（ワンナイト人狼 or WordWolf）
            if (this.phase === 'JUDGING' && this.mode === 'ONE_NIGHT_WEREWOLF' && this.werewolfState) {
                this.startDiscussionTimer(this.werewolfState.discussion_end_time);
            } else if (this.phase === 'ANSWERING' && this.mode === 'WORD_WOLF' && this.wordWolfState) {
                this.startDiscussionTimer(this.wordWolfState.discussion_end_time);
            }

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
            if (key === 'speedStar') {
                this.config.speedStar = !this.config.speedStar;
                this.sendMessage('UPDATE_CONFIG', { type: 'speed_star', value: this.config.speedStar });
            } else if (key === 'shuffle') {
                this.config.shuffle = !this.config.shuffle;
                this.sendMessage('UPDATE_CONFIG', { type: 'shuffle', value: this.config.shuffle });
            } else if (key === 'ito_coop') {
                this.config.itoCoop = !this.config.itoCoop;
                this.sendMessage('UPDATE_CONFIG', { type: 'ito_coop', value: this.config.itoCoop });
            } else if (key === 'ito_close_call') {
                this.config.itoCloseCall = !this.config.itoCloseCall;
                this.sendMessage('UPDATE_CONFIG', { type: 'ito_close_call', value: this.config.itoCloseCall });
            } else if (key === 'werewolf_madman') {
                this.config.werewolfMadman = !this.config.werewolfMadman;
                this.sendMessage('UPDATE_CONFIG', { type: 'werewolf_madman', value: this.config.werewolfMadman });
            }
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

        // --- Ito Actions ---
        itoNextStage() {
            this.sendMessage('ITO_NEXT_STAGE');
        },

        itoShowResult() {
            this.sendMessage('ITO_SHOW_RESULT');
        },

        itoPlayAgain() {
            this.sendMessage('START_GAME', { mode: 'ITO' });
        },

        // --- Werewolf Actions ---
        werewolfStartNight() {
            this.sendMessage('WEREWOLF_START_NIGHT');
        },

        werewolfAdvanceNight() {
            this.sendMessage('WEREWOLF_ADVANCE_NIGHT');
        },

        werewolfStartDiscussion() {
            this.sendMessage('WEREWOLF_START_DISCUSSION');
        },

        werewolfFinishVoting() {
            this.sendMessage('WEREWOLF_FINISH_VOTING');
        },

        werewolfPlayAgain() {
            this.sendMessage('START_GAME', { mode: 'ONE_NIGHT_WEREWOLF' });
        },

        // 夜フェーズの自動音声再生
        autoPlayNightAudio(phase) {
            let soundKey = '';
            let countdownTime = 10;  // デフォルト10秒

            // その役職のプレイヤーがいるかチェック
            const hasRolePlayer = (role) => {
                if (!this.werewolfState || !this.werewolfState.original_roles) return false;
                return Object.values(this.werewolfState.original_roles).includes(role);
            };

            if (phase === 'closing_eyes') {
                soundKey = 'night_closing_eyes';
                countdownTime = 3;  // 目を閉じるは3秒
            } else if (phase === 'werewolf') {
                soundKey = 'night_werewolf';
                // 人狼がいない場合は10秒（音声だけ流して自動進行）
                if (!hasRolePlayer('werewolf')) {
                    countdownTime = 10;
                }
            } else if (phase === 'seer') {
                soundKey = 'night_seer';
                // 占い師がいない場合は10秒
                if (!hasRolePlayer('seer')) {
                    countdownTime = 10;
                }
            } else if (phase === 'thief') {
                soundKey = 'night_thief';
                // 怪盗がいない場合は10秒
                if (!hasRolePlayer('thief')) {
                    countdownTime = 10;
                }
            } else if (phase === 'done') {
                soundKey = 'night_done';
            }

            // 既存のタイマーをクリア
            if (this.nightCountdownTimer) {
                clearInterval(this.nightCountdownTimer);
                this.nightCountdownTimer = null;
            }

            // カウントダウンを開始する関数
            const startCountdown = () => {
                if (phase === 'done') {
                    // doneフェーズ: カウントダウンなしで即座に議論フェーズへ遷移
                    this.nightCountdown = 0;
                    this.werewolfStartDiscussion();
                } else {
                    this.nightCountdown = countdownTime;
                    this.nightCountdownTimer = setInterval(() => {
                        this.nightCountdown--;
                        if (this.nightCountdown <= 0) {
                            clearInterval(this.nightCountdownTimer);
                            this.nightCountdownTimer = null;
                            // 自動で次のフェーズへ進む
                            this.werewolfAdvanceNight();
                        }
                    }, 1000);
                }
            };

            // WAV音声を再生し、再生完了後にカウントダウン開始
            if (soundKey) {
                this.nightCountdown = '-';  // 再生中は「-」を表示
                this.sounds.play(soundKey, () => {
                    startCountdown();
                });
            } else {
                // 音声がない場合はすぐにカウントダウン開始
                startCountdown();
            }
        },

        // 手動で音声を再生（リプレイ用）
        speakNightPhase() {
            const phase = this.werewolfState?.night_phase;
            this.autoPlayNightAudio(phase);
        },

        // Discussion Timer
        startDiscussionTimer(endTime) {
            if (this.discussionTimer) {
                clearInterval(this.discussionTimer);
            }

            const updateTimer = () => {
                const now = Date.now() / 1000;
                const remaining = Math.max(0, endTime - now);
                this.discussionTimeRemaining = Math.ceil(remaining);

                if (remaining <= 0) {
                    clearInterval(this.discussionTimer);
                    this.discussionTimer = null;
                }
            };

            updateTimer();
            this.discussionTimer = setInterval(updateTimer, 1000);
        },

        formatTime(seconds) {
            const min = Math.floor(seconds / 60);
            const sec = seconds % 60;
            return `${min}:${sec.toString().padStart(2, '0')}`;
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
