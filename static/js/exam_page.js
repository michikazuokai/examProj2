// exam_page.js（新 StudentExam API 対応版）★最小修正版

let exam = null;
let questions = [];
let studentAnswers = [];
let students = [];
let examId = null;
let currentStdNo = null;
let currentStudentIndex = 0;

let currentQuestionId = null;
let originalAnswers = null;

// ★ 追加：一括処理中ロック
let isBusy = false;

// 共通 fetch
async function fetchJSON(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
        console.error("fetch error:", url, res.status);
    }
    return await res.json();
}

// ★ 追加：UIロック（最小）
function setBusy(flag) {
    isBusy = flag;

    // ボタン系（存在するものだけ）
    const ids = ["cancelButton", "prevButton", "nextButton", "submitButton", "studentSelect"];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.disabled = flag;
    });

    // 見た目（任意：CSSがなければ影響なし）
    const sheet = document.getElementById("answerSheet");
    if (sheet) sheet.style.pointerEvents = flag ? "none" : "auto";
}

// ----------------- 初期化 -----------------
async function initExamPage() {
    console.log("initExamPage start");

    const params = new URLSearchParams(location.search);
    examId = params.get("exam_id");
    currentStdNo = params.get("stdNo");

    if (!examId) {
        alert("exam_id が指定されていません。index から入り直してください。");
        return;
    }
    console.log("fetch:", `/api/exams/${examId}/`);

    // ① Exam と Question
    exam = await fetchJSON(`/api/exams/${examId}/`);
    questions = exam.questions || [];

    // console.log(questions);
    
    document.getElementById("examTitle").textContent =
        `${exam.subjectNo} ${exam.title}（${exam.version}版）`;

    // ② 学生一覧
    students = await fetchJSON(`/api/exam-students/?exam_id=${examId}`);
    renderStudentDropdown();

    // 初期学生の決定
    if (!currentStdNo && students.length > 0) {
        currentStdNo = students[0].stdNo;
    }
    currentStudentIndex = students.findIndex(s => s.stdNo === currentStdNo);
    if (currentStudentIndex < 0 && students.length > 0) currentStudentIndex = 0;
    if (students[currentStudentIndex]) {
        currentStdNo = students[currentStudentIndex].stdNo;
        document.getElementById("studentSelect").value = currentStdNo;
    }

    // ③ StudentExam 読み込み
    await loadStudentAnswers();
    renderExam();
    updateScores();
}

// ----------------- 学生一覧 UI -----------------
function renderStudentDropdown() {
    const sel = document.getElementById("studentSelect");
    sel.innerHTML = "";

    students.forEach(stu => {
        const op = document.createElement("option");
        op.value = stu.stdNo;
        op.textContent = `${stu.stdNo} / ${stu.nickname}`;
        sel.appendChild(op);
    });

    sel.addEventListener("change", async () => {
        if (isBusy) return; // ★ 追加
        currentStdNo = sel.value;
        currentStudentIndex = students.findIndex(s => s.stdNo === currentStdNo);
        await loadStudentAnswers();
        renderExam();
        updateScores();
    });
}

// ----------------- StudentExam 読み込み -----------------
async function loadStudentAnswers() {
    if (!currentStdNo) return;

    studentAnswers = await fetchJSON(
        `/api/student-exams/?exam=${examId}&student_stdno=${currentStdNo}`
    );

    // Deep copy を保持（キャンセル用）
    originalAnswers = JSON.parse(JSON.stringify(studentAnswers));
    // console.log("--->",originalAnswers)

    const stu = students[currentStudentIndex];
    if (stu) {
        document.getElementById("studentInfo").textContent =
            ` [${stu.stdNo}] ${stu.nickname}`;
    }
    document.getElementById("cancelStatus").textContent = "なし";
}

// Helper: question → points, gyo, retu 取得
function findQuestion(qid) {
    return questions.find(q => q.id === qid);
}

// Helper: StudentExam の 1件取得
function findAnswer(qid) {
    return studentAnswers.find(a => a.question === qid);
}

// ----------------- 画面描画 -----------------
function renderExam() {

    console.log("=== renderExam called ===");
    // console.log("questions =", questions);

    const sheet = document.getElementById("answerSheet");
    console.log("sheet =", sheet);

    sheet.innerHTML = "";

    if (!questions.length) return;

    const maxGyo = Math.max(...questions.map(q => q.gyo || 1));

    for (let g = 1; g <= maxGyo; g++) {
        const rowQs = questions.filter(q => q.gyo === g);
        if (!rowQs.length) continue;

        rowQs.sort((a, b) => a.retu - b.retu);

        const rowDiv = document.createElement("div");
        rowDiv.classList.add("answer-row");

        const label = document.createElement("span");
        label.textContent = `行 ${g}`;
        rowDiv.appendChild(label);

        rowQs.forEach(q => {
            const wrapper = document.createElement("div");
            wrapper.style.display = "flex";
            wrapper.style.flexDirection = "column";
            wrapper.style.alignItems = "center";

            const qnoLabel = document.createElement("div");
            qnoLabel.textContent = q.q_no;   // ここを問題番号として使う
            qnoLabel.classList.add("qno-label");
            wrapper.appendChild(qnoLabel);

            const box = document.createElement("div");
            box.classList.add("answer-box");
            box.dataset.qid = q.id;

            // ★ 基本サイズを config から取得
            const BW = window.EXAM_CONFIG.BASE_WIDTH;
            const BH = window.EXAM_CONFIG.BASE_HEIGHT;

            // テーブル上の倍率（width, height）
            const w = q.width ?? 1;   // 幅方向の倍率
            const h = q.height ?? 1;  // 高さ方向の倍率

            // ★ box のサイズを決定
            box.style.width  = `${BW * w}px`;
            box.style.height = `${BH * h}px`;

            // ★ 正解テキスト要素を作成
            const ansText = document.createElement("div");
            ansText.textContent = q.answer;
            ansText.classList.add("answer-text");
            box.appendChild(ansText);

            // ★ フォントサイズを固定値で設定（config.js から取得）
            if (window.EXAM_CONFIG.FONT_SIZE) {
                ansText.style.fontSize = `${window.EXAM_CONFIG.FONT_SIZE}px`;
            }

            const ans = findAnswer(q.id);
            if (ans) {
                if (ans.TF === 1) box.classList.add("checked");
                if ((ans.hosei || 0) !== 0) box.classList.add("hosei");
            }

            box.addEventListener("click", () => {
                if (isBusy) return; // ★ 追加
                toggleTF(q.id, box);
            });

            box.addEventListener("contextmenu", (e) => {
                if (isBusy) return; // ★ 追加
                e.preventDefault();
                showContextMenu(e.pageX, e.pageY, q.id);
            });

            wrapper.appendChild(box);
            rowDiv.appendChild(wrapper);
        });

        const scoreLabel = document.createElement("span");
        scoreLabel.id = `row-score-${g}`;
        scoreLabel.classList.add("row-score");
        scoreLabel.textContent = "得点: 0";
        rowDiv.appendChild(scoreLabel);

        sheet.appendChild(rowDiv);
    }
    console.log("=== renderExam finished ===");
    // console.log("sheet HTML =", sheet.innerHTML);
}

// ----------------- TF 切替 -----------------
async function toggleTF(qid, box) {
    const ans = findAnswer(qid);
    const q = findQuestion(qid);
    if (!ans || !q) return;

    const newTF = ans.TF === 1 ? 0 : 1;
    ans.TF = newTF;

    if (newTF === 1) {
        // 正解 → 補正クリア
        ans.hosei = 0;
        box.classList.remove("hosei");
    }

    box.classList.toggle("checked");
    updateScores();

    // サーバ保存
    await fetch(`/api/student-exams/${ans.id}/`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ TF: ans.TF, hosei: ans.hosei }),
    });
}

// ----------------- 右クリックメニュー -----------------

function showContextMenu(x, y, qid) {
    const menu = document.getElementById("context-menu");
    menu.innerHTML = "";

    const ans = findAnswer(qid);
    const q = findQuestion(qid);
    if (!ans || !q) return;

    currentQuestionId = qid;

    const rowNo = q.gyo;

    // 行一括 ON
    const rowOn = document.createElement("div");
    rowOn.className = "menu-item";
    rowOn.dataset.action = "row-on";
    rowOn.dataset.gyo = rowNo;
    rowOn.textContent = `行 ${rowNo} を全て正解`;
    menu.appendChild(rowOn);

    // 行一括 OFF
    const rowOff = document.createElement("div");
    rowOff.className = "menu-item";
    rowOff.dataset.action = "row-off";
    rowOff.dataset.gyo = rowNo;
    rowOff.textContent = `行 ${rowNo} を全て未解答`;
    menu.appendChild(rowOff);

    const sep = document.createElement("div");
    sep.className = "separator";
    menu.appendChild(sep);

    if (ans.TF === 1) {
        const item = document.createElement("div");
        item.className = "menu-item";
        item.textContent = "補正できません（正解）";
        item.style.color = "gray";
        item.style.cursor = "default";
        menu.appendChild(item);
    } else {
        const maxHosei = Math.max(0, q.points - 1);
        for (let i = 1; i <= maxHosei; i++) {
            const item = document.createElement("div");
            item.className = "menu-item";
            item.dataset.hosei = i;
            item.textContent = `補正 +${i}`;
            menu.appendChild(item);
        }

        const reset = document.createElement("div");
        reset.className = "menu-item";
        reset.dataset.hosei = 0;
        reset.textContent = "補正リセット";
        menu.appendChild(reset);
    }

    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;
    menu.style.display = "block";
}

function hideContextMenu() {
    const menu = document.getElementById("context-menu");
    menu.style.display = "none";
}

// クリック処理
document.addEventListener("click", async (e) => {
    const menu = document.getElementById("context-menu");
    if (menu.style.display === "none") return;

    if (!e.target.closest("#context-menu")) {
        hideContextMenu();
        return;
    }

    const action = e.target.dataset.action;
    const gyo = e.target.dataset.gyo;

    if (action === "row-on") {
        await applyRowTF(gyo, 1); // 行一括 ON
        hideContextMenu();
        return;
    }
    if (action === "row-off") {
        await applyRowTF(gyo, 0); // 行一括 OFF
        hideContextMenu();
        return;
    }

    const hosei = Number(e.target.dataset.hosei);
    if (!isNaN(hosei)) {
        await applyHosei(hosei);
        hideContextMenu();
    }
});

// 補正値適用
async function applyHosei(hoseiValue) {
    if (isBusy) return; // ★ 追加
    const ans = findAnswer(currentQuestionId);
    const q = findQuestion(currentQuestionId);
    if (!ans || !q) return;

    if (ans.TF === 1) return;

    const maxHosei = Math.max(0, q.points - 1);
    hoseiValue = Math.min(hoseiValue, maxHosei);

    ans.hosei = hoseiValue;

    const box = document.querySelector(`.answer-box[data-qid="${currentQuestionId}"]`);
    if (hoseiValue > 0) box.classList.add("hosei");
    else box.classList.remove("hosei");

    updateScores();

    await fetch(`/api/student-exams/${ans.id}/`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ hosei: ans.hosei }),
    });
}

//  *** 統合版：applyRowTF（完成形）  ***
async function applyRowTF(gyo, tfValue) {
    if (isBusy) return;
    setBusy(true);

    try {
        const g = Number(gyo);
        const rowQs = questions.filter(q => q.gyo === g);

        const payload = [];

        for (const q of rowQs) {
            const ans = findAnswer(q.id);
            if (!ans) continue;

            // 状態更新
            ans.TF = tfValue;
            ans.hosei = 0;

            // UI 即時反映
            const box = document.querySelector(
                `.answer-box[data-qid="${q.id}"]`
            );
            if (box) {
                box.classList.toggle("checked", tfValue === 1);
                box.classList.remove("hosei");
            }

            // bulk 用
            payload.push({
                id: ans.id,
                TF: tfValue,
                hosei: 0
            });
        }

        updateScores();

        // DB 更新（1回）
        if (payload.length > 0) {
            await fetch("/api/student-exams/bulk_update/", {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        }

    } finally {
        setBusy(false);
    }
}

// 行一括 ON
async function applyRowCorrect(gyo) {
    if (isBusy) return;         // ★ 追加
    setBusy(true);              // ★ 追加

    const g = Number(gyo);
    const rowQs = questions.filter(q => q.gyo === g);

    const reqs = []; // ★ 追加：全fetchを集める
    for (const q of rowQs) {
        const ans = findAnswer(q.id);
        if (!ans) continue;

        ans.TF = 1;
        ans.hosei = 0;

        const box = document.querySelector(`.answer-box[data-qid="${q.id}"]`);
        if (box) {
            box.classList.add("checked");
            box.classList.remove("hosei");
        }

        // ★ ここは元の設計（1件ずつPATCH）は維持
        reqs.push(fetch(`/api/student-exams/${ans.id}/`, {
            method: "PATCH",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ TF: 1, hosei: 0 }),
        }));
    }

    updateScores();

    // ★ 追加：全部終わるまで待って解除（不整合防止）
    await Promise.all(reqs);

    setBusy(false); // ★ 追加
}

// 行一括 OFF
async function applyRowUnset(gyo) {
    if (isBusy) return;         // ★ 追加
    setBusy(true);              // ★ 追加

    const g = Number(gyo);
    const rowQs = questions.filter(q => q.gyo === g);

    const reqs = []; // ★ 追加
    for (const q of rowQs) {
        const ans = findAnswer(q.id);
        if (!ans) continue;

        ans.TF = 0;
        ans.hosei = 0;

        const box = document.querySelector(`.answer-box[data-qid="${q.id}"]`);
        if (box) {
            box.classList.remove("checked");
            box.classList.remove("hosei");
        }

        reqs.push(fetch(`/api/student-exams/${ans.id}/`, {
            method: "PATCH",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ TF: 0, hosei: 0 }),
        }));
    }

    updateScores();

    await Promise.all(reqs);

    setBusy(false); // ★ 追加
}

// ----------------- スコア計算 -----------------
function updateScores() {
    const rowScores = {};
    let total = 0;

    studentAnswers.forEach(a => {
        const q = findQuestion(a.question);
        if (!q) return;

        const base = a.TF === 1 ? q.points : 0;
        const corr = a.hosei || 0;
        const ten = base + corr;

        const g = q.gyo;
        rowScores[g] = (rowScores[g] || 0) + ten;
        total += ten;
    });

    Object.keys(rowScores).forEach(g => {
        const elem = document.getElementById(`row-score-${g}`);
        if (elem) elem.textContent = `得点: ${rowScores[g]}`;
    });

    document.getElementById("totalScore").textContent = total;
}

// ----------------- キャンセル -----------------
async function applyCancel() {
    if (isBusy) return; // ★ 追加

    const ok = confirm("現在の学生の採点をすべて元に戻しますか？（DB にも反映されます）");
    if (!ok) return;

    if (!originalAnswers) {
        alert("元データがありません。");
        return;
    }

    setBusy(true); // ★ 追加（キャンセル中もロック）

    // 1) 画面上のデータを元に戻す
    studentAnswers = JSON.parse(JSON.stringify(originalAnswers));

    // 2) DB に書き戻す payload
    const payload = studentAnswers.map(ans => ({
        id: ans.id,
        TF: ans.TF,
        hosei: ans.hosei
    }));

    // 3) DB 更新
    const res = await fetch("/api/student-exams/bulk_update/", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });

    if (!res.ok) {
        console.error("キャンセル DBエラー:", await res.text());
        alert("キャンセルの反映に失敗しました（DB エラー）");
        setBusy(false);
        return;
    }

    // 4) UI 再描画
    renderExam();

    // ★ バグ修正：updateTotalScore() は存在しない → updateScores()
    updateScores();

    document.getElementById("cancelStatus").textContent = "なし";

    setBusy(false);
}

// ----------------- 前 / 次 / 終了 -----------------
function goPrevStudent() {
    if (isBusy) return; // ★ 追加
    if (!students.length) return;
    currentStudentIndex = (currentStudentIndex - 1 + students.length) % students.length;
    currentStdNo = students[currentStudentIndex].stdNo;
    document.getElementById("studentSelect").value = currentStdNo;
    loadStudentAnswers().then(() => {
        renderExam();
        updateScores();
    });
}

function goNextStudent() {
    if (isBusy) return; // ★ 追加
    if (!students.length) return;
    currentStudentIndex = (currentStudentIndex + 1) % students.length;
    currentStdNo = students[currentStudentIndex].stdNo;
    document.getElementById("studentSelect").value = currentStdNo;
    loadStudentAnswers().then(() => {
        renderExam();
        updateScores();
    });
}

function finishExam() {
    if (isBusy) return; // ★ 追加
    const params = new URLSearchParams(location.search);
    const subjectNo = params.get("subjectNo");
    const fsyear = params.get("fsyear");
    const term = params.get("term");

    // すぐ戻る
    location.href = `/?subjectNo=${subjectNo}&fsyear=${fsyear}&term=${term}`;
}

// ----------------- DOMContentLoaded -----------------
document.addEventListener("DOMContentLoaded", async () => {
    await initExamPage();

    const cancelBtn = document.getElementById("cancelButton");
    if (cancelBtn) {
        cancelBtn.addEventListener("click", applyCancel);
    }
    document.getElementById("prevButton").addEventListener("click", goPrevStudent);
    document.getElementById("nextButton").addEventListener("click", goNextStudent);
    document.getElementById("submitButton").addEventListener("click", finishExam);
});