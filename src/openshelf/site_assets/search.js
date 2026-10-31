// Client-side search over titles and summaries in catalog.json.
(() => {
  const box = document.querySelector(".search");
  if (!box) return;
  const input = box.querySelector("input");
  const list = box.querySelector(".results");
  const root = box.dataset.root;
  let pages = null;

  const load = async () => {
    if (!pages) pages = (await (await fetch(root + "catalog.json")).json()).pages;
    return pages;
  };
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const hide = () => { list.hidden = true; };

  input.addEventListener("focus", () => { load().catch(() => {}); }, { once: true });
  input.addEventListener("input", async () => {
    const words = input.value.toLowerCase().split(/\s+/).filter(Boolean);
    if (!words.length) { list.innerHTML = ""; hide(); return; }
    let all;
    try { all = await load(); } catch { list.innerHTML = '<li class="empty">Search is unavailable here</li>'; list.hidden = false; return; }
    const hits = all
      .map((p) => {
        const title = p.title.toLowerCase();
        const text = `${title} ${(p.summary || "").toLowerCase()} ${p.id.toLowerCase()}`;
        if (!words.every((w) => text.includes(w))) return null;
        return { p, score: words.filter((w) => title.includes(w)).length };
      })
      .filter(Boolean)
      .sort((a, b) => b.score - a.score || a.p.title.localeCompare(b.p.title))
      .slice(0, 10);
    list.innerHTML = hits.length
      ? hits.map(({ p }) => `<li><a href="${esc(root + p.url)}"><strong>${esc(p.title)}</strong><span>${esc(p.summary || "")}</span></a></li>`).join("")
      : '<li class="empty">No matching pages</li>';
    list.hidden = false;
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { input.value = ""; hide(); }
    if (e.key === "ArrowDown") { const first = list.querySelector("a"); if (first) { e.preventDefault(); first.focus(); } }
  });
  list.addEventListener("keydown", (e) => {
    const links = [...list.querySelectorAll("a")];
    const i = links.indexOf(document.activeElement);
    if (e.key === "ArrowDown" && i < links.length - 1) { e.preventDefault(); links[i + 1].focus(); }
    if (e.key === "ArrowUp") { e.preventDefault(); (i > 0 ? links[i - 1] : input).focus(); }
    if (e.key === "Escape") { hide(); input.focus(); }
  });
  document.addEventListener("click", (e) => { if (!box.contains(e.target)) hide(); });
})();
