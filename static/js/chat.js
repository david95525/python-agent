/**
 * AI Agent - Chat Module
 */

// 下載功能
function downloadChart(base64Data) {
    const link = document.createElement('a');
    link.href = base64Data;
    link.download = `Report_${new Date().getTime()}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
window.downloadChart = downloadChart;
// 渲染邏輯 (封裝 Mermaid 處理)
async function renderGraph(payload) {
    const graphContainer = document.getElementById('mermaid-graph');
    const statusDisplay = document.getElementById('intent-display');
    
    // 如果後端沒傳 graph 字串過來，就不執行
    if (!graphContainer || !payload.graph && !payload.content) return;

    graphContainer.removeAttribute('data-processed');

    let mermaidCode = payload.graph || payload.content;
    const intent = payload.intent;
    const currentNode = payload.node; // 這是從單個 graph 事件傳來的 (on_chain_start)

    // 更新系統狀態文字
    if (currentNode && statusDisplay) {
        statusDisplay.innerText = `系統狀態：正在執行 [${currentNode}]`;
    }

    let highlightNode = currentNode;
    
    // 邏輯調整：如果是最終結果 (payload.type === 'final') 且是查詢意圖，高亮 fetch_records
    if (!currentNode && intent === 'health_query') {
        highlightNode = 'fetch_records';
    } else if (!currentNode && intent === 'health_analyst') {
        highlightNode = 'health_analyst';
    } else if (!currentNode && intent === 'device_expert') {
        highlightNode = 'device_expert';
    } else if (!currentNode && intent === 'visualizer') {
        highlightNode = 'visualizer';
    }

    // 關鍵：將 class 注入 Mermaid 原始碼
    if (highlightNode && mermaidCode.includes(highlightNode)) {
        mermaidCode += `\nclass ${highlightNode} activeNode`;
    }

    // 緊急狀態特殊高亮
    if (payload.is_emergency || (payload.data && payload.data.is_emergency)) {
        mermaidCode += '\nclass health_analyst activeEmergencyNode';
    }

    graphContainer.innerHTML = mermaidCode;

    try {
        if (window.mermaid) {
            await window.mermaid.run({ nodes: [graphContainer] });
        }
    } catch (err) {
        console.error("Mermaid Render Error:", err);
    }
}

// 主發送函數 (升級為串流模式)
async function sendMessage() {
    const input = document.getElementById('userInput');
    const chatBox = document.getElementById('chat-box');
    const message = input.value.trim();
    if (!message) return;

    // 用戶訊息 UI
    chatBox.innerHTML += `<div class="msg user-msg">${message}</div>`;
    input.value = '';

    const loadingId = "loading-" + Date.now();
    // 建立一個空的 Agent 回覆容器，準備接收串流
    chatBox.innerHTML += `
        <div class="msg agent-msg">
            <div id="status-${loadingId}" class="status-indicator">思考中...</div>
            <div id="text-${loadingId}" class="content-body"></div>
            <div id="extra-${loadingId}"></div>
        </div>`;
    chatBox.scrollTop = chatBox.scrollHeight;

    const statusEl = document.getElementById(`status-${loadingId}`);
    const textEl = document.getElementById(`text-${loadingId}`);
    const extraEl = document.getElementById(`extra-${loadingId}`);

    try {
        const response = await fetch('/api/v1/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, userId: "default-user" })
        });

        if (!response.ok) throw new Error("網路請求失敗");

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // SSE 格式處理: 尋找以 "data: " 開頭並以 "\n\n" 結尾的區塊
            const lines = buffer.split("\n\n");
            buffer = lines.pop(); // 剩下的不完整內容留給下一輪

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const jsonStr = line.replace("data: ", "");
                try {
                    const event = JSON.parse(jsonStr);

                    if (event.type === "status") {
                        statusEl.innerText = event.content;
                    } else if (event.type === "stream") {
                        // 處理換行符號並即時顯示文字 (打字機效果)
                        textEl.innerHTML += event.content.replace(/\n/g, '<br>');
                    } else if (event.type === "graph") {
                        // 即時更新流程圖
                        await renderGraph(event);
                    } else if (event.type === "interrupt") {
                        statusEl.style.display = "none"; // 隱藏狀態列
                        // 中斷時顯示問題，如果 stream 已經有部分內容，則追加
                        textEl.innerHTML = event.content.replace(/\n/g, '<br>');
                        extraEl.innerHTML = `<div class="interrupt-hint">💡 需要補充資訊以繼續</div>`;
                    } else if (event.type === "final") {
                        const payload = event.data;
                        statusEl.style.display = "none"; // 隱藏狀態列
                        
                        // 執行圖表更新與 UI 美化
                        if (payload.graph) {
                            await renderGraph(payload);
                        }
                        
                        // 如果有額外的 UI 數據 (表格等)，顯示在 extra 區域
                        const beautified = beautifyContent(payload);
                        // 因為文字已經在 stream 階段顯示過了，我們只需要抓取 extraHTML 部分
                        const tempDiv = document.createElement('div');
                        tempDiv.innerHTML = beautified;
                        const extraContent = tempDiv.querySelector('.data-component-container');
                        if (extraContent) {
                            extraEl.appendChild(extraContent);
                        }
                    } else if (event.type === "error") {
                        textEl.innerHTML = `<div class="msg-error">❌ ${event.content}</div>`;
                    }
                } catch (e) {
                    console.error("JSON Parse Error:", e, jsonStr);
                }
            }
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    } catch (error) {
        console.error("Chat Error:", error);
        statusEl.innerText = "連線失敗，請檢查網路或系統狀態。";
    } finally {
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

// 事件綁定
document.addEventListener('DOMContentLoaded', async () => {
    const sendBtn = document.getElementById('sendBtn');
    const userInput = document.getElementById('userInput');
    const graphContainer = document.getElementById('mermaid-graph');

    // 監聽按鈕點擊
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }

    // 監聽 Enter 鍵
    if (userInput) {
        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
});
/**
 * 核心渲染邏輯：嚴格遵守 SKILL.MD，不進行多餘統計
 */
function beautifyContent(payload) {
    // 基礎安全檢查
    if (!payload || payload.intent === 'error') {
        return `<div class="msg-error">❌ ${payload?.text || "系統處理異常"}</div>`;
    }
    let text = payload.text || "";
    // 給予預設文字
    if (payload.intent === 'health_query' && !text) {
        text = "已為您讀取紀錄明細如下：";
    }
    let extraHTML = '';
    const ui = payload.ui_data;

    // 處理圖片與下載按鈕
    text = text.replace(
        /!\[.*?\]\((data:image\/.*?;base64,.*?)\)/g,
        (match, base64Data) => `
            <div class="chart-wrapper">
                <img src="${base64Data}" class="chart-img" />
                <button class="download-btn" onclick="downloadChart('${base64Data}')">
                    <i class="fas fa-download"></i> 下載圖表
                </button>
            </div>
        `
    );

    // 處理換行
    text = text.replace(/\n/g, '<br>');

    // 數據組件偵測
    if (ui && ui.records && ui.records.length > 0) {
        // 使用 intent 來精準判斷模式
        const isAnalysisMode = payload.intent === 'health_analyst';
        const modeClass = isAnalysisMode ? "mode-analysis" : "mode-list";
        const modeLabel = isAnalysisMode ? "專業分析數據來源" : "查詢紀錄明細";

        extraHTML += `
            <div class="data-component-container ${modeClass}">
                <div class="mode-tag">${modeLabel}</div>
                <div class="data-table-scroll-area">
                    ${generateSimpleTable(ui.records)}
                </div>
            </div>`;
    }

    return `<div class="content-body">${text}</div>${extraHTML}`;
}

/**
 * 修改：加入標題與更精簡的結構
 */
function generateSimpleTable(list) {
    const rows = list.map(item => {
        const isHigh = item.sys >= 135 || item.dia >= 85;
        const statusClass = isHigh ? 'val-high' : 'val-normal';
        const dateStr = item.date ? item.date.split(' ')[0] : '-';

        return `
            <tr>
                <td>${dateStr}</td>
                <td class="cell-center ${statusClass}">${item.sys}/${item.dia}</td>
                <td class="cell-center">${item.pul || '-'}</td>
            </tr>`;
    }).join('');

    return `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>日期</th>
                        <th class="cell-center">血壓(S/D)</th>
                        <th class="cell-center">心率</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `;
}