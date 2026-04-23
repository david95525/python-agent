/**
 * Deep Agent 投資對比邏輯
 */

// --- 安全機制設定 ---
// 這裡從後端動態注入的 window.ENV 獲取
const getApiToken = () => (window.ENV ? window.ENV.APP_AUTH_TOKEN : 'your_token_here'); 

// 重置 UI 狀態
function resetUI() {
    document.getElementById('manualResult').innerHTML =
        '<div class="pulse-loader text-center py-20"><i class="fas fa-spinner fa-spin text-4xl mb-4"></i><p>正在按流程圖節點執行中...</p></div>';
    document.getElementById('officialResult').innerHTML =
        '<div class="pulse-loader text-center py-20"><i class="fas fa-brain fa-spin text-4xl mb-4"></i><p>正在自動規劃與推理中...</p></div>';
    document.getElementById('manualThought').innerHTML = "";
    document.getElementById('officialThought').innerHTML = "";
    document.getElementById('manualStatus').innerText = "執行中...";
    document.getElementById('officialStatus').innerText = "規劃中...";
}

// 執行實驗 (主進入點)
async function runExperiment() {
    const symbolInput = document.getElementById('symbolInput');
    const symbol = symbolInput.value.trim();

    if (!symbol) {
        alert("請輸入標的代號");
        return;
    }

    resetUI();

    // 並行執行兩個模式
    fetchManual(symbol);
    fetchOfficial(symbol);
}

// --- 手動 LangGraph 模式 ---
async function fetchManual(symbol) {
    const status = document.getElementById('manualStatus');
    const thought = document.getElementById('manualThought');
    const resultArea = document.getElementById('manualResult');

    thought.innerHTML += "> [START] 進入 Router 節點\n";
    thought.innerHTML += "> [NODE] 啟動市場研究節點 (yfinance)... \n";

    try {
        const response = await fetch('/api/v1/deep-research/invest/manual', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-API-Key': getApiToken()
            },
            body: JSON.stringify({ symbol: symbol })
        });

        const jsonResponse = await response.json();
        const resData = jsonResponse.data;

        if (resData) {
            thought.innerHTML += "> [NODE] 風險評估完成\n";
            thought.innerHTML += "> [END] 產出報告\n";
            status.innerText = "完成";

            const rawDataHtml = `<div class='bg-gray-900 p-4 rounded mb-4 text-xs font-mono text-blue-300 overflow-x-auto'>${resData.data_raw}</div>`;
            const reportHtml = `<div class='prose prose-invert max-w-none'>${resData.final_response.replace(/\n/g, '<br>')}</div>`;

            resultArea.innerHTML = rawDataHtml + reportHtml;
        } else {
            throw new Error("後端回傳格式不符合預期");
        }
    } catch (e) {
        status.innerText = "出錯";
        resultArea.innerHTML = `<span class="text-red-400">系統錯誤: ${e.message}</span>`;
    }
}

// --- 官方自主代理模式 ---
async function fetchOfficial(symbol) {
    const status = document.getElementById('officialStatus');
    const thought = document.getElementById('officialThought');
    const resultArea = document.getElementById('officialResult');

    thought.innerHTML += "> [PLANNING] 正在啟動官方自主代理 (DeepAgents)...\n";

    try {
        const response = await fetch('/api/v1/deep-research/invest/official', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-API-Key': getApiToken()
            },
            body: JSON.stringify({ symbol: symbol })
        });

        if (!response.ok) throw new Error(`HTTP 錯誤! 狀態碼: ${response.status}`);

        const jsonResponse = await response.json();
        let content = "";
        const finalResponse = jsonResponse?.result?.final_response;

        if (Array.isArray(finalResponse) && finalResponse.length > 0 && finalResponse[0].text) {
            content = finalResponse[0].text;
            if (content.trim().length < 5) content = "⚠️ AI 回傳內容過於簡短，可能因數據源受限。";
        } else if (jsonResponse?.error) {
            content = `❌ 系統錯誤: ${jsonResponse.error}`;
        } else {
            content = "⚠️ 官方代理未回傳具體分析。";
        }

        thought.innerHTML += "> [SUB-AGENT] 任務完成\n";
        status.innerText = content.includes("⚠️") || content.includes("❌") ? "異常" : "完成";

        resultArea.innerHTML = content
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    } catch (e) {
        status.innerText = "網路錯誤";
        resultArea.innerHTML = `<span class="text-red-400">無法連線: ${e.message}</span>`;
    }
}

/**
 * 綁定事件監聽器
 */
document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('startBtn');
    const symbolInput = document.getElementById('symbolInput');

    // 獲獲取並顯示 Provider 資訊
    async function fetchConfig() {
        try {
            const response = await fetch('/api/v1/config', {
                headers: { 'X-API-Key': getApiToken() }
            });
            const config = await response.json();
            const providerEl = document.getElementById('provider-info');
            if (providerEl) {
                providerEl.innerText = `${config.llm_provider.toUpperCase()} (${config.model_id})`;
            }
        } catch (err) {
            console.error("Failed to fetch config:", err);
        }
    }
    fetchConfig();

    // 監聽點擊「開始深度分析」按鈕
    if (startBtn) {
        startBtn.addEventListener('click', () => {
            console.log("🚀 [DeepAgent] 啟動深度實驗...");
            runExperiment();
        });
    }

    // 監聽鍵盤「Enter」鍵
    if (symbolInput) {
        symbolInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                runExperiment();
            }
        });
    }
});