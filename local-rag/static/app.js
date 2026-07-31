/**
 * app.js —— 前端交互（教学版）
 *
 * 职责很单纯：
 *   点按钮 → 调后端 API → 把 JSON 结果显示到页面
 * AI / 检索逻辑全部在 Python，浏览器不做模型计算。
 */

/** 封装 fetch：统一解析 JSON、把错误变成 Error */
async function api(path, options = {}) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || data.message || res.statusText);
  }
  return data;
}

/** 创建 DOM 节点的小工具 */
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

/** 刷新顶部状态 + 左侧文档列表 */
async function refreshStatus() {
  const s = await api("/api/status");
  const badge = document.getElementById("badge");
  if (s.llm_enabled && s.has_index) {
    badge.textContent = `就绪 · ${s.chunk_count} 片段 · ${s.llm_model}`;
    badge.className = "badge ok";
  } else if (!s.llm_enabled) {
    badge.textContent = "未配置 LLM（可先建索引）";
    badge.className = "badge warn";
  } else {
    badge.textContent = "已配置 LLM · 请重建索引";
    badge.className = "badge warn";
  }

  document.getElementById("indexInfo").textContent = s.has_index
    ? `索引：${s.chunk_count} 段 / 模型 ${s.embedding_model}`
    : "尚未建索引";

  const list = document.getElementById("docs");
  list.innerHTML = "";
  if (!s.docs.length) {
    list.appendChild(el("li", "", "暂无文档，请上传 txt/md/pdf"));
    return;
  }
  for (const name of s.docs) {
    const li = el("li");
    li.appendChild(el("span", "", name));
    const btn = el("button", "", "删除");
    btn.onclick = async () => {
      // 只删 docs 文件；索引要用户再点「重建」
      await api("/api/docs/" + encodeURIComponent(name), { method: "DELETE" });
      await refreshStatus();
    };
    li.appendChild(btn);
    list.appendChild(li);
  }
}

/** 往聊天区追加一条消息；citations 是检索到的原文 */
function addMsg(role, text, citations) {
  const box = document.getElementById("chat");
  const msg = el("div", "msg " + (role === "user" ? "user" : "bot"), text);
  if (citations && citations.length) {
    const cite = el("div", "cite");
    cite.textContent = citations
      .map((c) => `[资料${c.rank}] ${c.source} · ${c.score}\n${c.text.slice(0, 120)}…`)
      .join("\n\n");
    msg.appendChild(cite);
  }
  box.appendChild(msg);
  box.scrollTop = box.scrollHeight;
}

// —— 上传：FormData 发文件 ——
document.getElementById("btnUpload").onclick = async () => {
  const input = document.getElementById("file");
  if (!input.files.length) return alert("请选择文件");
  const fd = new FormData();
  fd.append("file", input.files[0]);
  await api("/api/upload", { method: "POST", body: fd });
  input.value = "";
  await refreshStatus();
};

// —— 重建索引：后端跑切片 + 嵌入（可能较慢）——
document.getElementById("btnReindex").onclick = async () => {
  const btn = document.getElementById("btnReindex");
  btn.disabled = true;
  btn.textContent = "索引中…";
  try {
    const r = await api("/api/reindex", { method: "POST" });
    alert(`完成：${r.docs} 个文档，${r.chunks} 个片段`);
    await refreshStatus();
  } catch (e) {
    alert(e.message || String(e));
  } finally {
    btn.disabled = false;
    btn.textContent = "重建索引";
  }
};

// —— 提问：拿到 answer + citations ——
document.getElementById("btnAsk").onclick = async () => {
  const q = document.getElementById("question").value.trim();
  if (!q) return;
  const btn = document.getElementById("btnAsk");
  btn.disabled = true;
  addMsg("user", q);
  document.getElementById("question").value = "";
  try {
    const r = await api("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    addMsg("bot", r.answer, r.citations);
  } catch (e) {
    addMsg("bot", "出错：" + (e.message || String(e)));
  } finally {
    btn.disabled = false;
  }
};

// Cmd/Ctrl + Enter 快捷提问
document.getElementById("question").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
    document.getElementById("btnAsk").click();
  }
});

// 页面加载后先拉一次状态
refreshStatus().catch((e) => {
  document.getElementById("badge").textContent = "服务异常";
  document.getElementById("badge").className = "badge warn";
  console.error(e);
});
