/**
 * Medical Agent QA Dashboard - Advanced Logic
 * 支援載入 YAML 劇本與手動編輯即時測試
 */

// --- 安全機制設定 ---
// 這裡從後端動態注入的 window.ENV 獲取
const getApiToken = () => (window.ENV ? window.ENV.APP_AUTH_TOKEN : 'your_token_here'); 

let currentScenario = { name: "", steps: [] };
let lastReport = null;

// 初始化
window.onload = async () => {
    lucide.createIcons();
    await fetchScenarios();
    addStep(); // 預設給一個空白步驟

    // 事件綁定
    document.getElementById('addStepBtn').onclick = () => addStep();
    document.getElementById('clearEditorBtn').onclick = clearEditor;
    document.getElementById('customName').oninput = (e) => currentScenario.name = e.target.value;
    document.getElementById('runBtn').onclick = runTest;
    document.getElementById('copyConsoleBtn').onclick = copyConsole;
};

// 取得 YAML 劇本清單
async function fetchScenarios() {
    const listContainer = document.getElementById('scenarioList');
    try {
        const response = await fetch('/api/test/scenarios', {
            headers: { 'X-API-Key': getApiToken() }
        });
        const scenarios = await response.json();
        listContainer.innerHTML = '';
        scenarios.forEach(s => {
            const item = document.createElement('div');
            item.className = "p-3 border rounded cursor-pointer hover:bg-blue-50 border-gray-100 text-sm transition-all";
            item.innerHTML = `<div class="font-medium text-gray-700">${s.name}</div><div class="text-[10px] text-gray-400">${s.steps.length} steps</div>`;
            item.onclick = () => loadToEditor(s);
            listContainer.appendChild(item);
        });
    } catch (err) {
        listContainer.innerHTML = '<div class="text-xs text-red-400">無法連線後端</div>';
    }
}

// 將劇本載入編輯器
function loadToEditor(scenario) {
    clearEditor();
    document.getElementById('customName').value = scenario.name;
    currentScenario.name = scenario.name;
    scenario.steps.forEach(step => {
        addStep(step.user_input, step.expected_intent, step.expect_emergency, step.expect_contains?.join(','));
    });
    checkRunButton();
}

// 新增步驟 UI
function addStep(input = "", intent = "", emergency = false, keywords = "") {
    const container = document.getElementById('stepsContainer');
    const stepIdx = container.children.length;
    const div = document.createElement('div');
    div.className = "bg-gray-50 p-3 rounded-lg border border-gray-100 relative group";
    div.innerHTML = `
        <button class="absolute -right-2 -top-2 bg-red-100 text-red-500 rounded-full p-1 opacity-0 group-hover:opacity-100 transition-all" onclick="this.parentElement.remove(); checkRunButton();">
            <i data-lucide="x" class="w-3 h-3"></i>
        </button>
        <div class="space-y-2">
            <input type="text" placeholder="使用者說..." value="${input}" class="step-input w-full bg-white border border-gray-200 rounded p-2 text-xs outline-none focus:border-blue-400" oninput="checkRunButton()">
            <div class="grid grid-cols-2 gap-2">
                <select class="step-intent bg-white border border-gray-200 rounded p-1 text-[10px] outline-none">
                    <option value="">-- 預期意圖 --</option>
                    <option value="health_analyst" ${intent === 'health_analyst' ? 'selected' : ''}>健康分析</option>
                    <option value="visualizer" ${intent === 'visualizer' ? 'selected' : ''}>視覺化</option>
                    <option value="general" ${intent === 'general' ? 'selected' : ''}>一般對話</option>
                </select>
                <input type="text" placeholder="預期關鍵字(逗點隔開)" value="${keywords}" class="step-keywords bg-white border border-gray-200 rounded p-1 text-[10px] outline-none">
            </div>
            <label class="flex items-center text-[10px] text-gray-500">
                <input type="checkbox" class="step-emergency mr-1" ${emergency ? 'checked' : ''}> 預期觸發緊急標記
            </label>
        </div>
    `;
    container.appendChild(div);
    lucide.createIcons();
    checkRunButton();
}

function clearEditor() {
    document.getElementById('stepsContainer').innerHTML = '';
    document.getElementById('customName').value = '';
    currentScenario = { name: "", steps: [] };
    checkRunButton();
}

function checkRunButton() {
    const inputs = document.querySelectorAll('.step-input');
    const name = document.getElementById('customName').value;
    document.getElementById('runBtn').disabled = (inputs.length === 0 || !name);
}

// 收集編輯器內容並執行
async function runTest() {
    const name = document.getElementById('customName').value;
    const stepElems = document.getElementById('stepsContainer').children;
    const steps = [];

    for (let el of stepElems) {
        steps.push({
            user_input: el.querySelector('.step-input').value,
            expected_intent: el.querySelector('.step-intent').value || undefined,
            expect_emergency: el.querySelector('.step-emergency').checked,
            expect_contains: el.querySelector('.step-keywords').value.split(',').map(s => s.trim()).filter(s => s)
        });
    }

    const payload = { name, steps };

    // UI 鎖定
    const btn = document.getElementById('runBtn');
    const console = document.getElementById('testConsole');
    const status = document.getElementById('overallStatus');

    btn.disabled = true;
    console.innerHTML = '<div class="text-blue-400 italic">// 測試引擎啟動中，請稍候...</div>';
    status.innerText = "RUNNING";
    status.className = "px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500 text-white animate-pulse";

    try {
        const response = await fetch('/api/test/run-test', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-API-Key': getApiToken()
            },
            body: JSON.stringify(payload)
        });
        const report = await response.json();
        lastReport = report;
        renderReport(report);
    } catch (err) {
        log(`API 呼叫失敗: ${err.message}`, 'red');
    } finally {
        btn.disabled = false;
        document.getElementById('downloadReportBtn').disabled = false;
    }
}

function renderReport(report) {
    const console = document.getElementById('testConsole');
    const status = document.getElementById('overallStatus');
    console.innerHTML = '';

    if (!report || !report.steps) {
        log("錯誤：收到的報告格式不正確", 'red');
        return;
    }

    report.steps.forEach((s, i) => {
        log(`[Step ${i + 1}] Input: ${s.input}`, 'white');

        if (s.errors && s.errors.length === 0) {
            log(`  Result: PASS (Intent: ${s.actual_intent || 'N/A'})`, 'green');
        } else {
            const errs = s.errors || ["未知錯誤"];
            errs.forEach(e => log(`  Result: FAIL - ${e}`, 'red'));
        }

        // 關鍵防禦：確保 actual_response 存在才呼叫 substring
        const safeResp = s.actual_response || "（無回覆內容）";
        log(`  Response: "${safeResp}"`, 'gray');
        log('--------------------------------------', 'gray');
    });

    const isPass = report.status === "PASS";
    status.innerText = isPass ? "PASSED" : "FAILED";
    status.className = isPass ? "px-2 py-0.5 rounded text-[10px] font-bold bg-green-500 text-white" : "px-2 py-0.5 rounded text-[10px] font-bold bg-red-500 text-white";
    log(`測試完畢: ${isPass ? '成功' : '失敗'}`, isPass ? 'green' : 'red');
}

function log(msg, type) {
    const console = document.getElementById('testConsole');
    const colors = { green: 'text-green-400', red: 'text-red-400', white: 'text-gray-100', gray: 'text-gray-500' };
    console.innerHTML += `<div class="${colors[type] || 'text-white'}">> ${msg}</div>`;
    console.scrollTop = console.scrollHeight;
}

function copyConsole() {
    const text = document.getElementById('testConsole').innerText;
    const el = document.createElement('textarea');
    el.value = text;
    document.body.appendChild(el);
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
    alert('已複製日誌');
}