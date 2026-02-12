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
    if (!graphContainer || !payload.graph) return;

    // 清除舊狀態
    graphContainer.removeAttribute('data-processed');

    let mermaidCode = payload.graph;
    const intent = payload.intent;

    // 高亮對應節點
    const nodeMapping = {
        'device_expert': 'device_expert',
        'health_analyst': 'health_analyst',
        'visualizer': 'visualizer',
        'general': 'general_assistant'
    };

    if (nodeMapping[intent]) {
        mermaidCode += `\nclass ${nodeMapping[intent]} activeNode`;
    }

    if (payload.is_emergency) {
        mermaidCode += '\nclass emergency_advice activeEmergencyNode';
    }

    // 更新 DOM 並渲染
    graphContainer.innerHTML = mermaidCode;

    try {
        await mermaid.run({ nodes: [graphContainer] });
        const svg = graphContainer.querySelector('svg');
        if (svg) {
            svg.style.maxWidth = 'none';
            svg.style.width = '100%';
            svg.style.height = 'auto';
        }
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

        // 格式化回覆內容：處理圖片與換行
        let formattedText = payload.text
            .replace(/\n/g, '<br>') // 處理一般換行
            .replace(
                /!\[.*?\]\((data:image\/.*?;base64,.*?)\)/g,
                (match, base64Data) => `
                    <div class="chart-container-inner" style="text-align: center; margin-top: 10px;">
                        <img src="${base64Data}" style="width:100%; border-radius:10px; border:1px solid #eee;" />
                        <br>
                        <button class="download-btn" onclick="downloadChart('${base64Data}')">
                            📥 下載趨勢圖表
                        </button>
                    </div>
                `
            );

        document.getElementById(loadingId).innerHTML = formattedText;

        // 更新意圖看板
        const intentDisplay = document.getElementById('intent-display');
        if (intentDisplay) {
            intentDisplay.innerHTML = `意圖辨識：<b>${payload.intent}</b> ${payload.is_emergency ?
                "<span style='color:red;'>[緊急]</span>" : ""}`;
        }

        // 執行圖表更新
        await renderGraph(payload);

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

    // 初始 Mermaid 渲染
    if (graphContainer && window.mermaid) {
        try {
            await mermaid.run({ nodes: [graphContainer] });
        } catch (e) {
            console.warn("Initial Mermaid load pending...");
        }
    }
});