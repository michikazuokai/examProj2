// examadjust_page.js  --- ★ 完全版 ★

let students = [];
let globalComment = "";

// ------------------------
// 起動
// ------------------------
document.addEventListener("DOMContentLoaded", async () => {
    await initEnvironment();
    await initAdjustPage();
});

// ------------------------
// 環境表示
// ------------------------
async function initEnvironment() {
    const res = await fetch("/api/environment/");
    const data = await res.json();

    const envSpan = document.getElementById("exam-env");
    if (!envSpan) return;

    if (data.environment === "テスト") envSpan.textContent = " (テスト)";
    if (data.environment === "本番") envSpan.textContent = " (本番)";
}

// ------------------------
// URL パラメータ取得
// ------------------------
function getParams() {
    const p = new URLSearchParams(location.search);
    return {
        subjectNo: p.get("subjectNo"),
        fsyear: p.get("fsyear"),
        term: p.get("term"),
    };
}

// ------------------------
// 調整画面 初期化
// ------------------------
async function initAdjustPage() {

    const { subjectNo, fsyear, term } = getParams();

    if (!subjectNo || !fsyear || !term) {
        alert("subjectNo / fsyear / term がありません");
        return;
    }

    // -------------------------
    // ★ 科目全体の A/B 学生一覧
    // -------------------------
    const data = await fetchJSON(
        `/api/examadjust_subject/?subjectNo=${subjectNo}&fsyear=${fsyear}&term=${term}`
    );

    renderExamInfo(data.exams);

    // 見出し表示
    document.getElementById("exam-year").textContent = fsyear;
    document.getElementById("exam-name").textContent = `${subjectNo}（${term}期）`;

    // local 状態構築
    students = data.students.map(stu => ({
        ...stu,
        originalAdjust: stu.adjust,
    }));

    // コメント読み込み
    const cdata = await fetchJSON(
        `/api/examadjustcomment_subject/?subjectNo=${subjectNo}&fsyear=${fsyear}&term=${term}`
    );
    console.log("examadjust_subject response:", data);

    document.getElementById("adjust-comment").value = cdata.adjust_comment || "";
    globalComment = cdata.adjust_comment || "";

    renderAdjustTable();

    // -------------------------
    // ボタン設定
    // -------------------------
    document.getElementById("updateButton").addEventListener("click", () => {
        updateAdjustments(subjectNo, fsyear, term);
    });

    // ★ 一覧に戻る（URL パラメータつき）
    document.getElementById("backButton").addEventListener("click", () => {
        const url =
            `/?subjectNo=${subjectNo}` +
            `&fsyear=${fsyear}` +
            `&term=${term}`;
        console.log("戻る:", url);
        location.href = url;
    });
}

// ------------------------
async function fetchJSON(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) console.error("fetch error:", url, res.status);
    return await res.json();
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

// ------------------------
// テーブル描画
// ------------------------
function renderAdjustTable() {
    const tbody = document.getElementById("student-table-body");
    tbody.innerHTML = "";

    students.forEach((stu, idx) => {

        // ★ API から返る正しい素点（score）+ 補正（hosei）
        const baseTotal = (stu.score || 0) + (stu.hosei || 0);

        const tr = document.createElement("tr");

        tr.innerHTML = `
            <td>${stu.stdNo}</td>
            <td>${stu.nickname}</td>
            <td>${baseTotal}</td>
            <td><input id="adj-${idx}" type="number" min="0" value="${stu.adjust}"></td>
            <td id="total-${idx}">${baseTotal + stu.adjust}</td>
        `;

        // 入力イベント（合計値の再計算）
        tr.querySelector(`#adj-${idx}`).addEventListener("input", e => {
            let val = parseInt(e.target.value, 10);
            if (isNaN(val) || val < 0) val = 0;

            students[idx].adjust = val;
            document.getElementById(`total-${idx}`).textContent =
                baseTotal + val;
        });

        tbody.appendChild(tr);
    });
}

// ------------------------
// 更新処理（科目ベース）
// ------------------------
async function updateAdjustments(subjectNo, fsyear, term) {

    // 変更されたものだけ送る
    const changed = students.filter(stu => stu.adjust !== stu.originalAdjust);

    // -------- Adjust 更新 --------
    if (changed.length > 0) {
        await fetch("/api/exam-adjust-update-subject/", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                subjectNo,
                fsyear,
                term,
                items: changed
            })
        });
    }

    // -------- コメント更新 --------
    const newComment = document.getElementById("adjust-comment").value;
    if (newComment !== globalComment) {
        await fetch(
            `/api/examadjustcomment_subject/?subjectNo=${subjectNo}&fsyear=${fsyear}&term=${term}`,
            {
                method: "PUT",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ adjust_comment: newComment }),
            }
        );
    }

//    alert("更新しました");
}