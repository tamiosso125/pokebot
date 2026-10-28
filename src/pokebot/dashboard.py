import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pokebot import db
from pokebot.board import listing_rows
from pokebot.config import Settings

PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PokeBot</title>
<style>
:root{color-scheme:light dark;--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#ddd;--good:#0a7d33;--bad:#b3261e}
@media(prefers-color-scheme:dark){:root{--bg:#16181c;--fg:#eee;--mut:#9aa;--line:#2c3036;--good:#5fd38a;--bad:#ff8a80}}
body{margin:0;font:15px system-ui,sans-serif;background:var(--bg);color:var(--fg)}
header{padding:12px 16px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center;flex-wrap:wrap}
h1{font-size:18px;margin:0 auto 0 0}label{color:var(--mut)}input,select{font:inherit;padding:4px}
main{padding:0 16px 24px}table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:600;cursor:pointer;white-space:nowrap}
img{width:56px;height:56px;object-fit:cover;border-radius:4px}
.good{color:var(--good);font-weight:600}.bad{color:var(--bad)}.mut{color:var(--mut);font-size:13px}
a{color:inherit}.empty{padding:32px 0;color:var(--mut)}
@media(max-width:700px){.hide{display:none}}
</style></head><body>
<header><h1>PokeBot</h1>
<label>Desconto mínimo <input id="min" type="number" value="0" min="-100" max="100" style="width:4em">%</label>
<label><input id="onlycard" type="checkbox"> só com carta identificada</label>
<span class="mut" id="stamp"></span></header>
<main><table><thead><tr><th></th><th data-k="title">Anúncio</th><th data-k="price">Preço</th>
<th class="hide" data-k="reference_brl">Referência</th><th data-k="discount_pct">Desconto</th>
<th class="hide" data-k="condition">Condição</th></tr></thead><tbody id="rows"></tbody></table>
<div class="empty" id="empty" hidden>Nenhum anúncio com esses filtros.</div></main>
<script>
let data=[],sortKey="discount_pct",desc=true;
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const brl=v=>v==null?"—":"R$ "+v.toFixed(2).replace(".",",");
function render(){
  const min=parseFloat($("min").value)||0, only=$("onlycard").checked;
  let rows=data.filter(r=>(!only||r.card_id)&&(min<=0||(r.discount_pct!=null&&r.discount_pct>=min)));
  rows.sort((a,b)=>{const x=a[sortKey],y=b[sortKey];if(x==null)return 1;if(y==null)return -1;return (x>y?1:x<y?-1:0)*(desc?-1:1)});
  $("empty").hidden=rows.length>0;
  $("rows").innerHTML=rows.map(r=>`<tr>
   <td>${r.image_url?`<img src="${esc(r.image_url)}" alt="" loading="lazy">`:""}</td>
   <td><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.title)}</a>
     <div class="mut">${esc(r.source)}${r.card_name?" · "+esc(r.card_name):" · carta não identificada"}</div></td>
   <td>${r.currency==="BRL"?brl(r.price):esc((r.currency||"")+" "+(r.price??"—"))}</td>
   <td class="hide">${brl(r.reference_brl)}<div class="mut">${esc(r.reference_source||"")}</div></td>
   <td class="${r.discount_pct>=30?"good":r.discount_pct<0?"bad":""}">${r.discount_pct==null?"—":r.discount_pct.toFixed(0)+"%"}</td>
   <td class="hide">${r.condition?esc(r.condition)+` <span class="mut">${Math.round((r.condition_confidence||0)*100)}%${r.in_protective_case?" · em proteção":""}</span>`:"—"}</td>
  </tr>`).join("");
}
document.querySelectorAll("th[data-k]").forEach(th=>th.onclick=()=>{const k=th.dataset.k;desc=k===sortKey?!desc:true;sortKey=k;render()});
$("min").oninput=render;$("onlycard").onchange=render;
async function load(){try{const r=await fetch("/api/listings");data=await r.json();$("stamp").textContent="atualizado "+new Date().toLocaleTimeString();render()}catch(e){$("stamp").textContent="sem conexão com o servidor"}}
load();setInterval(load,30000);
</script></body></html>"""


def make_handler(settings: Settings):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                body, ctype = PAGE.encode(), "text/html; charset=utf-8"
            elif self.path == "/api/listings":
                conn = db.connect(settings.db_path)  # conexão por requisição: o servidor usa várias threads
                try:
                    body = json.dumps(listing_rows(conn, settings.usd_brl), ensure_ascii=False).encode()
                finally:
                    conn.close()
                ctype = "application/json; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return Handler


def serve(settings: Settings, port: int) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(settings))  # só acessível nesta máquina
    print(f"Painel em http://127.0.0.1:{port}  (Ctrl+C para parar)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
