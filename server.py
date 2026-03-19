import aiohttp
from aiohttp import web, WSMsgType
import aiofiles
from pathlib import Path
from datetime import datetime
import json
from urllib.parse import unquote

PORT = 5000
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Liste des clients WebSocket
ws_clients = set()

# -------------------------
# Page HTML
# -------------------------
INDEX_HTML = """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Chat WebSocket</title>
<style>
body { font-family: Arial; margin:30px; background:#f4f6f9; }
#chat { height:400px; overflow-y:auto; border-radius:12px; padding:15px; background:white; box-shadow:0 4px 12px rgba(0,0,0,0.1); margin-bottom:15px; display:flex; flex-direction:column; }
.message { max-width:70%; padding:10px 14px; margin-bottom:8px; border-radius:14px; display:flex; justify-content:space-between; align-items:flex-start; }
.mine { align-self:flex-end; background:#007bff; color:white; }
.other { align-self:flex-start; background:#e4e6eb; color:black; }
.msg-content { word-break:break-word; white-space:pre-wrap; }
.msg-content * { max-width:100%; }
.mine .msg-content a { color:#cce5ff; }
.time { font-size:11px; opacity:0.7; margin-top:4px; }
.copy-btn { background:none; border:none; cursor:pointer; margin-left:10px; flex-shrink:0; }
button { padding:8px 12px; border-radius:6px; border:none; background:#007bff; color:white; cursor:pointer; }
.file-box { background:white; padding:10px; border-radius:8px; box-shadow:0 2px 6px rgba(0,0,0,0.1); margin-bottom:15px; }
.toolbar { display:flex; align-items:center; gap:16px; margin-bottom:6px; }
.toolbar label { font-size:13px; color:#555; display:flex; align-items:center; gap:5px; cursor:pointer; }
#msg {
    padding:10px; min-height:60px; max-height:200px; overflow-y:auto;
    width:75%; box-sizing:border-box;
    border-radius:8px; border:1px solid #ccc; background:white;
    font-family:Arial; font-size:14px;
    outline:none; vertical-align:top;
    display:inline-block;
    white-space:pre-wrap; word-break:break-word;
}
#msg:empty:before { content:attr(data-placeholder); color:#aaa; pointer-events:none; }
#msg code { background:#f0f0f0; padding:1px 5px; border-radius:4px; font-family:monospace; font-size:13px; }
#msg pre { background:#f0f0f0; padding:8px; border-radius:6px; margin:4px 0; font-family:monospace; font-size:13px; white-space:pre; overflow-x:auto; }
.message code { background:rgba(0,0,0,0.12); padding:1px 5px; border-radius:4px; font-family:monospace; font-size:13px; }
.message pre { background:rgba(0,0,0,0.08); padding:8px; border-radius:6px; overflow-x:auto; margin:4px 0; font-family:monospace; font-size:13px; white-space:pre; }
.mine code, .mine pre { background:rgba(255,255,255,0.2); }
</style>
</head>
<body>
<h2>💬 Chat WebSocket</h2>
<div id="chat"></div>
<div class="toolbar">
  <label title="Colle et conserve le formatage HTML (gras, italique, listes...)">
    <input type="checkbox" id="richToggle" checked> 🎨 Conserver le formatage au collage
  </label>
</div>
<div id="msg" contenteditable="true" data-placeholder="Votre message... (Entrée pour envoyer, Shift+Entrée pour sauter une ligne)"></div>
<button id="sendBtn" style="vertical-align:top;margin-left:8px;">Envoyer</button>
<hr>
<div class="file-box">
<h3>📤 Upload fichier</h3>
<form method="POST" action="/upload" enctype="multipart/form-data">
<input type="file" name="file"><input type="submit" value="Upload">
</form>
</div>
<div class="file-box">
<h3>📁 Fichiers disponibles</h3>
<div id="files"></div>
</div>
<script>
document.addEventListener("DOMContentLoaded", function() {
function generateUUID(){return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,function(c){const r=Math.random()*16|0; const v=c==='x'?r:(r&0x3|0x8);return v.toString(16);});}
let userId=localStorage.getItem("userId"); if(!userId){userId=generateUUID(); localStorage.setItem("userId",userId);}
const ws=new WebSocket("ws://"+location.host+"/ws");
const chat=document.getElementById("chat");
const msgInput=document.getElementById("msg");
const sendBtn=document.getElementById("sendBtn");
const filesDiv=document.getElementById("files");
const richToggle=document.getElementById("richToggle");

// Gestion du collage : riche ou texte brut selon la checkbox
msgInput.addEventListener("paste", function(e){
    e.preventDefault();
    var cd=e.clipboardData || window.clipboardData;
    if(richToggle.checked && cd.types && (cd.types.indexOf("text/html")>=0 || cd.types.contains && cd.types.contains("text/html"))){
        var html=cd.getData("text/html");
        // Nettoyage léger : supprime les balises span avec styles excessifs mais garde structure
        var clean=sanitizeHtml(html);
        document.execCommand("insertHTML", false, clean);
    } else {
        var text=cd.getData("text/plain");
        document.execCommand("insertText", false, text);
    }
});

function sanitizeHtml(html){
    var tmp=document.createElement("div");
    tmp.innerHTML=html;
    // Supprime scripts et styles embarqués
    tmp.querySelectorAll("script,style,meta,link,head").forEach(function(el){el.remove();});

    // Convertit les éléments block (div, p, h1-h6) en inline avec <br>
    // pour éviter les doubles sauts de ligne sur anciens navigateurs
    var blocks=["div","p","h1","h2","h3","h4","h5","h6","blockquote"];
    tmp.querySelectorAll(blocks.join(",")).forEach(function(el){
        // Ajoute un <br> après le contenu si l'élément n'est pas le dernier
        if(el.nextSibling || el.parentNode!==tmp){
            el.insertAdjacentHTML("afterend","<br>");
        }
        // Remplace la balise block par son contenu inline
        while(el.firstChild){ el.parentNode.insertBefore(el.firstChild, el); }
        el.remove();
    });

    // Nettoie les attributs sur les balises restantes
    tmp.querySelectorAll("*").forEach(function(el){
        var tag=el.tagName.toLowerCase();
        var keep=["b","strong","i","em","u","s","del","code","pre","br","ul","ol","li","a","span","table","tr","td","th"];
        if(keep.indexOf(tag)<0){
            el.replaceWith(document.createTextNode(el.textContent));
        } else {
            var allowed={"a":["href"],"td":["colspan","rowspan"],"th":["colspan","rowspan"]};
            var allowedAttrs=allowed[tag]||[];
            Array.from(el.attributes).forEach(function(attr){
                if(allowedAttrs.indexOf(attr.name)<0) el.removeAttribute(attr.name);
            });
        }
    });

    // Supprime les <br> en double ou en debut/fin
    var result=tmp.innerHTML;
    var brClean=function(s){
        s=s.replace(/<br>/gi,"<br>");
        var prev="";
        while(prev!==s){ prev=s; s=s.replace(/<br><br><br>/gi,"<br><br>"); }
        s=s.replace(/^(<br>)+/i,"");
        s=s.replace(/(<br>)+$/i,"");
        return s;
    };
    result=brClean(result);
    return result;
}

// Entrée = envoyer, Shift+Entrée = saut de ligne
msgInput.addEventListener("keydown", function(e){
    if(e.key==="Enter" && !e.shiftKey){ e.preventDefault(); sendMsg(); }
});

sendBtn.addEventListener("click", sendMsg);

function sendMsg(){
    var html=msgInput.innerHTML.trim();
    var text=msgInput.innerText.trim();
    if(text===""){ return; }
    if(ws.readyState===WebSocket.OPEN){
        ws.send(JSON.stringify({message:html, plain:text, userId:userId}));
    } else { alert("Connexion WebSocket fermée. Rechargez la page."); }
    msgInput.innerHTML="";
}

ws.onmessage=function(event){
    var data=JSON.parse(event.data);
    addMessageToChat(data.message, data.plain, data.time, data.userId);
};

function addMessageToChat(html, plain, time, senderId){
    var container=document.createElement("div");
    container.className="message "+(senderId===userId?"mine":"other");
    var content=document.createElement("div");
    content.style.flex="1";
    var msgDiv=document.createElement("div");
    msgDiv.className="msg-content";
    msgDiv.innerHTML=html;
    var timeDiv=document.createElement("div");
    timeDiv.className="time";
    timeDiv.textContent=time;
    var copyBtn=document.createElement("button");
    copyBtn.className="copy-btn";
    copyBtn.textContent="📋";
    copyBtn.title="Copier";
    copyBtn.onclick=function(){
        var raw=plain||msgDiv.innerText;
        var richHtml=html;
        if(richToggle.checked){
            if(navigator.clipboard && window.ClipboardItem){
                // Navigateur moderne : ClipboardItem avec HTML + texte brut
                try {
                    var item=new ClipboardItem({
                        "text/html": new Blob([richHtml], {type:"text/html"}),
                        "text/plain": new Blob([raw], {type:"text/plain"})
                    });
                    navigator.clipboard.write([item]).catch(function(){ fallbackRichCopy(richHtml); });
                } catch(err){ fallbackRichCopy(richHtml); }
            } else {
                // Ancien navigateur : copie riche via div contenteditable temporaire
                fallbackRichCopy(richHtml);
            }
        } else if(navigator.clipboard && navigator.clipboard.writeText){
            navigator.clipboard.writeText(raw);
        } else {
            fallbackPlainCopy(raw);
        }
    };

    function fallbackRichCopy(richHtml){
        var el=document.createElement("div");
        el.contentEditable="true";
        el.innerHTML=richHtml;
        el.style.position="fixed";
        el.style.left="-9999px";
        el.style.top="0";
        el.style.opacity="0";
        document.body.appendChild(el);
        var sel=window.getSelection();
        var range=document.createRange();
        range.selectNodeContents(el);
        sel.removeAllRanges();
        sel.addRange(range);
        try{ document.execCommand("copy"); } catch(err){ console.warn("Copie riche échouée",err); }
        sel.removeAllRanges();
        document.body.removeChild(el);
    }

    function fallbackPlainCopy(text){
        var ta=document.createElement("textarea");
        ta.value=text; ta.style.position="fixed"; ta.style.left="-9999px"; ta.style.opacity="0";
        document.body.appendChild(ta); ta.focus(); ta.select();
        try{ document.execCommand("copy"); } catch(err){ console.warn("Copie échouée",err); }
        document.body.removeChild(ta);
    }
    content.appendChild(msgDiv);
    content.appendChild(timeDiv);
    container.appendChild(content);
    container.appendChild(copyBtn);
    chat.appendChild(container);
    chat.scrollTop=chat.scrollHeight;
}

function loadFiles(){
    fetch("/files").then(r=>r.json()).then(data=>{
        var html="";
        data.forEach(function(f){ html+='<div><a href="/uploads/'+f+'">'+f+'</a></div>'; });
        filesDiv.innerHTML=html;
    });
}
loadFiles(); setInterval(loadFiles,3000);
});
</script>
</body>
</html>
"""

# -------------------------
# HTTP Routes
# -------------------------
async def index(request):
    return web.Response(text=INDEX_HTML, content_type='text/html')

async def list_files(request):
    files = [f.name for f in UPLOAD_DIR.iterdir() if f.is_file()]
    return web.json_response(files)

async def uploads_file(request):
    filename = Path(unquote(request.match_info['filename'])).name
    filepath = UPLOAD_DIR / filename
    if not filepath.exists():
        return web.Response(status=404, text="File not found")
    return web.FileResponse(filepath)

async def upload_file(request):
    reader = await request.multipart()
    async for part in reader:
        if part.filename:
            filename = Path(part.filename).name
            fpath = UPLOAD_DIR / filename
            async with aiofiles.open(fpath, 'wb') as f:
                while True:
                    chunk = await part.read_chunk()
                    if not chunk: break
                    await f.write(chunk)
    raise web.HTTPFound('/')

# -------------------------
# WebSocket route
# -------------------------
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws_clients.add(ws)
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                data = json.loads(msg.data)
                payload = json.dumps({
                    "message": data["message"],
                    "userId": data["userId"],
                    "time": datetime.now().strftime("%H:%M:%S")
                })
                to_remove = set()
                for client in ws_clients:
                    try:
                        await client.send_str(payload)
                    except:
                        to_remove.add(client)
                ws_clients.difference_update(to_remove)
            elif msg.type == WSMsgType.ERROR:
                print(f"WebSocket error: {ws.exception()}")
    finally:
        ws_clients.discard(ws)
    return ws

# -------------------------
# App setup
# -------------------------
app = web.Application()
app.add_routes([
    web.get('/', index),
    web.get('/files', list_files),
    web.get('/uploads/{filename}', uploads_file),
    web.post('/upload', upload_file),
    web.get('/ws', websocket_handler),
])

if __name__ == '__main__':
    web.run_app(app, port=PORT)