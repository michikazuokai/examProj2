// -------------------------------------------
// exam11_v2.js（A/B対応 + 補正右クリック対応 完全版）
// -------------------------------------------

// 全体状態
let exam = null;
let questions = [];
let studentAnswers = [];
let examId = null;
let studentId = null;
let currentQuestionForMenu = null;
let originalAnswers = [];  // ← 追加

// -------------------------------------------
// 共通 fetch 関数
// -------------------------------------------
async function fetchJSON(url, options = {}) {
    const res = await fetch(url, options);
    return await res.json();
}

// -------------------------------------------
// ① A/B 試験データ取得
// -------------------------------------------
async function loadExam(subjectNo, version) {
    const url = `/api/exam/?subjectNo=${subjectNo}&version=${version}`;
    exam = await fetchJSON(url);
    examId = exam.id;
    questions = exam.questions;

    // タイトル表示
    document.getElementById("examTitle").textContent =
        `${exam.subjectNo} ${exam.title}（${exam.version}版）`;
}

// -------------------------------------------
// ② StudentExam 回答データ取得
// -------------------------------------------
async function loadStudentAnswers(stuId) {
    const url = `/api/student-exam/?student=${stuId}&exam=${examId}`;
    studentAnswers = await fetchJSON(url);

    // ★ 読み込み時の元データを deep copy で保存
    originalAnswers = JSON.parse(JSON.stringify(studentAnswers));
}

// -------------------------------------------
// StudentExam を検索
// -------------------------------------------
function findAnswer(questionId) {
    return studentAnswers.find(a => a.question === questionId);
}

// -------------------------------------------
// ③ gyo × retu 画面構築
// -------------------------------------------
function renderExam() {

    const sheet = document.getElementById("answerSheet");
    sheet.innerHTML = "";

    const maxGyo = Math.max(...questions.map(q => q.gyo));

    for (let g = 1; g <= maxGyo; g++) {

        const row = questions.filter(q => q.gyo === g);
        if (row.length === 0) continue;

        const rowDiv = document.createElement("div");
        rowDiv.classList.add("answer-row");

        // 行タイトル
        const label = document.createElement("span");
        label.textContent = `行 ${g}`;
        rowDiv.appendChild(label);

        // 列順にソート
        row.sort((a, b) => a.retu - b.retu);

        row.forEach(q => {
            const boxWrapper = document.createElement("div");
            boxWrapper.style.display = "flex";
            boxWrapper.style.flexDirection = "column";
            boxWrapper.style.alignItems = "center";

            // ▼ q_no 表示（小さく）
            const qnoLabel = document.createElement("div");
            qnoLabel.textContent = q.q_no;
            qnoLabel.classList.add("qno-label");
            boxWrapper.appendChild(qnoLabel);

            // ▼ box 本体
            const box = document.createElement("div");
            box.classList.add("answer-box");
            box.dataset.qid = q.id;

            box.style.width = `${q.width * 30}px`;
            box.style.height = `${Math.ceil(q.height / 60) * 30}px`;

            // ▼ answer を box の中央に表示
            const ansText = document.createElement("div");
            ansText.textContent = q.answer;
            ansText.classList.add("answer-text");
            box.appendChild(ansText);

            // ▼ 現在の回答状態を反映
            const ans = findAnswer(q.id);
            if (ans) {
                if (ans.TF === 1) box.classList.add("checked");
                if (ans.hosei !== 0) box.classList.add("hosei");
            }

            // 左クリックで TF 切り替え
            box.addEventListener("click", () => toggleTF(q.id, box));

            // 右クリック補正メニュー
            box.addEventListener("contextmenu", (e) => {
                e.preventDefault();
                showContextMenu(e.pageX, e.pageY, q.id, box);
            });

            boxWrapper.appendChild(box);
            rowDiv.appendChild(boxWrapper);
        });


        sheet.appendChild(rowDiv);

        // 行ごとの得点表示
        const scoreLabel = document.createElement("span");
        scoreLabel.id = `row-score-${g}`;
        scoreLabel.classList.add("row-score");
        scoreLabel.textContent = "得点：0";
        rowDiv.appendChild(scoreLabel);
    }
}

// -------------------------------------------
// ④ TF 切替（PATCH 即保存）
// -------------------------------------------

async function toggleTF(questionId, box) {
    const ans = findAnswer(questionId);
    const q = questions.find(q => q.id === questionId);
    if (!ans || !q) return;

    // TF の切替
    const newTF = ans.TF === 1 ? 0 : 1;
    ans.TF = newTF;

    // --- 正解になった瞬間（newTF = 1）補正クリア ---
    if (newTF === 1) {
        ans.hosei = 0;
        box.classList.remove("hosei");
        ans.ten = q.points;
    } else {
        // 間違い → ten は補正値のみ
        ans.ten = ans.hosei;
    }

    // UI 反映
    box.classList.toggle("checked");
    updateScores();

    // 保存（待たない）
    fetch(`/api/student-exam/${ans.id}/`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ TF: newTF, hosei: ans.hosei })
    });
}

async function toggleTF_slow(questionId, box) {

    const ans = findAnswer(questionId);
    if (!ans) return;

    const newTF = ans.TF === 1 ? 0 : 1;

    const url = `/api/student-exam/${ans.id}/`;

    await fetchJSON(url, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ TF: newTF })
    });

    ans.TF = newTF;

    box.classList.toggle("checked");

    // ten 更新
    ans.ten = (ans.TF * ans.points) + ans.hosei;

    updateScores();
}

// -------------------------------------------
// ⑤ 補正メニューの表示
// -------------------------------------------
let currentQuestionId = null;

// 右クリックされたとき
function showContextMenu(x, y, questionId, box) {
    const menu = document.getElementById("context-menu");
    menu.innerHTML = "";  // メニューをクリア

    const ans = findAnswer(questionId);
    const q   = questions.find(q => q.id === questionId);

    if (!ans || !q) return;

    currentQuestionId = questionId;

    // ▼ ここで行番号を取得
    const rowNo = q.gyo;

    // ============================================================
    // ★ 行一括 正解（ON）
    // ============================================================
    const rowCorrect = document.createElement("div");
    rowCorrect.className = "menu-item";
    rowCorrect.dataset.action = "row-correct";
    rowCorrect.dataset.gyo = rowNo;
    rowCorrect.textContent = `行 ${rowNo} を全て正解にする`;
    menu.appendChild(rowCorrect);

    // ============================================================
    // ★ 行一括 未解答（OFF）
    // ============================================================
    const rowUnset = document.createElement("div");
    rowUnset.className = "menu-item";
    rowUnset.dataset.action = "row-unset";
    rowUnset.dataset.gyo = rowNo;
    rowUnset.textContent = `行 ${rowNo} を全て未解答にする`;
    menu.appendChild(rowUnset);

    // セパレータ（全体メニュー区切り）
    const sepAll = document.createElement("div");
    sepAll.className = "separator";
    menu.appendChild(sepAll);    

    // ============================================================
    // ★ 全体 一括 正解
    // ============================================================
    const allCorrect = document.createElement("div");
    allCorrect.className = "menu-item";
    allCorrect.dataset.action = "all-correct";
    allCorrect.textContent = "全問題を全て正解にする";
    menu.appendChild(allCorrect);

    // ============================================================
    // ★ 全体 一括 未解答
    // ============================================================
    const allUnset = document.createElement("div");
    allUnset.className = "menu-item";
    allUnset.dataset.action = "all-unset";
    allUnset.textContent = "全問題を全て未解答にする";
    menu.appendChild(allUnset);

    // セパレータ
    const sep = document.createElement("div");
    sep.className = "separator";
    menu.appendChild(sep);

    // ============================================================
    // ★ 正解（TF=1）のときメニューは補正禁止のみ
    // ============================================================
    if (ans.TF === 1) {
        const item = document.createElement("div");
        item.className = "menu-item";
        item.textContent = "補正できません（正解）";
        item.style.color = "gray";
        item.style.cursor = "default";
        menu.appendChild(item);

        // メニュー表示
        menu.style.left = `${x}px`;
        menu.style.top  = `${y}px`;
        menu.style.display = "block";
        return;
    }

    // ============================================================
    // ★ 補正は 1 ～ (points - 1)
    // ============================================================
    const maxHosei = Math.max(0, q.points - 1);

    for (let i = 1; i <= maxHosei; i++) {
        const item = document.createElement("div");
        item.className = "menu-item";
        item.dataset.hosei = i;
        item.textContent = `補正 +${i}`;
        menu.appendChild(item);
    }

    // リセット項目
    const reset = document.createElement("div");
    reset.className = "menu-item";
    reset.dataset.hosei = 0;
    reset.textContent = "補正リセット";
    menu.appendChild(reset);

    // メニュー表示
    menu.style.left = `${x}px`;
    menu.style.top  = `${y}px`;
    menu.style.display = "block";
}

// 補正メニューを閉じる
function hideContextMenu() {
    const menu = document.getElementById("context-menu");
    menu.style.display = "none";
}

// -------------------------------------------
// ⑥ 補正値の適用（PATCH）
// -------------------------------------------
async function applyHosei(hoseiValue) {

    const ans = findAnswer(currentQuestionId);
    if (!ans) return;

    const q = questions.find(q => q.id === ans.question);
    if (!q) return;

    const box = document.querySelector(`.answer-box[data-qid="${currentQuestionId}"]`);

    // --- 正解は補正できない ---
    if (ans.TF === 1) {
        hideContextMenu();
        return;
    }

    // --- 補正の最大値（points - 1） ---
    const maxHosei = Math.max(0, q.points - 1);
    hoseiValue = Math.min(hoseiValue, maxHosei);

    // --- 状態更新 ---
    ans.hosei = hoseiValue;
    ans.ten = ans.hosei;   // TF=0 のとき ten = hosei

    // --- ピンク反映（hosei>0 のとき） ---
    if (hoseiValue > 0) {
        box.classList.add("hosei");
    } else {
        box.classList.remove("hosei");
    }

    updateScores();

    // --- PATCH 保存（待たない） ---
    fetch(`/api/student-exam/${ans.id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hosei: ans.hosei })
    });

    hideContextMenu();
}

// -------------------------------------------
// 補正メニューのクリックイベント
// -------------------------------------------
document.addEventListener("click", (event) => {
    const menu = document.getElementById("context-menu");
    const action = event.target.dataset.action;
    const gyo = event.target.dataset.gyo;

    // メニューが出ていないなら無視
    if (menu.style.display === "none") return;

    // メニュー外をクリック → 閉じる
    if (!event.target.closest("#context-menu")) {
        hideContextMenu();
        return;
    }

    if (action === "row-correct") {
        applyRowCorrect(gyo);
        return;
    }
    if (action === "row-unset") {
        applyRowUnset(gyo);
        return;
    }

    if (action === "all-correct") {
    applyAllCorrect();
    hideContextMenu();
    return;
    }

    if (action === "all-unset") {
        applyAllUnset();
        hideContextMenu();
        return;
    }

    // メニュー項目クリック
    const hosei = Number(event.target.dataset.hosei);

    if (!isNaN(hosei)) {
        applyHosei(hosei);
        hideContextMenu();
    }
});

// -------------------------------------------
// ⑦ 合計点 / 行ごとの点数更新
// -------------------------------------------
function updateScores() {
    const rowScores = {};
    let total = 0;

    studentAnswers.forEach(a => {
        const q = questions.find(q => q.id === a.question);
        if (!q) return;

        const g = q.gyo;
        rowScores[g] = (rowScores[g] || 0) + a.ten;
        total += a.ten;
    });

    // 行ごとの得点反映
    for (let g in rowScores) {
        const elem = document.getElementById(`row-score-${g}`);
        if (elem) elem.textContent = `得点：${rowScores[g]}`;
    }

    document.getElementById("totalScore").textContent = total;
}

// -------------------------------------------
// ⑨ キャンセル（元の状態に戻す）
// -------------------------------------------
async function applyCancel() {

    if (!originalAnswers || originalAnswers.length === 0) {
        alert("元に戻すデータがありません。");
        return;
    }

    // UI 復元
    studentAnswers = JSON.parse(JSON.stringify(originalAnswers));

    // UI 再描画
    renderExam();
    updateScores();

    // ----------------------------
    //  DB を元の状態に戻す PATCH
    // ----------------------------
    for (const a of originalAnswers) {
        fetch(`/api/student-exam/${a.id}/`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                TF: a.TF,
                hosei: a.hosei
            })
        });
    }

    // 完了通知（必要なら）
    // alert("元に戻しました");
}


// -------------------------------------------
// ⑧ 初期化処理
// -------------------------------------------
async function init() {
    const params = new URLSearchParams(location.search);

    const subjectNo = params.get("subjectNo");
    const version   = params.get("version");
    const year      = params.get("year");
    const term      = params.get("term");
    studentId       = params.get("student");

    // ① 試験データ
    await loadExam(subjectNo, version);

    // ② 学生一覧ロード
    const students = await loadStudents(subjectNo, year, term);
    renderStudentDropdown(students);

    // ③ 最初に studentId が指定されていればロード
    if (studentId) {
        document.getElementById("studentSelect").value = studentId;
        await loadStudentAnswers(studentId);
    } else if (students.length > 0) {
        // デフォルトは最初の学生
        studentId = students[0].id;
        document.getElementById("studentSelect").value = studentId;
        await loadStudentAnswers(studentId);
    }

    renderExam();
    updateScores();
}

document.addEventListener("DOMContentLoaded", async () => {
    await init();

    const cancelBtn = document.getElementById("cancelButton");
    if (cancelBtn) {
        cancelBtn.addEventListener("click", () => {

            const yes = confirm("現在の学生の採点をすべて元に戻しますか？\n（DB の状態に復元されます）");

            if (!yes) return;

            applyCancel();  // ← OK のときだけ実行
        });
    }
    // 前へ
    document.getElementById("prevButton").addEventListener("click", goPrevStudent);
    // 次へ
    document.getElementById("nextButton").addEventListener("click", goNextStudent);
    // 終了
    document.getElementById("submitButton").addEventListener("click", finishExam);
});

// -------------------------------------------
// 学生一覧を取得する関数
// -------------------------------------------
async function loadStudents(subjectNo, year, term) {
    const url = `/api/students/?subjectNo=${subjectNo}&year=${year}&term=${term}`;
    return await fetchJSON(url);  
}

// -------------------------------------------
// ドロップダウンへ反映
// -------------------------------------------
function renderStudentDropdown(students) {
    const select = document.getElementById("studentSelect");

    select.innerHTML = '<option value="">選択してください</option>';

    students.forEach(stu => {
        const op = document.createElement("option");
        op.value = stu.id;
        op.textContent = `${stu.stdNo} / ${stu.nickname}`;
        select.appendChild(op);
    });

    // 学生選択時の動作
    select.addEventListener("change", async () => {
        const stuId = select.value;
        if (!stuId) return;

        studentId = stuId;
        await loadStudentAnswers(studentId);
        renderExam();
        updateScores();
    });
}

// -------------------------------------------
// 右クリック　行一括ON
// -------------------------------------------
async function applyRowCorrect(gyo) {

    // 行の全問題を取得
    const rowQuestions = questions.filter(q => q.gyo === Number(gyo));

    rowQuestions.forEach(q => {
        const ans = findAnswer(q.id);
        if (!ans) return;

        ans.TF = 1;
        ans.hosei = 0;
        ans.ten = q.points;

        // UI 更新
        const box = document.querySelector(`.answer-box[data-qid="${q.id}"]`);
        if (box) {
            box.classList.add("checked");
            box.classList.remove("hosei");
        }

        // PATCH（待たない）
        fetch(`/api/student-exam/${ans.id}/`, {
            method: "PATCH",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ TF: 1, hosei: 0 })
        });
    });

    updateScores();
    hideContextMenu();
}

// -------------------------------------------
// 右クリック　行一括OFF
// -------------------------------------------
async function applyRowUnset(gyo) {

    const rowQuestions = questions.filter(q => q.gyo === Number(gyo));

    rowQuestions.forEach(q => {
        const ans = findAnswer(q.id);
        if (!ans) return;

        ans.TF = 0;
        ans.hosei = 0;
        ans.ten = 0;

        const box = document.querySelector(`.answer-box[data-qid="${q.id}"]`);
        if (box) {
            box.classList.remove("checked");
            box.classList.remove("hosei");
        }

        // PATCH（待たない）
        fetch(`/api/student-exam/${ans.id}/`, {
            method: "PATCH",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ TF: 0, hosei: 0 })
        });
    });

    updateScores();
    hideContextMenu();
}

// -------------------------------------------
// 全体 一括 正解
// -------------------------------------------
async function applyAllCorrect() {

    studentAnswers.forEach(a => {
        const q = questions.find(q => q.id === a.question);
        if (!q) return;

        a.TF = 1;
        a.hosei = 0;
        a.ten = q.points;

        const box = document.querySelector(`.answer-box[data-qid="${a.question}"]`);
        if (box) {
            box.classList.add("checked");
            box.classList.remove("hosei");
        }

        // PATCH（待たない）
        fetch(`/api/student-exam/${a.id}/`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ TF: 1, hosei: 0 })
        });
    });

    updateScores();
    hideContextMenu();
}

// -------------------------------------------
// 全体 一括 未解答
// -------------------------------------------
async function applyAllUnset() {

    studentAnswers.forEach(a => {
        a.TF = 0;
        a.hosei = 0;
        a.ten = 0;

        const box = document.querySelector(`.answer-box[data-qid="${a.question}"]`);
        if (box) {
            box.classList.remove("checked");
            box.classList.remove("hosei");
        }

        fetch(`/api/student-exam/${a.id}/`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ TF: 0, hosei: 0 })
        });
    });

    updateScores();
    hideContextMenu();
}

function goPrevStudent() {
    const select = document.getElementById("studentSelect");
    const idx = select.selectedIndex;

    if (idx > 1) {   // 0:「選択してください」なので 1 が最初の学生
        select.selectedIndex = idx - 1;

        const newStuId = select.value;
        studentId = newStuId;
        loadStudentAnswers(studentId).then(() => {
            renderExam();
            updateScores();
        });
    }
}

function goNextStudent() {
    const select = document.getElementById("studentSelect");
    const idx = select.selectedIndex;

    if (idx < select.options.length - 1) {
        select.selectedIndex = idx + 1;

        const newStuId = select.value;
        studentId = newStuId;
        loadStudentAnswers(studentId).then(() => {
            renderExam();
            updateScores();
        });
    }
}

//------------------------------------------------------
// 終了ボタン：採点を終了して index に戻る
//------------------------------------------------------
function finishExam() {
    if (!confirm("採点を終了して一覧に戻りますか？")) {
        return;
    }

    // index.html に戻る（wexamid を保持）
    const url = "/?wexamid=" + examId;
    console.log("→ 終了: 戻りURL =", url);

    window.location.href = url;
}