// index_page.js
let GLOBAL_FSYEAR = null;
let GLOBAL_TERM = null;

console.log("index_page.js loaded");

// ---------------- 環境情報の取得 ----------------
async function initEnvironment() {
    const res = await fetch("/api/environment/");
    const data = await res.json();

    GLOBAL_FSYEAR = data.fsyear;   // settings から返す年度
    GLOBAL_TERM  = data.term ?? 2; // settings から返す期（なければ 2）

    document.getElementById("current-year").textContent = GLOBAL_FSYEAR;
    document.getElementById("current-term").textContent = GLOBAL_TERM;
}

// 共通 fetch
async function fetchJSON(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`);
    return await res.json();
}

// ---------------- ページ初期化 ----------------
document.addEventListener("DOMContentLoaded", async () => {

    // 1. 年度・期設定
    await initEnvironment();

    // 2. 科目ドロップダウン設定（完了を await）
    await loadSubjects();

    // 3. URL パラメータ復元処理（★順番が最重要）
    await restoreFromURL();

    // 4. イベント登録
    setupEvents();
});

// ---------------- URL から状態復元（最重要） ----------------
async function restoreFromURL() {

    const params = new URLSearchParams(location.search);
    const subjectNo = params.get("subjectNo");
    const fsyear    = params.get("fsyear");
    const term      = params.get("term");

    if (fsyear) GLOBAL_FSYEAR = fsyear;
    if (term) GLOBAL_TERM = term;

    if (!subjectNo) return;  // URL に subject が無ければ何もしない

    // 科目一覧がロードされている前提で値をセット
    const sel = document.getElementById("subject-dropdown");
    sel.value = subjectNo;

    // 学生一覧を表示
    await loadStudentList(subjectNo);
}

// ---------------- 科目一覧読み込み ----------------
async function loadSubjects() {
    const data = await fetchJSON("/api/subjects/");
    const sel = document.getElementById("subject-dropdown");

    sel.innerHTML = `<option value="">科目を選択してください</option>`;

    data.forEach(sub => {
        const op = document.createElement("option");
        op.value = sub.subjectNo;
        op.textContent = `${sub.subjectNo} ${sub.name}`;
        sel.appendChild(op);
    });
}


// ---------------- 試験情報（A/B 両方の hash）表示 ----------------
function renderExamInfo(exams) {
    const info = document.getElementById("exam-info");
    if (!info) return;

    // exams が無い/空なら表示しない
    if (!exams || typeof exams !== "object") {
        info.textContent = "";
        return;
    }

    // A,B,C... の順に並べたい（存在するものだけ）
    const order = ["A", "B", "C", "D"];
    const versions = Object.keys(exams).sort((a, b) => {
        const ia = order.indexOf(a);
        const ib = order.indexOf(b);
        if (ia === -1 && ib === -1) return a.localeCompare(b);
        if (ia === -1) return 1;
        if (ib === -1) return -1;
        return ia - ib;
    });

    // hash を集める（null/空は除外）
    const hashes = [];
    const fullHashes = [];
    for (const v of versions) {
        const h = exams[v]?.problem_hash;
        if (!h) continue;
        fullHashes.push(h);
        hashes.push(h.slice(0, 7));
    }

    // 何も無いなら消す
    if (hashes.length === 0) {
        info.textContent = "";
        info.removeAttribute("title");
        return;
    }

    // 同じhashが複数版で出ても 1個だけ表示（任意：安全）
    const uniq = [...new Set(hashes)];

    // ★ 表示：A版/B版の文字は一切出さない
    info.textContent = uniq.map(x => `[${x}]`).join(" ");

    // フルhashは hover で見えるように
    info.title = [...new Set(fullHashes)].join("\n");
}


// ---------------- 学生一覧の読み込み（A/B 混在版） ----------------
async function loadStudentList(subjectNo) {

    const data = await fetchJSON(
        `/api/examadjust_subject/?subjectNo=${subjectNo}&fsyear=${GLOBAL_FSYEAR}`
    );


    // 返ってきた term を表示に反映（settings.TERM依存を薄める）
    if (data.term != null) {
        GLOBAL_TERM = data.term;
        document.getElementById("current-term").textContent = data.term;
    }
        
    // ★ 追加：科目に対応する exam 情報を表示
    renderExamInfo(data.exams);

    const tbody = document.getElementById("students-table-body");
    tbody.innerHTML = "";

    data.students.forEach(stu => {
        const tr = document.createElement("tr");

        tr.innerHTML = `
            <td>${stu.stdNo}</td>
            <td>${stu.nickname}</td>
            <td>${stu.version}</td>
            <td>${stu.score}</td>
            <td>${stu.hosei}</td>
            <td>${stu.adjust}</td>
            <td>${stu.total}</td>
        `;

        tr.addEventListener("dblclick", (ev) => {

            if (ev.shiftKey) {
                // 調整画面へ
                const url = `/examadjust/?subjectNo=${subjectNo}&fsyear=${GLOBAL_FSYEAR}`;
                console.log("Shift + dblclick → Adjust:", url);
                location.href = url;
                return;
            }

            // 採点画面へ
            const url = `/exam/?exam_id=${stu.exam_id}&stdNo=${stu.stdNo}&subjectNo=${subjectNo}&fsyear=${GLOBAL_FSYEAR}`;
            console.log("dblclick → Grading:", url);
            location.href = url;
        });

        tbody.appendChild(tr);
    });
}

// ---------------- イベント ----------------
function setupEvents() {
    document.getElementById("subject-dropdown").addEventListener("change", ev => {
        const subjectNo = ev.target.value;
        if (!subjectNo) return;

        const newUrl = `/?subjectNo=${subjectNo}&fsyear=${GLOBAL_FSYEAR}`;
        history.pushState({}, "", newUrl);

        loadStudentList(subjectNo);
    });

    document.getElementById("download-csv").addEventListener("click", downloadCSV);
}

// ----------------- CSV -----------------
function downloadCSV() {
    const table = document.querySelector("table");
    if (!table) return;

    let csv = "data:text/csv;charset=utf-8,";

    table.querySelectorAll("tr").forEach(row => {
        csv += [...row.children].map(td => td.textContent.trim()).join(",") + "\n";
    });

    const link = document.createElement("a");
    link.href = encodeURI(csv);
    link.download = "exam_results.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
}