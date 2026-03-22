// ========================================
// chat-stream-ui.js - Shared chat streaming helpers
// 職責：共用 timer/progress/SSE buffer 邏輯
// ========================================

const ChatStreamUI = window.ChatStreamUI || {
    updateTimers(targetDiv, elapsedSeconds) {
        if (!targetDiv) return;
        targetDiv.querySelectorAll('#loading-timer').forEach((display) => {
            display.textContent = `${elapsedSeconds}s`;
        });
    },

    applyProgress(botMsgDiv, progressData) {
        if (!botMsgDiv || !progressData) return;

        if (progressData.message) {
            const loadingLabel = botMsgDiv.querySelector('.process-container span.font-medium');
            if (loadingLabel) {
                loadingLabel.textContent = progressData.message;
            }
        }

        const stepNum = progressData.step;
        const stepEl = botMsgDiv.querySelector(`.plan-step[data-step="${stepNum}"]`);
        if (!stepEl) return;

        const check = stepEl.querySelector('.plan-check');
        if (progressData.type === 'agent_start') {
            if (check) {
                check.innerHTML =
                    '<i data-lucide="loader-2" class="w-3 h-3 text-primary animate-spin"></i>';
            }
            stepEl.classList.add('bg-primary/5', 'border-primary/20');
        } else if (progressData.type === 'agent_finish') {
            if (check) {
                if (progressData.success) {
                    check.innerHTML = '<i data-lucide="check" class="w-3 h-3 text-primary"></i>';
                } else {
                    check.innerHTML =
                        '<i data-lucide="alert-circle" class="w-3 h-3 text-danger"></i>';
                    stepEl.classList.add('border-danger/20');
                }
            }
            stepEl.classList.remove('bg-primary/5', 'animate-pulse');
        } else if (progressData.type === 'parallel_group_start') {
            stepEl.classList.add('bg-primary/5', 'border-primary/20', 'animate-pulse');
        } else if (progressData.type === 'parallel_group_finish') {
            stepEl.classList.remove('bg-primary/5', 'animate-pulse');
        }

        if (window.lucide && typeof window.createIconsIn === 'function') {
            window.createIconsIn(botMsgDiv);
        }
    },

    consumeChunk(buffer, chunk) {
        const pending = (buffer || '') + chunk;
        const lines = pending.split('\n');
        return {
            lines: lines.slice(0, -1),
            pending: lines[lines.length - 1] || '',
        };
    },
};
window.ChatStreamUI = ChatStreamUI;

export { ChatStreamUI };
