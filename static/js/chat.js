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
    // 如果後端沒傳 graph 字串過來，就不執行
    if (!graphContainer || !payload.graph) return;

    graphContainer.removeAttribute('data-processed');

    let mermaidCode = payload.graph;
    const intent = payload.intent;

    let highlightNode = intent;
    if (intent === 'health_query') {
        highlightNode = 'fetch_records'; // 純查詢時，高亮停止的那個節點
    } else if (intent === 'health_analyst') {
        highlightNode = 'health_analyst';
    }

    if (mermaidCode.includes(highlightNode)) {
        mermaidCode += `\nclass ${highlightNode} activeNode`;
    }

    // 緊急狀態特殊高亮
    if (payload.is_emergency || mermaidCode.includes('activeEmergencyNode')) {
        mermaidCode += '\nclass emergency_advice activeEmergencyNode';
    }

    graphContainer.innerHTML = mermaidCode;

    try {
        await mermaid.run({ nodes: [graphContainer] });
        // SVG 自適應處理 ...
    } catch (err) {
        console.error("Mermaid Render Error:", err);
    }
}

// 主發送函數
async function sendMessage() {
    const input = document.getElementById('userInput');
    const chatBox = document.getElementById('chat-box');
    const message = input.value.trim();
    if (!message) return;

    // 用戶訊息 UI
    chatBox.innerHTML += `<div class="msg user-msg">${message}</div>`;
    input.value = '';

    const loadingId = "loading-" + Date.now();
    chatBox.innerHTML += `<div class="msg agent-msg" id="${loadingId}">分析路徑中...</div>`;
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const response = await fetch('/api/v1/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, userId: "default-user" })
        });

        const json = await response.json();
        const payload = json.data;

        let finalUI = beautifyContent(payload);

        document.getElementById(loadingId).innerHTML = finalUI;

        // 執行圖表更新
        await renderGraph(payload);
        setTimeout(() => {
            const chatBox = document.getElementById('chat-box');
            chatBox.scrollTo({ top: chatBox.scrollHeight, behavior: 'smooth' });
        }, 100);
    } catch (error) {
        console.error("Chat Error:", error);
        document.getElementById(loadingId).innerText = "連線失敗，請檢查網路或系統狀態。";
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