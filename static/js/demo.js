/**
 * Medical AI Assistant - Demo Logic
 */

// 使用一個立即執行的匿名函數 (IIFE) 或是單一 DOMContentLoaded 來保護作用域
document.addEventListener('DOMContentLoaded', () => {
    // --- 1. 取得 DOM 元素 ---
    const widgetTrigger = document.getElementById('chat-widget-trigger');
    const closeBtn = document.getElementById('close-chat');
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-input');
    const chatContainer = document.getElementById('chat-container');
    const chatBox = document.getElementById('chat-box');

    // --- 2. 事件綁定 ---
    if (widgetTrigger) widgetTrigger.addEventListener('click', toggleChat);
    if (closeBtn) closeBtn.addEventListener('click', toggleChat);
    if (sendBtn) sendBtn.addEventListener('click', handleSend);
    if (userInput) {
        userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleSend();
        });
    }

    // --- 3. 功能函式 ---

    function toggleChat() {
        const isFlex = chatContainer.style.display === 'flex';
        chatContainer.style.display = isFlex ? 'none' : 'flex';
    }

    async function handleSend() {
        const text = userInput.value.trim();
        if (!text) return;

        // 顯示用戶訊息
        appendMessage('user-msg', text);
        userInput.value = '';
        scrollToBottom();

        // 顯示 Loading 並紀錄 ID 以便後續移除
        const loadingId = 'loading-' + Date.now();
        appendLoading(loadingId);

        try {
            const res = await fetch('/api/v1/demo/quick-chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, userId: "default-user" })
            });

            const result = await res.json();

            // 移除 Loading
            const loadingEl = document.getElementById(loadingId);
            if (loadingEl) loadingEl.remove();

            // 執行渲染邏輯
            renderAIResponse(result.data.text);

        } catch (e) {
            console.error("API Error:", e);
            const loadingEl = document.getElementById(loadingId);
            if (loadingEl) {
                loadingEl.innerHTML = '<i class="fas fa-exclamation-circle"></i> 連線失敗，請檢查網路。';
            }
        }
        scrollToBottom();
    }

    /**
     * 核心渲染邏輯：將 LLM 回傳的 JSON 轉為 HTML 結構
     * 升級版：支援 highlights 顯示與多模態並存
     */
    function renderAIResponse(jsonString) {
        const aiMsgDiv = document.createElement('div');
        aiMsgDiv.className = 'message ai-msg';

        try {
            const data = JSON.parse(jsonString);

            // 基礎文字總結
            let htmlContent = `<div class="summary" style="margin-bottom: 12px; font-weight: bold; border-left: 3px solid #3498db; padding-left: 8px;">${data.summary}</div>`;

            // 顯示 Highlights 關鍵卡片 (不論什麼 mode，只要有 highlights 就顯示)
            if (data.highlights && Object.keys(data.highlights).length > 0) {
                htmlContent += `<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px;">`;
                for (const [key, value] of Object.entries(data.highlights)) {
                    htmlContent += `
                    <div style="background: #fff5f5; border: 1px solid #fed7d7; padding: 8px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 11px; color: #c53030; margin-bottom: 2px;">${key}</div>
                        <div style="font-size: 16px; font-weight: bold; color: #9b2c2c;">${value}</div>
                    </div>`;
                }
                htmlContent += `</div>`;
            }

            // 根據模式呈現主要內容
            if (data.mode === 'stats' && data.statistics) {
                //傳統統計模式
                htmlContent += generateStatsCards(data.statistics);
            }

            // 明細列表 (只要有 data_list 且長度大於 0 就顯示表格)
            // 這樣可以滿足「告訴我有幾筆，並列出來」的需求
            if (data.data_list && data.data_list.length > 0) {
                if (data.mode === 'highlights') {
                    htmlContent += `<div style="font-size: 12px; color: #888; margin-bottom: 4px;">符合條件的數據明細：</div>`;
                }
                htmlContent += generateTableHTML(data.data_list);
            }

            aiMsgDiv.innerHTML = htmlContent;
        } catch (e) {
            // 解析失敗則降級為純文字
            aiMsgDiv.textContent = jsonString;
        }

        chatBox.appendChild(aiMsgDiv);
    }

    function generateTableHTML(list) {
        if (!list || list.length === 0) return '<p style="font-size:12px; color:#888;">無相關紀錄。</p>';

        const rows = list.map(item => {
            const isHigh = item.sys >= 140 || item.dia >= 90;
            const dateStr = item.date ? item.date.split(' ')[0] : '-';
            return `
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px 0; color: #666;">${dateStr}</td>
                    <td style="padding: 8px 0; text-align: center; ${isHigh ? 'color: #e74c3c; font-weight: bold;' : ''}">
                        ${item.sys}/${item.dia}
                    </td>
                    <td style="padding: 8px 0; text-align: center;">${item.pul}</td>
                </tr>`;
        }).join('');

        return `
            <div style="overflow-x: auto;">
                <table style="width:100%; border-collapse: collapse; font-size: 13px;">
                    <thead>
                        <tr style="text-align: left; color: #999; font-size: 11px; border-bottom: 2px solid #f4f4f4;">
                            <th>日期</th><th style="text-align: center;">血壓(S/D)</th><th style="text-align: center;">心率</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;
    }

    function generateStatsCards(stats) {
        const avgSys = Math.round(stats.avg_sys || stats.average_sys || 0);
        const maxSys = stats.max_sys || 0;

        return `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px;">
                <div style="background: #ebf5fb; padding: 10px; border-radius: 10px; text-align: center;">
                    <div style="font-size: 10px; color: #5dade2; margin-bottom: 4px;">平均收縮壓</div>
                    <div style="font-size: 16px; font-weight: bold; color: #2e86c1;">${avgSys}</div>
                </div>
                <div style="background: #fef5e7; padding: 10px; border-radius: 10px; text-align: center;">
                    <div style="font-size: 10px; color: #f39c12; margin-bottom: 4px;">最高收縮壓</div>
                    <div style="font-size: 16px; font-weight: bold; color: #d35400;">${maxSys}</div>
                </div>
            </div>`;
    }

    // --- 輔助工具 ---

    function appendMessage(className, text) {
        const msg = document.createElement('div');
        msg.className = `message ${className}`;
        msg.textContent = text;
        chatBox.appendChild(msg);
    }

    function appendLoading(id) {
        const loading = document.createElement('div');
        loading.className = 'message ai-msg';
        loading.id = id;
        loading.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 分析數據中...';
        chatBox.appendChild(loading);
    }

    function scrollToBottom() {
        chatBox.scrollTop = chatBox.scrollHeight;
    }
});